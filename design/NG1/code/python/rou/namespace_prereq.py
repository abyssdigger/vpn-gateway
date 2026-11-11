from __future__ import annotations

from dataclasses import dataclass

from .command_backend import NamespaceBackend
from .device_engine import DeviceBindingSnapshot
from .environment import EnvironmentSnapshot


HOST_INTERFACE = "host0"


@dataclass(frozen=True)
class NamespacePrerequisiteVerification:
    ok: bool
    errors: tuple[str, ...]


def _payload_ifnames(bindings: DeviceBindingSnapshot) -> tuple[str, ...]:
    names = {HOST_INTERFACE}
    names.update(item.identity.ifname for item in bindings.bound)
    return tuple(sorted(names))


def prerequisite_commands(
    bindings: DeviceBindingSnapshot,
) -> tuple[tuple[str, ...], ...]:
    """Return idempotent namespace-sysctl commands for current payload interfaces."""

    commands: list[tuple[str, ...]] = [
        ("sysctl", "-q", "-w", "net/ipv4/conf/all/rp_filter=0"),
        ("sysctl", "-q", "-w", "net/ipv4/conf/default/rp_filter=0"),
        ("sysctl", "-q", "-w", "net/ipv6/conf/all/forwarding=0"),
        ("sysctl", "-q", "-w", "net/ipv6/conf/default/forwarding=0"),
        ("sysctl", "-q", "-w", "net/ipv6/conf/default/disable_ipv6=1"),
    ]

    for ifname in _payload_ifnames(bindings):
        commands.append(
            ("sysctl", "-q", "-w", f"net/ipv4/conf/{ifname}/rp_filter=0")
        )
        commands.append(
            ("sysctl", "-q", "-w", f"net/ipv6/conf/{ifname}/disable_ipv6=1")
        )

    return tuple(commands)


def apply_namespace_prerequisites(
    bindings: DeviceBindingSnapshot,
    backend: NamespaceBackend,
) -> None:
    """Apply prerequisite sysctls while forwarding is expected to remain closed."""

    for command in prerequisite_commands(bindings):
        backend.run(command)


def verify_namespace_prerequisites(
    snapshot: EnvironmentSnapshot,
    bindings: DeviceBindingSnapshot,
    *,
    forwarding: bool,
) -> NamespacePrerequisiteVerification:
    """Verify the exact safety prerequisites required before admitting payload."""

    values = snapshot.sysctl_map
    errors: list[str] = []

    expected_global = {
        "net.ipv4.ip_forward": "1" if forwarding else "0",
        "net.ipv4.conf.all.rp_filter": "0",
        "net.ipv4.conf.default.rp_filter": "0",
        "net.ipv6.conf.all.forwarding": "0",
        "net.ipv6.conf.default.forwarding": "0",
        "net.ipv6.conf.default.disable_ipv6": "1",
    }

    for key, expected in expected_global.items():
        actual = values.get(key)
        if actual != expected:
            errors.append(f"{key}={actual!r}, expected {expected!r}")

    for ifname in _payload_ifnames(bindings):
        expected_per_if = {
            f"net.ipv4.conf.{ifname}.rp_filter": "0",
            f"net.ipv6.conf.{ifname}.disable_ipv6": "1",
        }
        for key, expected in expected_per_if.items():
            actual = values.get(key)
            if actual != expected:
                errors.append(f"{key}={actual!r}, expected {expected!r}")

    return NamespacePrerequisiteVerification(
        ok=not errors,
        errors=tuple(errors),
    )
