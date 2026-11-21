from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from .forwarding_gate import ForwardingGateState


class LinuxForwardingGateError(RuntimeError):
    pass


class ForwardingGateCommandRunner(Protocol):
    def run(self, argv: Sequence[str]) -> str:
        """Run one command or raise; return stdout text."""


@dataclass(slots=True)
class LinuxForwardingGateDriver:
    runner: ForwardingGateCommandRunner
    namespace: str

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not self.namespace:
            raise ValueError("namespace must be a non-empty string")

    def observe_forwarding_gate(self) -> ForwardingGateState:
        stdout = self.runner.run(
            (
                "ip",
                "netns",
                "exec",
                self.namespace,
                "sysctl",
                "-n",
                "net.ipv4.ip_forward",
            )
        )
        value = stdout.strip()
        if value == "0":
            return ForwardingGateState.DISABLED
        if value == "1":
            return ForwardingGateState.ENABLED
        raise LinuxForwardingGateError(
            f"unexpected net.ipv4.ip_forward representation {value!r}"
        )

    def set_forwarding_gate(
        self,
        desired: ForwardingGateState,
    ) -> None:
        if not isinstance(desired, ForwardingGateState):
            raise ValueError("desired must be ForwardingGateState")
        value = 1 if desired is ForwardingGateState.ENABLED else 0
        self.runner.run(
            (
                "ip",
                "netns",
                "exec",
                self.namespace,
                "sysctl",
                "-w",
                f"net.ipv4.ip_forward={value}",
            )
        )


# Transitional alias; current code uses the Driver role name.
LinuxForwardingGateBackend = LinuxForwardingGateDriver
