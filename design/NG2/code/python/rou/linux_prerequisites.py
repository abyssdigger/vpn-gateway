from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LinuxNamespacePrerequisites:
    """Technical namespace prerequisites required by the IPv4-only policy backend."""

    interface_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(set(self.interface_names)) != len(self.interface_names):
            raise ValueError("duplicate interface in namespace prerequisites")
        if any(not item for item in self.interface_names):
            raise ValueError("namespace prerequisite interface name must be non-empty")

    @property
    def expected_sysctls(self) -> tuple[tuple[str, str], ...]:
        expected: list[tuple[str, str]] = [
            ("net.ipv4.conf.all.rp_filter", "0"),
            ("net.ipv4.conf.default.rp_filter", "0"),
            ("net.ipv6.conf.all.forwarding", "0"),
            ("net.ipv6.conf.default.forwarding", "0"),
            ("net.ipv6.conf.default.disable_ipv6", "1"),
        ]
        for ifname in self.interface_names:
            expected.extend(
                (
                    (f"net.ipv4.conf.{ifname}.rp_filter", "0"),
                    (f"net.ipv6.conf.{ifname}.disable_ipv6", "1"),
                )
            )
        return tuple(expected)

    @property
    def observation_commands(
        self,
    ) -> tuple[tuple[str, tuple[str, ...]], ...]:
        commands: list[tuple[str, tuple[str, ...]]] = [
            (
                "net.ipv4.conf.all.rp_filter",
                ("sysctl", "-n", "net/ipv4/conf/all/rp_filter"),
            ),
            (
                "net.ipv4.conf.default.rp_filter",
                ("sysctl", "-n", "net/ipv4/conf/default/rp_filter"),
            ),
            (
                "net.ipv6.conf.all.forwarding",
                ("sysctl", "-n", "net/ipv6/conf/all/forwarding"),
            ),
            (
                "net.ipv6.conf.default.forwarding",
                ("sysctl", "-n", "net/ipv6/conf/default/forwarding"),
            ),
            (
                "net.ipv6.conf.default.disable_ipv6",
                ("sysctl", "-n", "net/ipv6/conf/default/disable_ipv6"),
            ),
        ]
        for ifname in self.interface_names:
            commands.extend(
                (
                    (
                        f"net.ipv4.conf.{ifname}.rp_filter",
                        (
                            "sysctl",
                            "-n",
                            f"net/ipv4/conf/{ifname}/rp_filter",
                        ),
                    ),
                    (
                        f"net.ipv6.conf.{ifname}.disable_ipv6",
                        (
                            "sysctl",
                            "-n",
                            f"net/ipv6/conf/{ifname}/disable_ipv6",
                        ),
                    ),
                )
            )
        return tuple(commands)

    @property
    def apply_commands(self) -> tuple[tuple[str, ...], ...]:
        commands: list[tuple[str, ...]] = [
            ("sysctl", "-q", "-w", "net/ipv4/conf/all/rp_filter=0"),
            ("sysctl", "-q", "-w", "net/ipv4/conf/default/rp_filter=0"),
            ("sysctl", "-q", "-w", "net/ipv6/conf/all/forwarding=0"),
            ("sysctl", "-q", "-w", "net/ipv6/conf/default/forwarding=0"),
            ("sysctl", "-q", "-w", "net/ipv6/conf/default/disable_ipv6=1"),
        ]
        for ifname in self.interface_names:
            commands.extend(
                (
                    (
                        "sysctl",
                        "-q",
                        "-w",
                        f"net/ipv4/conf/{ifname}/rp_filter=0",
                    ),
                    (
                        "sysctl",
                        "-q",
                        "-w",
                        f"net/ipv6/conf/{ifname}/disable_ipv6=1",
                    ),
                )
            )
        return tuple(commands)


def verify_linux_namespace_prerequisites(
    desired: LinuxNamespacePrerequisites,
    observed: tuple[tuple[str, str], ...],
) -> tuple[str, ...]:
    actual = dict(observed)
    errors = []
    for key, expected in desired.expected_sysctls:
        value = actual.get(key)
        if value != expected:
            errors.append(f"{key}={value!r}, expected {expected!r}")
    return tuple(errors)
