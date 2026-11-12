from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address
import json
import re

from .command_backend import NamespaceBackend
from .device_engine import DeviceBindingSnapshot
from .domain import (
    ActiveConfig,
    EnvelopeAction,
    EnvelopeDirection,
    EnvelopeProtocol,
    NatMode,
    PortRange,
    TrafficEnvelopeRule,
)
from .firewall_intent import FlowDirection, compile_new_flow_intents


FILTER_TABLE = "vpng_filter"
NAT_TABLE = "vpng_nat"
HOST_INTERFACE = "host0"


class NftPolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class NftTableDesiredState:
    family: str
    name: str
    definition: str
    canonical: str
    interface_identities: tuple[tuple[int, str], ...] = ()
    numeric_interface_refs: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class NftVerification:
    ok: bool
    actual: str
    expected: str


@dataclass(frozen=True)
class NftObservedState:
    canonical: str
    numeric_interface_refs: tuple[tuple[str, int], ...]



def _numeric_interface_refs_from_definition(
    definition: str,
) -> tuple[tuple[str, int], ...]:
    refs = [
        (match.group(1), int(match.group(2)))
        for match in re.finditer(
            r"\b(iif|oif)\s+([0-9]+)\b",
            definition,
        )
    ]
    return tuple(sorted(refs))


