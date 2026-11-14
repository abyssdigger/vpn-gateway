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
    def _entries(self) -> tuple[tuple[str, str, str], ...]:
        entries: list[tuple[str, str, str]] = [
            (
                "net.ipv4.conf.all.rp_filter",
                "net/ipv4/conf/all/rp_filter",
                "0",
            ),
            (
                "net.ipv4.conf.default.rp_filter",
                "net/ipv4/conf/default/rp_filter",
                "0",
            ),
            (
                "net.ipv6.conf.all.forwarding",
                "net/ipv6/conf/all/forwarding",
                "0",
            ),
            (
                "net.ipv6.conf.default.forwarding",
                "net/ipv6/conf/default/forwarding",
                "0",
            ),
            (
                "net.ipv6.conf.default.disable_ipv6",
                "net/ipv6/conf/default/disable_ipv6",
                "1",
            ),
        ]
        for ifname in self.interface_names:
            entries.extend(
                (
                    (
                        f"net.ipv4.conf.{ifname}.rp_filter",
                        f"net/ipv4/conf/{ifname}/rp_filter",
                        "0",
                    ),
                    (
                        f"net.ipv6.conf.{ifname}.disable_ipv6",
                        f"net/ipv6/conf/{ifname}/disable_ipv6",
                        "1",
                    ),
                )
            )
        return tuple(entries)

    @property
    def expected_sysctls(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (key, expected)
            for key, _path, expected in self._entries
        )

    @property
    def observation_commands(
        self,
    ) -> tuple[tuple[str, tuple[str, ...]], ...]:
        return tuple(
            (key, ("sysctl", "-n", path))
            for key, path, _expected in self._entries
        )

    @property
    def apply_commands(self) -> tuple[tuple[str, ...], ...]:
        return tuple(
            ("sysctl", "-q", "-w", f"{path}={expected}")
            for _key, path, expected in self._entries
        )


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
