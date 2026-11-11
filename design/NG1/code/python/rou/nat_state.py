from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .device_engine import DeviceBindingSnapshot
from .domain import ActiveConfig, NatMode
from .firewall_state import normalize_iptables_save


class NatPolicyBlocked(RuntimeError):
    """Legacy design-gate error retained for explicit historical tests."""


@dataclass(frozen=True)
class NatDesiredState:
    restore_text: str
    canonical_save: str


class NatProvider(Protocol):
    def compile(
        self,
        config: ActiveConfig,
        bindings: DeviceBindingSnapshot,
    ) -> NatDesiredState:
        ...


def _base_lines() -> list[str]:
    return [
        "*nat",
        ":PREROUTING ACCEPT [0:0]",
        ":INPUT ACCEPT [0:0]",
        ":OUTPUT ACCEPT [0:0]",
        ":POSTROUTING ACCEPT [0:0]",
    ]


def _finish(lines: list[str]) -> NatDesiredState:
    lines.extend(["COMMIT", ""])
    text = "\n".join(lines)
    return NatDesiredState(text, normalize_iptables_save(text))


class ConfigNatProvider:
    """Compile schema-v1 Device-scoped NAT policy."""

    def compile(
        self,
        config: ActiveConfig,
        bindings: DeviceBindingSnapshot,
    ) -> NatDesiredState:
        lines = _base_lines()

        prefixes_by_device: dict[str, set] = {}
        for profile in config.profiles.values():
            if not profile.enabled:
                continue
            for device_name in profile.device_order:
                device = config.devices[device_name]
                if not device.enabled:
                    continue
                prefixes_by_device.setdefault(device_name, set()).update(
                    profile.destinations
                )

        for device_name in sorted(config.active_device_names):
            device = config.devices[device_name]
            if device.nat is None:
                raise ValueError(
                    f"enabled Device {device_name!r} has no explicit NAT mode"
                )
            if device.nat is NatMode.NONE:
                continue
            if device.nat is not NatMode.MASQUERADE:
                raise ValueError(
                    f"unsupported NAT mode {device.nat!r} on Device {device_name!r}"
                )

            prefixes = sorted(
                prefixes_by_device.get(device_name, set()),
                key=lambda network: (
                    -network.prefixlen,
                    int(network.network_address),
                ),
            )
            for binding in bindings.by_device.get(device_name, ()):
                ifname = binding.identity.ifname
                for prefix in prefixes:
                    lines.append(
                        f"-A POSTROUTING -o {ifname} "
                        f"-d {prefix.with_prefixlen} "
                        "-m addrtype ! --dst-type LOCAL -j MASQUERADE"
                    )

        return _finish(lines)


class UnresolvedNatProvider:
    """Deprecated Draft-4 gate retained only for historical regression evidence."""

    def compile(
        self,
        config: ActiveConfig,
        bindings: DeviceBindingSnapshot,
    ) -> NatDesiredState:
        raise NatPolicyBlocked(
            "Draft 4 production payload NAT policy was unresolved; "
            "Draft 5 uses ConfigNatProvider"
        )


class ExplicitNoNatProvider:
    """Explicit normalized no-NAT policy for narrow integration tests."""

    def compile(
        self,
        config: ActiveConfig,
        bindings: DeviceBindingSnapshot,
    ) -> NatDesiredState:
        return _finish(_base_lines())


class ExperimentalMasqueradeAllBoundProvider:
    """v0-compatible historical lab provider; not production schema semantics."""

    def compile(
        self,
        config: ActiveConfig,
        bindings: DeviceBindingSnapshot,
    ) -> NatDesiredState:
        lines = _base_lines()
        seen: set[str] = set()
        for binding in bindings.bound:
            ifname = binding.identity.ifname
            if ifname in seen:
                continue
            seen.add(ifname)
            lines.append(
                f"-A POSTROUTING -o {ifname} "
                "-m addrtype ! --dst-type LOCAL -j MASQUERADE"
            )
        return _finish(lines)
