"""Ordinary-host managed-routing contribution for Release-1 runtime."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .controller_boundary_contribution import ControllerBoundaryContribution
from .forwarding_gate import (
    ForwardingGateBackend,
    ForwardingGateState,
    converge_forwarding_gate_once,
)
from .linux_host_managed_routing import (
    HostManagedRoutingLinuxDesired,
    build_linux_host_managed_routing_desired,
)
from .linux_host_managed_routing_backend import (
    HostManagedRoutingObservation,
    LinuxHostManagedRoutingBackend,
    cleanup_host_managed_routing_once,
    converge_host_managed_routing_once,
)
from .linux_nft_scaffold import NftScriptRunner
from .linux_policy_platform import NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION
from .managed_network_domain import ManagedNetworkDomainSpec
from .release1_config import Release1Config
from .release1_host_managed_routing import build_release1_host_managed_routing_plan


@dataclass(frozen=True, slots=True)
class HostManagedRoutingRuntimeDesired:
    routing: HostManagedRoutingLinuxDesired


@dataclass(frozen=True, slots=True)
class HostManagedRoutingRuntimeObservation:
    exact: bool
    conflicts: tuple[str, ...]


class HostManagedRoutingRuntimeStatus(str, Enum):
    EXACT = "exact"
    RECONCILED = "reconciled"
    CONFLICT = "conflict"
    CONTAINMENT_FAILED = "containment_failed"
    CONVERGENCE_FAILED = "convergence_failed"
    POSTCONDITION_FAILED = "postcondition_failed"


@dataclass(frozen=True, slots=True)
class HostManagedRoutingRuntimeResult:
    status: HostManagedRoutingRuntimeStatus
    observation: HostManagedRoutingRuntimeObservation | None
    diagnostic: str | None = None

    @property
    def confirmed(self) -> bool:
        return self.status in {
            HostManagedRoutingRuntimeStatus.EXACT,
            HostManagedRoutingRuntimeStatus.RECONCILED,
        }


def build_host_managed_routing_runtime_desired(
    config: Release1Config,
    domain_spec: ManagedNetworkDomainSpec,
) -> HostManagedRoutingRuntimeDesired:
    if not isinstance(config, Release1Config):
        raise ValueError("config must be Release1Config")
    if not isinstance(domain_spec, ManagedNetworkDomainSpec):
        raise ValueError("domain_spec must be ManagedNetworkDomainSpec")

    boundary_owned_addresses = {domain_spec.inner_address.ip}
    for profile_id, semantic in config.profiles.items():
        if not config.structural.profiles[profile_id].enabled:
            continue
        address = semantic.effective_snat_address
        if address is not None and address in boundary_owned_addresses:
            raise ValueError(
                f"profile {profile_id!r} effective SNAT address {address} "
                "conflicts with managed-boundary service/address ownership"
            )

    plan = build_release1_host_managed_routing_plan(config)
    return HostManagedRoutingRuntimeDesired(
        routing=build_linux_host_managed_routing_desired(
            plan,
            host_interface=domain_spec.host_interface,
            allocation=NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION,
            stack_service_address=domain_spec.inner_address.ip,
        )
    )


@dataclass(slots=True)
class LinuxHostManagedRoutingContribution(ControllerBoundaryContribution):
    routing_backend: LinuxHostManagedRoutingBackend
    desired: HostManagedRoutingRuntimeDesired

    def observe(self) -> HostManagedRoutingRuntimeObservation:
        observed = self.routing_backend.observe(self.desired.routing)
        return HostManagedRoutingRuntimeObservation(
            exact=observed.exact,
            conflicts=observed.conflicts,
        )

    def converge(self) -> None:
        if not isinstance(self.desired, HostManagedRoutingRuntimeDesired):
            raise ValueError("desired must be HostManagedRoutingRuntimeDesired")
        converge_host_managed_routing_once(
            self.routing_backend,
            self.desired.routing,
        )

    def cleanup(self) -> None:
        cleanup_host_managed_routing_once(
            self.routing_backend,
            self.desired.routing,
        )


def reconcile_host_managed_routing_runtime_once(
    gate_backend: ForwardingGateBackend,
    contribution: LinuxHostManagedRoutingContribution | None,
) -> HostManagedRoutingRuntimeResult:
    """Audit/repair managed host routing only while payload forwarding is contained."""
    if contribution is None:
        return HostManagedRoutingRuntimeResult(
            HostManagedRoutingRuntimeStatus.EXACT,
            HostManagedRoutingRuntimeObservation(True, ()),
        )
    if not isinstance(contribution, LinuxHostManagedRoutingContribution):
        raise ValueError(
            "contribution must be LinuxHostManagedRoutingContribution or None"
        )

    try:
        observed = contribution.observe()
    except Exception as exc:
        containment = converge_forwarding_gate_once(
            gate_backend,
            ForwardingGateState.DISABLED,
        )
        if not containment.confirmed:
            return HostManagedRoutingRuntimeResult(
                HostManagedRoutingRuntimeStatus.CONTAINMENT_FAILED,
                None,
                (
                    f"host managed-routing observation failed: "
                    f"{type(exc).__name__}: {exc}; "
                    + (
                        containment.diagnostic
                        or "forwarding containment is not confirmed"
                    )
                ),
            )
        return HostManagedRoutingRuntimeResult(
            HostManagedRoutingRuntimeStatus.CONVERGENCE_FAILED,
            None,
            (
                f"host managed-routing observation failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    if observed.exact:
        return HostManagedRoutingRuntimeResult(
            HostManagedRoutingRuntimeStatus.EXACT,
            observed,
        )

    containment = converge_forwarding_gate_once(
        gate_backend,
        ForwardingGateState.DISABLED,
    )
    if not containment.confirmed:
        return HostManagedRoutingRuntimeResult(
            HostManagedRoutingRuntimeStatus.CONTAINMENT_FAILED,
            observed,
            containment.diagnostic or "forwarding containment is not confirmed",
        )

    if observed.conflicts:
        return HostManagedRoutingRuntimeResult(
            HostManagedRoutingRuntimeStatus.CONFLICT,
            observed,
            "host managed-routing owner conflict: " + "; ".join(observed.conflicts),
        )

    try:
        contribution.converge()
    except Exception as exc:
        return HostManagedRoutingRuntimeResult(
            HostManagedRoutingRuntimeStatus.CONVERGENCE_FAILED,
            observed,
            (
                f"host managed-routing convergence failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    try:
        final = contribution.observe()
    except Exception as exc:
        return HostManagedRoutingRuntimeResult(
            HostManagedRoutingRuntimeStatus.POSTCONDITION_FAILED,
            None,
            (
                f"host managed-routing final observation failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )
    if final.conflicts or not final.exact:
        return HostManagedRoutingRuntimeResult(
            HostManagedRoutingRuntimeStatus.POSTCONDITION_FAILED,
            final,
            (
                "host managed-routing final state is conflicting"
                if final.conflicts
                else "host managed-routing final state is not exact"
            ),
        )

    return HostManagedRoutingRuntimeResult(
        HostManagedRoutingRuntimeStatus.RECONCILED,
        final,
    )


def build_linux_host_managed_routing_contribution(
    config: Release1Config,
    domain_spec: ManagedNetworkDomainSpec,
    runner: NftScriptRunner,
) -> LinuxHostManagedRoutingContribution:
    desired = build_host_managed_routing_runtime_desired(config, domain_spec)
    return LinuxHostManagedRoutingContribution(
        routing_backend=LinuxHostManagedRoutingBackend(
            runner,
            NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION,
        ),
        desired=desired,
    )
