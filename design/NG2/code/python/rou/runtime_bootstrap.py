from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .linux_adapter import LinuxNetworkBackend, LinuxNetworkRulesAdapter
from .linux_driver import (
    LinuxCommandRunner,
    LinuxDriverResult,
    LinuxNetworkDriver,
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
        ),
    )


def bootstrap_linux_network_rules_adapter_in_namespace(
    namespace: str,
    *,
    local_interface: str,
    host_runner: LinuxCommandRunner | None = None,
) -> LinuxRuntimeBootstrapResult:
    """Bootstrap the Adapter inside one pre-existing named network namespace."""

    namespace_runner = NetworkNamespaceLinuxRunner(
        host_runner or SubprocessLinuxRunner(),
        namespace,
    )
    driver = LinuxNetworkDriver(namespace_runner)
    return bootstrap_linux_network_rules_adapter(
        driver,
        local_interface=local_interface,
    )