def _numeric_interface_refs_from_json(
    text: str,
) -> tuple[tuple[str, int], ...]:
    try:
        root = json.loads(text)
    except json.JSONDecodeError as exc:
        raise NftPolicyError(f"invalid nft JSON output: {exc}") from None

    items = root.get("nftables")
    if not isinstance(items, list):
        raise NftPolicyError("nft JSON root lacks nftables array")

    refs: list[tuple[str, int]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rule = item.get("rule")
        if not isinstance(rule, dict):
            continue
        exprs = rule.get("expr", ())
        if not isinstance(exprs, list):
            raise NftPolicyError("nft JSON rule expr is not an array")
        for expr in exprs:
            if not isinstance(expr, dict):
                continue
            match = expr.get("match")
            if not isinstance(match, dict) or match.get("op") != "==":
                continue
            left = match.get("left")
            if not isinstance(left, dict):
                continue
            meta = left.get("meta")
            if not isinstance(meta, dict):
                continue
            key = meta.get("key")
            if key not in {"iif", "oif"}:
                continue
            right = match.get("right")
            if type(right) is int:
                value = right
            elif isinstance(right, str) and right.isdecimal():
                value = int(right)
            else:
                raise NftPolicyError(
                    f"nft JSON {key} comparison is not numeric: {right!r}"
                )
            refs.append((key, value))

    return tuple(sorted(refs))


def observe_nft_numeric_interface_refs(
    desired: NftTableDesiredState,
    backend: NamespaceBackend,
) -> tuple[tuple[str, int], ...]:
    result = backend.run(
        (
            "nft",
            "-j",
            "-n",
            "list",
            "table",
            desired.family,
            desired.name,
        )
    )
    return _numeric_interface_refs_from_json(result.stdout)

def normalize_nft_list(
    text: str,
    interface_identities: tuple[tuple[int, str], ...] = (),
) -> str:
    """Normalize nft textual listing to generation-aware semantic form.

    nft list renders conntrack states as numeric bit values in numeric mode and may resolve
    an existing numeric iif/oif back to its current interface name. Desired policy is
    generation-specific, so current bound names are mapped back to their desired ifindex.
    A stale rule referring to a disappeared old ifindex remains numeric and therefore does
    not collapse onto a fresh same-name generation.
    """

    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        line = line.replace(
            "ct state established,related",
            "ct state 0x2,0x4",
        )
        line = line.replace(
            "ct state related,established",
            "ct state 0x2,0x4",
        )
        line = line.replace("ct state invalid", "ct state 0x1")
        line = line.replace("ct state new", "ct state 0x8")

        for ifindex, ifname in interface_identities:
            line = line.replace(
                f'iif "{ifname}"',
                f"iif {ifindex}",
            )
            line = line.replace(
                f'oif "{ifname}"',
                f"oif {ifindex}",
            )

        lines.append(line)

    return "\n".join(lines)


def _quote(value: str) -> str:
    if not value or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-" for ch in value):
        raise ValueError(f"unsupported nft interface/table token {value!r}")
    return f'"{value}"'


def _port_text(port_range: PortRange) -> str:
    if port_range.start == port_range.end:
        return str(port_range.start)
    return f"{port_range.start}-{port_range.end}"


def _envelope_rule_lines(
    chain: str,
    rule: TrafficEnvelopeRule,
) -> tuple[str, ...]:
    sources = rule.source_ports or (None,)
    destinations = rule.destination_ports or (None,)
    verdict = "return" if rule.action is EnvelopeAction.ALLOW else "drop"

    lines: list[str] = []
    for source_port in sources:
        for destination_port in destinations:
            parts: list[str] = []
            if rule.source is not None:
                parts.extend(["ip", "saddr", rule.source.with_prefixlen])
            if rule.destination is not None:
                parts.extend(["ip", "daddr", rule.destination.with_prefixlen])

            if rule.protocol is EnvelopeProtocol.TCP:
                if source_port is None and destination_port is None:
                    parts.extend(["ip", "protocol", "tcp"])
                if source_port is not None:
                    parts.extend(["tcp", "sport", _port_text(source_port)])
                if destination_port is not None:
                    parts.extend(["tcp", "dport", _port_text(destination_port)])
            elif rule.protocol is EnvelopeProtocol.UDP:
                if source_port is None and destination_port is None:
                    parts.extend(["ip", "protocol", "udp"])
                if source_port is not None:
                    parts.extend(["udp", "sport", _port_text(source_port)])
                if destination_port is not None:
                    parts.extend(["udp", "dport", _port_text(destination_port)])
            elif rule.protocol is EnvelopeProtocol.ICMP:
                parts.extend(["ip", "protocol", "icmp"])

            parts.append(verdict)
            lines.append(" ".join(parts))
    return tuple(lines)


def _envelope_chain_names(
    config: ActiveConfig,
) -> dict[str, tuple[str, str]]:
    names = [
        name
        for name in sorted(config.active_device_names)
        if config.devices[name].traffic_envelope is not None
    ]
    return {
        name: (f"env{index}_from", f"env{index}_to")
        for index, name in enumerate(names, start=1)
    }


def _publication_input_rules(
    config: ActiveConfig,
    local_address: IPv4Address | None,
) -> tuple[str, ...]:
    endpoints: set[tuple[str, int, int]] = set()
    for device_name in sorted(config.active_device_names):
        for publication in config.devices[device_name].publications:
            endpoints.add(
                (
                    publication.protocol.value,
                    publication.internal.start,
                    publication.internal.end,
                )
            )

    if endpoints and local_address is None:
        raise ValueError(
            "active publications require local publication address"
        )
    if local_address is None:
        return ()

    rules: list[str] = []
    for protocol, start, end in sorted(endpoints):
        port = str(start) if start == end else f"{start}-{end}"
        rules.append(
            f"ip daddr {local_address} iifname {_quote(HOST_INTERFACE)} "
            f"{protocol} dport {port} ct state new accept"
        )
    return tuple(rules)


def compile_nft_filter_state(
    config: ActiveConfig,
    bindings: DeviceBindingSnapshot,
    *,
    local_publication_address: IPv4Address | None = None,
) -> NftTableDesiredState:
    """Compile an ifindex-aware nftables filter table.

    Dynamic bound Device interfaces are matched by numeric ifindex. Static infrastructure
    interfaces host0/lo are matched by name because they are owned for the entire ROU
    instance lifetime.
    """

    chain_names = _envelope_chain_names(config)
    lines = [f"table ip {FILTER_TABLE} {{"]

    # Define regular Device chains before hook chains.
    for device_name in sorted(chain_names):
        envelope = config.devices[device_name].traffic_envelope
        if envelope is None:
            raise ValueError(
                f"missing traffic envelope for Device {device_name!r}"
            )
        from_chain, to_chain = chain_names[device_name]

        lines.append(f"chain {from_chain} {{")
        for rule in envelope.rules:
            if rule.direction is EnvelopeDirection.FROM_DEVICE:
                for text in _envelope_rule_lines(from_chain, rule):
                    lines.append(text)
        lines.append(
            "return"
            if envelope.default_action is EnvelopeAction.ALLOW
            else "drop"
        )
        lines.append("}")

        lines.append(f"chain {to_chain} {{")
        for rule in envelope.rules:
            if rule.direction is EnvelopeDirection.TO_DEVICE:
                for text in _envelope_rule_lines(to_chain, rule):
                    lines.append(text)
        lines.append(
            "return"
            if envelope.default_action is EnvelopeAction.ALLOW
            else "drop"
        )
        lines.append("}")

    lines.extend(
        [
            "chain input {",
            "type filter hook input priority 0; policy drop;",
            "ct state invalid drop",
            'iifname "lo" accept',
            f'iifname "{HOST_INTERFACE}" ct state established,related accept',
        ]
    )
    lines.extend(
        _publication_input_rules(
            config,
            local_publication_address,
        )
    )
    lines.append("}")

    lines.extend(
        [
            "chain forward {",
            "type filter hook forward priority 0; policy drop;",
            "ct state invalid drop",
        ]
    )

    by_device = bindings.by_device
    for device_name in sorted(chain_names):
        from_chain, to_chain = chain_names[device_name]
        for binding in by_device.get(device_name, ()):
            ifindex = binding.identity.ifindex
            lines.append(
                f'iifname "{HOST_INTERFACE}" oif {ifindex} jump {to_chain}'
            )
            lines.append(
                f'iif {ifindex} oifname "{HOST_INTERFACE}" jump {from_chain}'
            )

    for binding in bindings.bound:
        ifindex = binding.identity.ifindex
        lines.append(
            f'iifname "{HOST_INTERFACE}" oif {ifindex} '
            "ct state established,related accept"
        )
        lines.append(
            f'iif {ifindex} oifname "{HOST_INTERFACE}" '
            "ct state established,related accept"
        )

    for intent in compile_new_flow_intents(config):
        for binding in by_device.get(intent.device_name, ()):
            ifindex = binding.identity.ifindex
            verdict = intent.verdict.value
            prefix = intent.remote_prefix.with_prefixlen
            if intent.direction is FlowDirection.HOST_TO_DEVICE:
                lines.append(
                    f"ip daddr {prefix} "
                    f'iifname "{HOST_INTERFACE}" oif {ifindex} '
                    f"ct state new {verdict}"
                )
            else:
                lines.append(
                    f"ip saddr {prefix} iif {ifindex} "
                    f'oifname "{HOST_INTERFACE}" ct state new {verdict}'
                )

    lines.append("}")

    lines.extend(
        [
            "chain output {",
            "type filter hook output priority 0; policy drop;",
            "ct state invalid drop",
            'oifname "lo" accept',
            f'oifname "{HOST_INTERFACE}" ct state established,related accept',
            f'oifname "{HOST_INTERFACE}" ct state new accept',
            "}",
            "}",
            "",
        ]
    )

    definition = "\n".join(lines)
    identities = tuple(
        sorted(
            {
                (item.identity.ifindex, item.identity.ifname)
                for item in bindings.bound
            }
        )
    )
    return NftTableDesiredState(
        family="ip",
        name=FILTER_TABLE,
        definition=definition,
        canonical=normalize_nft_list(definition, identities),
        interface_identities=identities,
        numeric_interface_refs=_numeric_interface_refs_from_definition(
            definition
        ),
    )


def compile_nft_nat_state(
    config: ActiveConfig,
    bindings: DeviceBindingSnapshot,
) -> NftTableDesiredState:
    lines = [
        f"table ip {NAT_TABLE} {{",
        "chain postrouting {",
        "type nat hook postrouting priority 100; policy accept;",
    ]

    prefixes_by_device: dict[str, set] = {}
    for profile in config.profiles.values():
        if not profile.enabled:
            continue
        for device_name in profile.device_order:
            device = config.devices[device_name]
            if device.enabled:
                prefixes_by_device.setdefault(device_name, set()).update(
                    profile.destinations
                )

    for device_name in sorted(config.active_device_names):
        device = config.devices[device_name]
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
            for prefix in prefixes:
                lines.append(
                    f"ip daddr {prefix.with_prefixlen} "
                    f"oif {binding.identity.ifindex} masquerade"
                )

    lines.extend(["}", "}", ""])
    definition = "\n".join(lines)
    identities = tuple(
        sorted(
            {
                (item.identity.ifindex, item.identity.ifname)
                for item in bindings.bound
            }
        )
    )
    return NftTableDesiredState(
        family="ip",
        name=NAT_TABLE,
        definition=definition,
        canonical=normalize_nft_list(definition, identities),
        interface_identities=identities,
        numeric_interface_refs=_numeric_interface_refs_from_definition(
            definition
        ),
    )


def _table_exists(
    desired: NftTableDesiredState,
    backend: NamespaceBackend,
) -> bool:
    result = backend.run(
        ("nft", "list", "table", desired.family, desired.name),
        check=False,
    )
    return result.returncode == 0


def apply_nft_table(
    desired: NftTableDesiredState,
    backend: NamespaceBackend,
) -> None:
    """Atomically replace one owned nftables table."""

    if _table_exists(desired, backend):
        script = (
            f"delete table {desired.family} {desired.name}\n"
            + desired.definition
        )
    else:
        script = desired.definition
    backend.run(("nft", "-f", "-"), input_text=script)


def observe_nft_table(
    desired: NftTableDesiredState,
    backend: NamespaceBackend,
) -> str:
    result = backend.run(
        (
            "nft",
            "-n",
            "-n",
            "list",
            "table",
            desired.family,
            desired.name,
        )
    )
    return normalize_nft_list(
        result.stdout,
        desired.interface_identities,
    )


def observe_nft_state(
    desired: NftTableDesiredState,
    backend: NamespaceBackend,
) -> NftObservedState | None:
    """Observe one owned nft table through the production verification boundary.

    Textual canonicalization verifies complete policy/order semantics. JSON observation
    independently preserves numeric iif/oif generation identity even when the text renderer
    resolves a live ifindex back to an interface name.

    The two reads are intentionally encapsulated here. The runtime serializes its own nft
    mutations; foreign concurrent mutation can only make this observation stale, never make
    an unverified numeric generation satisfy the exact ref multiset.
    """

    probe = backend.run(
        (
            "nft",
            "-j",
            "-n",
            "list",
            "table",
            desired.family,
            desired.name,
        ),
        check=False,
    )
    if probe.returncode != 0:
        stderr = probe.stderr.lower()
        if (
            "no such file or directory" in stderr
            or "does not exist" in stderr
        ):
            return None
        raise NftPolicyError(
            f"cannot observe nft table {desired.family} {desired.name}: "
            f"returncode={probe.returncode} stderr={probe.stderr.strip()!r}"
        )

    refs = _numeric_interface_refs_from_json(probe.stdout)
    return NftObservedState(
        canonical=observe_nft_table(desired, backend),
        numeric_interface_refs=refs,
    )


def verify_nft_observation(
    desired: NftTableDesiredState,
    observed: NftObservedState | None,
) -> NftVerification:
    if observed is None:
        return NftVerification(
            ok=False,
            actual="<absent>",
            expected=(
                desired.canonical
                + "\n# numeric-interface-refs="
                + repr(desired.numeric_interface_refs)
            ),
        )

    text_ok = observed.canonical == desired.canonical
    refs_ok = (
        observed.numeric_interface_refs
        == desired.numeric_interface_refs
    )
    actual = (
        observed.canonical
        + "\n# numeric-interface-refs="
        + repr(observed.numeric_interface_refs)
    )
    expected = (
        desired.canonical
        + "\n# numeric-interface-refs="
        + repr(desired.numeric_interface_refs)
    )
    return NftVerification(
        ok=text_ok and refs_ok,
        actual=actual,
        expected=expected,
    )


def verify_nft_table(
    desired: NftTableDesiredState,
    backend: NamespaceBackend,
) -> NftVerification:
    return verify_nft_observation(
        desired,
        observe_nft_state(desired, backend),
    )
