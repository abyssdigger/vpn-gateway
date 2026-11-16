from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol
import time

from .linux_adapter import LinuxNetworkBackend, LinuxNetworkRulesAdapter
from .linux_local_process import LinuxLocalProcessConfig
from .linux_probe_execution import (
    ProbeExecutionDiagnosticPublisher,
    ProbeSendDriver,
)
from .payload_traffic_manager import PayloadTrafficStatePublisher
from .runtime_assembly import (
    LinuxNetworkPolicyRuntime,
    build_linux_network_policy_runtime,
)
from .linux_instance import (
    LinuxInstanceSpec,
    ensure_linux_instance,
)
from .linux_driver import (
    LinuxCommandRunner,
    LinuxDriverResult,
    LinuxNetworkExecutor,
    NetworkNamespaceLinuxRunner,
    SubprocessLinuxRunner,
)


class LinuxRuntimeBootstrapBackend(LinuxNetworkBackend, Protocol):
    def close_forwarding_verified(self) -> LinuxDriverResult:
        ...


@dataclass(frozen=True)
class LinuxRuntimeBootstrapResult:
    success: bool
    adapter: LinuxNetworkRulesAdapter | None = None
    diagnostic: str | None = None

    def __post_init__(self) -> None:
        if self.success and self.adapter is None:
            raise ValueError("successful bootstrap requires an Adapter")
        if not self.success and self.adapter is not None:
            raise ValueError("failed bootstrap must not expose an Adapter")


def bootstrap_linux_network_rules_adapter(
    backend: LinuxRuntimeBootstrapBackend,
    *,
    local_interface: str,
    local_process: LinuxLocalProcessConfig | None = None,
) -> LinuxRuntimeBootstrapResult:
    """Return an Adapter only after freshly verified forwarding closure."""

    closed = backend.close_forwarding_verified()
    if not closed.success:
        return LinuxRuntimeBootstrapResult(
            False,
            diagnostic=closed.diagnostic,
        )

    return LinuxRuntimeBootstrapResult(
        True,
        adapter=LinuxNetworkRulesAdapter(
            backend,
            local_interface=local_interface,
            local_process=local_process,
        ),
    )


def bootstrap_linux_network_rules_adapter_in_namespace(
    namespace: str,
    *,
    local_interface: str,
    host_runner: LinuxCommandRunner | None = None,
    local_process: LinuxLocalProcessConfig | None = None,
) -> LinuxRuntimeBootstrapResult:
    """Bootstrap the Adapter inside one pre-existing named network namespace."""

    namespace_runner = NetworkNamespaceLinuxRunner(
        (
            host_runner
            if host_runner is not None
            else SubprocessLinuxRunner()
        ),
        namespace,
    )
    executor = LinuxNetworkExecutor(namespace_runner)
    return bootstrap_linux_network_rules_adapter(
        executor,
        local_interface=local_interface,
        local_process=local_process,
    )


def bootstrap_linux_network_rules_adapter_for_instance(
    spec: LinuxInstanceSpec,
    *,
    host_runner: LinuxCommandRunner | None = None,
    local_process: LinuxLocalProcessConfig | None = None,
) -> LinuxRuntimeBootstrapResult:
    """Ensure fail-closed instance infrastructure, then publish its Adapter."""

    runner = (
        host_runner
        if host_runner is not None
        else SubprocessLinuxRunner()
    )
    try:
        ensure_linux_instance(spec, runner)
    except Exception as exc:
        return LinuxRuntimeBootstrapResult(
            False,
            diagnostic=f"instance infrastructure is not ready: {exc}",
        )

    return bootstrap_linux_network_rules_adapter_in_namespace(
        spec.namespace,
        local_interface="host0",
        host_runner=runner,
        local_process=local_process,
    )


@dataclass(frozen=True)
class LinuxNetworkPolicyRuntimeBootstrapResult:
    success: bool
    runtime: LinuxNetworkPolicyRuntime | None = None
    diagnostic: str | None = None

    def __post_init__(self) -> None:
        if self.success and self.runtime is None:
            raise ValueError(
                "successful network-policy bootstrap requires runtime"
            )
        if not self.success and self.runtime is not None:
            raise ValueError(
                "failed network-policy bootstrap must not expose runtime"
            )


def _network_policy_runtime_from_bootstrap(
    bootstrap: LinuxRuntimeBootstrapResult,
    *,
    payload_publisher: PayloadTrafficStatePublisher,
    probe_driver: ProbeSendDriver,
    diagnostic_publisher: ProbeExecutionDiagnosticPublisher,
    timeout_seconds: int,
    clock: Callable[[], float],
) -> LinuxNetworkPolicyRuntimeBootstrapResult:
    if not bootstrap.success:
        return LinuxNetworkPolicyRuntimeBootstrapResult(
            False,
            diagnostic=bootstrap.diagnostic,
        )

    assert bootstrap.adapter is not None
    return LinuxNetworkPolicyRuntimeBootstrapResult(
        True,
        runtime=build_linux_network_policy_runtime(
            bootstrap.adapter,
            payload_publisher,
            probe_driver,
            diagnostic_publisher,
            timeout_seconds=timeout_seconds,
            clock=clock,
        ),
    )


def bootstrap_linux_network_policy_runtime(
    backend: LinuxRuntimeBootstrapBackend,
    *,
    local_interface: str,
    payload_publisher: PayloadTrafficStatePublisher,
    probe_driver: ProbeSendDriver,
    diagnostic_publisher: ProbeExecutionDiagnosticPublisher,
    timeout_seconds: int,
    local_process: LinuxLocalProcessConfig | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> LinuxNetworkPolicyRuntimeBootstrapResult:
    """Expose network-policy runtime only after verified protective bootstrap."""

    return _network_policy_runtime_from_bootstrap(
        bootstrap_linux_network_rules_adapter(
            backend,
            local_interface=local_interface,
            local_process=local_process,
        ),
        payload_publisher=payload_publisher,
        probe_driver=probe_driver,
        diagnostic_publisher=diagnostic_publisher,
        timeout_seconds=timeout_seconds,
        clock=clock,
    )


def bootstrap_linux_network_policy_runtime_for_instance(
    spec: LinuxInstanceSpec,
    *,
    payload_publisher: PayloadTrafficStatePublisher,
    probe_driver: ProbeSendDriver,
    diagnostic_publisher: ProbeExecutionDiagnosticPublisher,
    timeout_seconds: int,
    host_runner: LinuxCommandRunner | None = None,
    local_process: LinuxLocalProcessConfig | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> LinuxNetworkPolicyRuntimeBootstrapResult:
    """Ensure one ROU instance, re-close it, then expose the network-policy runtime."""

    return _network_policy_runtime_from_bootstrap(
        bootstrap_linux_network_rules_adapter_for_instance(
            spec,
            host_runner=host_runner,
            local_process=local_process,
        ),
        payload_publisher=payload_publisher,
        probe_driver=probe_driver,
        diagnostic_publisher=diagnostic_publisher,
        timeout_seconds=timeout_seconds,
        clock=clock,
    )
