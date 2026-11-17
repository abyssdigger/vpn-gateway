"""First executable NG3 alpha runtime assembly.

This module intentionally assembles only already accepted Release-1 mechanisms:
- structural Device/Profile + integration transport configuration;
- direct-device VPN path realization;
- omitted Device firewall;
- explicit internal NatIntent.NONE for this alpha deployment slice;
- one local PayloadTrafficManager-style periodic reconciliation loop.

It does not define the postponed final Device NAT/firewall/publication TOML grammar.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Address, IPv4Interface
import os
from pathlib import Path
import signal
import socket
import sys
import threading
from typing import Iterable

from .binding import DeviceBindingState, project_device_bindings
from .config import parse_structural_config
from .controller_startup import (
    ControllerStartupStatus,
    start_controller_once,
)
from .controller_stop import (
    ControllerStopStatus,
    stop_controller_once,
)
from .device_policy import (
    DeviceFirewallPolicyIntent,
    DeviceNatPolicyIntent,
    NatIntent,
)
from .direct_device_route import realize_direct_device_path_routes
from .forwarding_gate import (
    ForwardingGateState,
    converge_forwarding_gate_once,
)
from .instance_lock import InstanceLockSpec
from .integration_config import (
    IntegrationTransportConfig,
    parse_integration_transport_config,
)
from .interface_identity import InterfaceIdentity
from .interface_inventory import parse_ip_link_inventory
from .linux_forwarding_gate import LinuxForwardingGateBackend
from .linux_nft_scaffold import (
    LinuxNftScaffoldBackend,
    SubprocessNftRunner,
)
from .linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from .linux_structural_policy import LinuxStructuralPolicyBackend
from .local_integration_policy import IntegrationLocalTransportIntent
from .managed_network_domain import (
    ManagedNetworkDomainSpec,
    verify_managed_network_domain,
)
from .network_policy_activation import (
    NetworkPolicyActivationResult,
    activate_network_policy,
)
from .network_policy_layout import allocate_network_policy_layout
from .payload_network_policy_desired import (
    PayloadNetworkPolicyDesiredState,
    build_payload_network_policy_desired_state,
)
from .payload_profile import build_payload_profile_requests
from .structural_policy_mutation import compare_structural_policy


ALPHA_NAMESPACE = "vpn-gate-alpha"
ALPHA_HOST_INTERFACE = "vnga-host0"
ALPHA_INNER_INTERFACE = "vnga-inner0"
ALPHA_HOST_ADDRESS = IPv4Interface("198.19.255.1/30")
ALPHA_INNER_ADDRESS = IPv4Interface("198.19.255.2/30")
ALPHA_RUNTIME_DIRECTORY = Path("/run/vpn-gate-alpha")
ALPHA_AUDIT_INTERVAL_SECONDS = 1.0


class AlphaRuntimeError(RuntimeError):
    pass


@dataclass(slots=True)
class AlphaPreparedPolicy:
    """Accepted config + current Device binding state for the alpha Manager."""

    local_address: IPv4Address
    binding_state: DeviceBindingState
    structural: object
    integrations: tuple[IntegrationTransportConfig, ...]

    @classmethod
    def from_text(
        cls,
        text: str,
        *,
        local_address: IPv4Address,
    ) -> "AlphaPreparedPolicy":
        structural = parse_structural_config(text)
        integrations = parse_integration_transport_config(text)

        known_devices = set(structural.devices)
        for item in integrations:
            if item.device_id not in known_devices:
                raise AlphaRuntimeError(
                    f"integration {item.integration_id!r} references unknown "
                    f"Device {item.device_id!r}"
                )

        return cls(
            local_address=local_address,
            binding_state=DeviceBindingState.empty(),
            structural=structural,
            integrations=integrations,
        )

    def build_current(
        self,
        host_boundary: InterfaceIdentity,
        interfaces: tuple[InterfaceIdentity, ...],
    ) -> PayloadNetworkPolicyDesiredState:
        projection = project_device_bindings(
            self.structural.device_binding_intents,
            self.binding_state,
            interfaces,
        )
        self.binding_state = projection.next_state

        profiles = build_payload_profile_requests(
            self.structural.profiles.values(),
            projection.bindings,
        )
        path_routes = realize_direct_device_path_routes(projection.bindings)
        layout = allocate_network_policy_layout(
            profiles,
            (),
            NG3_LINUX_POLICY_PLATFORM,
        )

        # The final external Device NAT grammar is intentionally still gated.
        # This alpha slice proves the runtime on a topology with an explicit
        # reverse route and therefore has no Device source-NAT contribution.
        nat_policies = tuple(
            DeviceNatPolicyIntent(device_id, NatIntent.NONE)
            for device_id in sorted(self.structural.active_device_ids)
        )
        firewall_policies = tuple(
            DeviceFirewallPolicyIntent(device_id, rules=None)
            for device_id in sorted(self.structural.active_device_ids)
        )

        integration_intents = tuple(
            IntegrationLocalTransportIntent(
                integration_id=item.integration_id,
                protocol=item.protocol,
                host_boundary=host_boundary,
                local_address=self.local_address,
                remote_address=item.remote_address,
                remote_port=item.remote_port,
                local_port=item.local_port,
            )
            for item in self.integrations
            if item.device_id in self.structural.active_device_ids
        )

        return build_payload_network_policy_desired_state(
            profiles,
            layout,
            path_routes,
            host_boundary,
            nat_policies,
            firewall_policies,
            (),
            integration_intents,
        )


class AlphaReconcileStatus(str, Enum):
    EXACT = "exact"
    RECONCILED = "reconciled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AlphaReconcileResult:
    status: AlphaReconcileStatus
    desired: PayloadNetworkPolicyDesiredState | None
    activation: NetworkPolicyActivationResult | None = None
    diagnostic: str | None = None

    @property
    def ready(self) -> bool:
        return self.status in {
            AlphaReconcileStatus.EXACT,
            AlphaReconcileStatus.RECONCILED,
        }


def reconcile_alpha_payload_once(
    prepared: AlphaPreparedPolicy,
    domain_spec: ManagedNetworkDomainSpec,
    runner: SubprocessNftRunner,
) -> AlphaReconcileResult:
    """Freshly audit one Manager-owned payload domain and converge only on drift."""
    verification = verify_managed_network_domain(domain_spec, runner)
    if not verification.confirmed or verification.host_boundary is None:
        containment_detail = "not attempted"
        try:
            containment = converge_forwarding_gate_once(
                LinuxForwardingGateBackend(runner, domain_spec.namespace),
                ForwardingGateState.DISABLED,
            )
            containment_detail = (
                "confirmed"
                if containment.confirmed
                else (
                    "not confirmed"
                    + (
                        f": {containment.diagnostic}"
                        if containment.diagnostic
                        else ""
                    )
                )
            )
        except Exception as exc:
            containment_detail = (
                f"failed: {type(exc).__name__}: {exc}"
            )
        return AlphaReconcileResult(
            AlphaReconcileStatus.FAILED,
            None,
            diagnostic=(
                "managed network domain failed exact verification: "
                + "; ".join(verification.errors)
                + f"; fail-closed containment={containment_detail}"
            ),
        )

    try:
        interfaces = parse_ip_link_inventory(
            runner.run(
                (
                    "ip",
                    "-n",
                    domain_spec.namespace,
                    "-j",
                    "link",
                    "show",
                )
            )
        )
        desired = prepared.build_current(
            verification.host_boundary,
            interfaces,
        )
    except Exception as exc:
        return AlphaReconcileResult(
            AlphaReconcileStatus.FAILED,
            None,
            diagnostic=f"desired-state rebuild failed: {type(exc).__name__}: {exc}",
        )

    gate_backend = LinuxForwardingGateBackend(runner, domain_spec.namespace)
    structural_backend = LinuxStructuralPolicyBackend(
        runner=runner,
        namespace=domain_spec.namespace,
        platform=NG3_LINUX_POLICY_PLATFORM,
    )

    # Fast no-op audit path: do not close forwarding merely because the local
    # Manager's periodic audit fired.
    try:
        snapshot = structural_backend.observe_structural_snapshot()
        comparison = compare_structural_policy(
            snapshot,
            desired.routing,
            desired.nft,
            NG3_LINUX_POLICY_PLATFORM,
        )
        gate = gate_backend.observe_forwarding_gate()
        if comparison.desired_confirmed and gate is ForwardingGateState.ENABLED:
            return AlphaReconcileResult(
                AlphaReconcileStatus.EXACT,
                desired,
            )
    except Exception:
        # The guarded activation boundary below re-observes from authoritative
        # state, closes forwarding first and classifies the concrete failure.
        pass

    activation = activate_network_policy(
        gate_backend,
        LinuxNftScaffoldBackend(runner, domain_spec.namespace),
        structural_backend,
        desired.routing,
        desired.nft,
        NG3_LINUX_POLICY_PLATFORM,
    )
    if activation.ready:
        return AlphaReconcileResult(
            AlphaReconcileStatus.RECONCILED,
            desired,
            activation=activation,
        )

    return AlphaReconcileResult(
        AlphaReconcileStatus.FAILED,
        desired,
        activation=activation,
        diagnostic=(
            activation.diagnostic
            or f"network-policy activation failed: {activation.status.value}"
        ),
    )


def _domain_spec() -> ManagedNetworkDomainSpec:
    return ManagedNetworkDomainSpec(
        namespace=ALPHA_NAMESPACE,
        host_interface=ALPHA_HOST_INTERFACE,
        inner_interface=ALPHA_INNER_INTERFACE,
        host_address=ALPHA_HOST_ADDRESS,
        inner_address=ALPHA_INNER_ADDRESS,
    )


def _notify_systemd(message: str) -> bool:
    notify_socket = os.environ.get("NOTIFY_SOCKET")
    if not notify_socket:
        return False

    address = (
        "\0" + notify_socket[1:]
        if notify_socket.startswith("@")
        else notify_socket
    )
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
        sock.connect(address)
        sock.sendall(message.encode("utf-8"))
    return True


def _log(marker: str, detail: str = "") -> None:
    print(
        marker + (f" {detail}" if detail else ""),
        flush=True,
    )


def run_alpha_runtime(
    config_path: Path,
    *,
    audit_interval_seconds: float = ALPHA_AUDIT_INTERVAL_SECONDS,
) -> int:
    if os.geteuid() != 0:
        raise AlphaRuntimeError("alpha runtime must run as root")
    if audit_interval_seconds <= 0:
        raise ValueError("audit_interval_seconds must be positive")

    runner = SubprocessNftRunner()
    domain_spec = _domain_spec()
    stop_event = threading.Event()
    holder: dict[str, AlphaPreparedPolicy] = {}

    def request_stop(signum, _frame):
        _log("VPNG_ALPHA_STOP_REQUESTED", f"signal={signum}")
        stop_event.set()

    previous_sigterm = signal.signal(signal.SIGTERM, request_stop)
    previous_sigint = signal.signal(signal.SIGINT, request_stop)

    def load_policy() -> AlphaPreparedPolicy:
        text = config_path.read_text(encoding="utf-8")
        prepared = AlphaPreparedPolicy.from_text(
            text,
            local_address=domain_spec.inner_address.ip,
        )
        holder["policy"] = prepared
        return prepared

    try:
        startup = start_controller_once(
            InstanceLockSpec(
                runtime_directory=ALPHA_RUNTIME_DIRECTORY,
                expected_owner_uid=os.getuid(),
            ),
            domain_spec,
            runner,
            NG3_LINUX_POLICY_PLATFORM,
            load_policy,
            stop_requested=stop_event.is_set,
        )
        if startup.status is not ControllerStartupStatus.READY:
            _log(
                "VPNG_ALPHA_START_FAILED",
                f"status={startup.status.value} diagnostic={startup.diagnostic!r}",
            )
            return 1

        assert startup.session is not None
        prepared = holder["policy"]
        _log(
            "VPNG_ALPHA_READY",
            (
                f"namespace={domain_spec.namespace} "
                f"netns_path=/run/netns/{domain_spec.namespace}"
            ),
        )
        _notify_systemd(
            "READY=1\n"
            f"STATUS=VPN-GATE alpha ready in /run/netns/{domain_spec.namespace}"
        )

        last_status: AlphaReconcileStatus | None = None
        last_diagnostic: str | None = None
        while not stop_event.wait(audit_interval_seconds):
            result = reconcile_alpha_payload_once(
                prepared,
                domain_spec,
                runner,
            )
            if (
                result.status is not last_status
                or result.diagnostic != last_diagnostic
            ):
                _log(
                    "VPNG_ALPHA_RECONCILE",
                    (
                        f"status={result.status.value} "
                        f"diagnostic={result.diagnostic!r}"
                    ),
                )
                _notify_systemd(
                    f"STATUS=VPN-GATE alpha reconcile {result.status.value}"
                )
                last_status = result.status
                last_diagnostic = result.diagnostic

        _notify_systemd("STOPPING=1\nSTATUS=VPN-GATE alpha stopping")
        stopped = stop_controller_once(
            startup.session,
            domain_spec,
            runner,
        )
        _log(
            "VPNG_ALPHA_STOP",
            (
                f"status={stopped.status.value} "
                f"cleanup_error={stopped.cleanup_error!r} "
                f"lock_error={stopped.lock_error!r}"
            ),
        )
        return 0 if stopped.status is ControllerStopStatus.STOPPED else 2
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)
        signal.signal(signal.SIGINT, previous_sigint)


def _parse_args(argv: Iterable[str] | None = None):
    parser = argparse.ArgumentParser(
        prog="vpn-gate-alpha",
        description="First executable NG3 alpha runtime assembly",
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="accepted NG3 Device/Profile + integration TOML",
    )
    parser.add_argument(
        "--audit-interval",
        type=float,
        default=ALPHA_AUDIT_INTERVAL_SECONDS,
        help="local Manager audit interval in seconds (alpha implementation parameter)",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        return run_alpha_runtime(
            args.config,
            audit_interval_seconds=args.audit_interval,
        )
    except Exception as exc:
        _log(
            "VPNG_ALPHA_FATAL",
            f"{type(exc).__name__}: {exc}",
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
