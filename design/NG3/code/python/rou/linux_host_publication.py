"""Strict host-namespace nft Driver/Executor for server publication."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Address
import json
from typing import Sequence

from .host_publication_policy import (
    HostPublicationDesiredState,
    HostPublicationRuleSpec,
    HostPublicationSelectorKind,
)
from .linux_nft_scaffold import NftScriptRunner
from .local_publication_policy import PublicationProtocol


HOST_PUBLICATION_TABLE = "vpn_gate_publication"
HOST_PUBLICATION_CHAIN = "publication_prerouting"
HOST_PUBLICATION_TABLE_COMMENT = "vpn-gate:ng3:host-publication-owner-v1"
HOST_PUBLICATION_CHAIN_COMMENT = "vpn-gate:ng3:host-publication-prerouting-v1"
HOST_PUBLICATION_RULE_COMMENT = "vpn-gate:ng3:host-publication-rule-v1"


@dataclass(frozen=True, slots=True)
class HostPublicationPhysicalObservation:
    table_present: bool
    rules: tuple[HostPublicationRuleSpec, ...]
    conflicts: tuple[str, ...]
    forwarding_enabled: bool

    @property
    def conflict_free(self) -> bool:
        return not self.conflicts


class HostPublicationConvergenceStatus(str, Enum):
    CONFIRMED = "confirmed"
    APPLIED = "applied"
    UNREADY = "unready"
    CONFLICT = "conflict"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class HostPublicationConvergenceResult:
    status: HostPublicationConvergenceStatus
    initial: HostPublicationPhysicalObservation | None
    final: HostPublicationPhysicalObservation | None
    mutation_attempted: bool
    diagnostic: str | None = None

    @property
    def confirmed(self) -> bool:
        return (
            self.status
            in {
                HostPublicationConvergenceStatus.CONFIRMED,
                HostPublicationConvergenceStatus.APPLIED,
            }
            and self.final is not None
            and self.final.conflict_free
        )


@dataclass(slots=True)
class LinuxHostPublicationBackend:
    runner: NftScriptRunner
    network_namespace: str | None = None

    def __post_init__(self) -> None:
        if self.network_namespace is not None and (
            not isinstance(self.network_namespace, str)
            or not self.network_namespace
        ):
            raise ValueError("network_namespace must be non-empty text or None")

    def observe(self) -> HostPublicationPhysicalObservation:
        forwarding = self._forwarding()
        raw = self.runner.run(self._cmd("nft", "-j", "-y", "list", "ruleset"))
        return _parse_observation(raw, forwarding)

    def replace(self, desired: HostPublicationDesiredState) -> None:
        if not isinstance(desired, HostPublicationDesiredState):
            raise ValueError("desired must be HostPublicationDesiredState")
        current = self.observe()
        if current.conflicts:
            raise RuntimeError(
                "host publication owner conflict: " + "; ".join(current.conflicts)
            )

        lines: list[str] = []
        if current.table_present:
            lines.append(f"delete table ip {HOST_PUBLICATION_TABLE}")
        if desired.rules:
            lines.extend(_render_table(desired))
        if not lines:
            return
        self.runner.run_script(
            self._cmd("nft", "-f", "-"),
            "\n".join(lines) + "\n",
        )

    def _forwarding(self) -> bool:
        value = self.runner.run(
            self._cmd("sysctl", "-n", "net.ipv4.ip_forward")
        ).strip()
        if value == "1":
            return True
        if value == "0":
            return False
        raise RuntimeError(
            f"unexpected host net.ipv4.ip_forward representation {value!r}"
        )

    def _cmd(self, *args: str) -> tuple[str, ...]:
        if self.network_namespace is None:
            return tuple(args)
        return ("ip", "netns", "exec", self.network_namespace, *args)


def converge_host_publication_once(
    backend: LinuxHostPublicationBackend,
    desired: HostPublicationDesiredState,
) -> HostPublicationConvergenceResult:
    if not isinstance(backend, LinuxHostPublicationBackend):
        raise ValueError("backend must be LinuxHostPublicationBackend")
    if not isinstance(desired, HostPublicationDesiredState):
        raise ValueError("desired must be HostPublicationDesiredState")

    try:
        initial = backend.observe()
    except Exception as exc:
        return HostPublicationConvergenceResult(
            status=HostPublicationConvergenceStatus.FAILED,
            initial=None,
            final=None,
            mutation_attempted=False,
            diagnostic=f"host publication observation failed: {exc}",
        )

    if initial.conflicts:
        return HostPublicationConvergenceResult(
            status=HostPublicationConvergenceStatus.CONFLICT,
            initial=initial,
            final=initial,
            mutation_attempted=False,
            diagnostic="; ".join(initial.conflicts),
        )

    exact = _matches(initial, desired)
    if exact:
        status = (
            HostPublicationConvergenceStatus.CONFIRMED
            if not desired.rules or initial.forwarding_enabled
            else HostPublicationConvergenceStatus.UNREADY
        )
        diagnostic = (
            None
            if status is HostPublicationConvergenceStatus.CONFIRMED
            else "host IPv4 forwarding prerequisite is disabled"
        )
        return HostPublicationConvergenceResult(
            status=status,
            initial=initial,
            final=initial,
            mutation_attempted=False,
            diagnostic=diagnostic,
        )

    # Removing all desired publication must remain possible even if forwarding
    # is unavailable. Adding/changing positive host mappings requires the
    # external forwarding prerequisite to be present first.
    if desired.rules and not initial.forwarding_enabled:
        return HostPublicationConvergenceResult(
            status=HostPublicationConvergenceStatus.UNREADY,
            initial=initial,
            final=initial,
            mutation_attempted=False,
            diagnostic="host IPv4 forwarding prerequisite is disabled",
        )

    try:
        backend.replace(desired)
        final = backend.observe()
    except Exception as exc:
        return HostPublicationConvergenceResult(
            status=HostPublicationConvergenceStatus.FAILED,
            initial=initial,
            final=None,
            mutation_attempted=True,
            diagnostic=f"host publication mutation/verification failed: {exc}",
        )

    if final.conflicts:
        return HostPublicationConvergenceResult(
            status=HostPublicationConvergenceStatus.CONFLICT,
            initial=initial,
            final=final,
            mutation_attempted=True,
            diagnostic="; ".join(final.conflicts),
        )
    if not _matches(final, desired):
        return HostPublicationConvergenceResult(
            status=HostPublicationConvergenceStatus.FAILED,
            initial=initial,
            final=final,
            mutation_attempted=True,
            diagnostic="host publication fresh postcondition does not match desired state",
        )
    if desired.rules and not final.forwarding_enabled:
        return HostPublicationConvergenceResult(
            status=HostPublicationConvergenceStatus.UNREADY,
            initial=initial,
            final=final,
            mutation_attempted=True,
            diagnostic="host IPv4 forwarding prerequisite became disabled",
        )
    return HostPublicationConvergenceResult(
        status=HostPublicationConvergenceStatus.APPLIED,
        initial=initial,
        final=final,
        mutation_attempted=True,
    )


def _matches(
    observed: HostPublicationPhysicalObservation,
    desired: HostPublicationDesiredState,
) -> bool:
    return (
        observed.conflict_free
        and observed.table_present == bool(desired.rules)
        and observed.rules == desired.rules
    )


def _render_table(desired: HostPublicationDesiredState) -> list[str]:
    lines = [
        f"add table ip {HOST_PUBLICATION_TABLE} {{ comment \"{HOST_PUBLICATION_TABLE_COMMENT}\"; }}",
        (
            f"add chain ip {HOST_PUBLICATION_TABLE} {HOST_PUBLICATION_CHAIN} "
            "{ type nat hook prerouting priority dstnat; policy accept; "
            f"comment \"{HOST_PUBLICATION_CHAIN_COMMENT}\"; }}"
        ),
    ]
    lines.extend(_render_rule(rule) for rule in desired.rules)
    return lines


def _render_rule(rule: HostPublicationRuleSpec) -> str:
    selector: list[str] = ["fib daddr type local"]
    if rule.selector_kind is HostPublicationSelectorKind.IPV4:
        selector.append(f"ip daddr {rule.selector_value}")
    elif rule.selector_kind is HostPublicationSelectorKind.INTERFACE:
        if not isinstance(rule.selector_value, str):
            raise ValueError("interface selector value must be text")
        safe = rule.selector_value.replace("\\", "\\\\").replace('"', '\\"')
        selector.append(f'iifname "{safe}"')
    elif rule.selector_kind is not HostPublicationSelectorKind.ANY:
        raise ValueError("unsupported host publication selector")
    selector.extend(
        (
            f"{rule.protocol.value} dport {rule.host_port}",
            f"dnat to {rule.internal_address}:{rule.internal_port}",
            f'comment "{HOST_PUBLICATION_RULE_COMMENT}"',
        )
    )
    return (
        f"add rule ip {HOST_PUBLICATION_TABLE} {HOST_PUBLICATION_CHAIN} "
        + " ".join(selector)
    )


def _parse_observation(
    raw: str,
    forwarding_enabled: bool,
) -> HostPublicationPhysicalObservation:
    try:
        root = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError("invalid host nft JSON") from None
    rows = root.get("nftables") if isinstance(root, dict) else None
    if not isinstance(rows, list):
        raise ValueError("host nft JSON must contain nftables array")

    table_rows: list[dict] = []
    chain_rows: list[dict] = []
    rule_rows: list[dict] = []
    conflicts: list[str] = []

    for row in rows:
        if not isinstance(row, dict) or len(row) != 1:
            continue
        kind, payload = next(iter(row.items()))
        if kind == "metainfo" or not isinstance(payload, dict):
            continue
        if payload.get("family") != "ip":
            continue
        table = payload.get("table")
        name = payload.get("name")
        belongs = (
            (kind == "table" and name == HOST_PUBLICATION_TABLE)
            or table == HOST_PUBLICATION_TABLE
        )
        if not belongs:
            continue
        if kind == "table":
            table_rows.append(payload)
        elif kind == "chain":
            chain_rows.append(payload)
        elif kind == "rule":
            rule_rows.append(payload)
        else:
            conflicts.append(
                f"unsupported object {kind!r} in host publication table"
            )

    if not table_rows and not chain_rows and not rule_rows and not conflicts:
        return HostPublicationPhysicalObservation(
            table_present=False,
            rules=(),
            conflicts=(),
            forwarding_enabled=forwarding_enabled,
        )

    if len(table_rows) != 1:
        conflicts.append("host publication table object is missing or duplicated")
    elif table_rows[0].get("comment") != HOST_PUBLICATION_TABLE_COMMENT:
        conflicts.append("host publication table owner comment mismatch")

    if len(chain_rows) != 1:
        conflicts.append("host publication prerouting chain is missing or duplicated")
    else:
        chain = chain_rows[0]
        if chain.get("name") != HOST_PUBLICATION_CHAIN:
            conflicts.append("unexpected chain in host publication table")
        if chain.get("type") != "nat" or chain.get("hook") != "prerouting":
            conflicts.append("host publication chain type/hook mismatch")
        if chain.get("prio") != -100:
            conflicts.append("host publication chain priority mismatch")
        if chain.get("policy") != "accept":
            conflicts.append("host publication chain policy mismatch")
        if chain.get("comment") != HOST_PUBLICATION_CHAIN_COMMENT:
            conflicts.append("host publication chain owner comment mismatch")

    decoded: list[HostPublicationRuleSpec] = []
    for payload in rule_rows:
        if payload.get("chain") != HOST_PUBLICATION_CHAIN:
            conflicts.append("host publication rule is on unexpected chain")
            continue
        if payload.get("comment") != HOST_PUBLICATION_RULE_COMMENT:
            conflicts.append("foreign rule exists in owned host publication table")
            continue
        try:
            decoded.append(_decode_rule(payload))
        except ValueError as exc:
            conflicts.append(str(exc))

    if len(set(decoded)) != len(decoded):
        conflicts.append("duplicate physical host publication rule")

    try:
        desired = HostPublicationDesiredState(tuple(set(decoded)))
        canonical = desired.rules
    except ValueError as exc:
        conflicts.append(f"invalid observed host publication rules: {exc}")
        canonical = tuple(sorted(set(decoded), key=_observed_sort_key))

    return HostPublicationPhysicalObservation(
        table_present=True,
        rules=canonical,
        conflicts=tuple(conflicts),
        forwarding_enabled=forwarding_enabled,
    )


def _decode_rule(payload: dict) -> HostPublicationRuleSpec:
    expr = payload.get("expr")
    if not isinstance(expr, list):
        raise ValueError("host publication rule expr must be an array")

    fib_local = 0
    interface: str | None = None
    address: IPv4Address | None = None
    protocol: PublicationProtocol | None = None
    host_port: int | None = None
    internal_address: IPv4Address | None = None
    internal_port: int | None = None

    for item in expr:
        if not isinstance(item, dict) or len(item) != 1:
            raise ValueError("unsupported host publication expression")
        if "match" in item:
            match = item["match"]
            if (
                not isinstance(match, dict)
                or match.get("op") != "=="
                or "left" not in match
                or "right" not in match
            ):
                raise ValueError("invalid host publication match")
            left = match["left"]
            right = match["right"]
            if _is_fib_local(left, right):
                fib_local += 1
                continue
            if isinstance(left, dict) and left == {"meta": {"key": "iifname"}}:
                if interface is not None or not isinstance(right, str) or not right:
                    raise ValueError("invalid/duplicate host publication interface match")
                interface = right
                continue
            if (
                isinstance(left, dict)
                and left == {"payload": {"protocol": "ip", "field": "daddr"}}
            ):
                if address is not None or not isinstance(right, str):
                    raise ValueError("invalid/duplicate host publication IPv4 match")
                try:
                    address = IPv4Address(right)
                except ValueError:
                    raise ValueError("invalid host publication IPv4 operand") from None
                continue
            if isinstance(left, dict) and set(left) == {"payload"}:
                p = left["payload"]
                if isinstance(p, dict) and p.get("field") == "dport":
                    try:
                        parsed_protocol = PublicationProtocol(p.get("protocol"))
                    except ValueError:
                        raise ValueError("unsupported host publication protocol") from None
                    if (
                        protocol is not None
                        or type(right) is not int
                        or not 1 <= right <= 65535
                    ):
                        raise ValueError("invalid/duplicate host publication port match")
                    protocol = parsed_protocol
                    host_port = right
                    continue
            raise ValueError("unsupported host publication match expression")

        if "dnat" in item:
            if internal_address is not None or internal_port is not None:
                raise ValueError("duplicate host publication DNAT")
            dnat = item["dnat"]
            if not isinstance(dnat, dict):
                raise ValueError("invalid host publication DNAT")
            allowed = {"addr", "port", "family", "flags"}
            if set(dnat) - allowed:
                raise ValueError("unsupported host publication DNAT fields")
            if dnat.get("family") not in {None, "ip"}:
                raise ValueError("host publication DNAT family mismatch")
            flags = dnat.get("flags")
            if flags not in {None, ()} and flags != []:
                raise ValueError("host publication DNAT flags are unsupported")
            try:
                internal_address = IPv4Address(dnat.get("addr"))
            except (TypeError, ValueError):
                raise ValueError("invalid host publication DNAT address") from None
            port = dnat.get("port")
            if type(port) is not int or not 1 <= port <= 65535:
                raise ValueError("invalid host publication DNAT port")
            internal_port = port
            continue

        raise ValueError("unsupported host publication rule statement")

    if fib_local != 1:
        raise ValueError("host publication rule must prove destination locality exactly once")
    if protocol is None or host_port is None:
        raise ValueError("host publication rule lacks exact transport port")
    if internal_address is None or internal_port is None:
        raise ValueError("host publication rule lacks exact DNAT target")
    if interface is not None and address is not None:
        raise ValueError("host publication rule mixes interface and IPv4 selectors")

    if interface is not None:
        kind = HostPublicationSelectorKind.INTERFACE
        value: IPv4Address | str | None = interface
    elif address is not None:
        kind = HostPublicationSelectorKind.IPV4
        value = address
    else:
        kind = HostPublicationSelectorKind.ANY
        value = None

    return HostPublicationRuleSpec(
        protocol=protocol,
        selector_kind=kind,
        selector_value=value,
        host_port=host_port,
        internal_address=internal_address,
        internal_port=internal_port,
    )


def _is_fib_local(left: object, right: object) -> bool:
    if right != "local" or not isinstance(left, dict) or set(left) != {"fib"}:
        return False
    fib = left["fib"]
    if not isinstance(fib, dict) or fib.get("result") != "type":
        return False
    flags = fib.get("flags")
    return flags == "daddr" or flags == ["daddr"]


def _observed_sort_key(rule: HostPublicationRuleSpec) -> tuple[object, ...]:
    return (
        rule.protocol.value,
        rule.host_port,
        rule.selector_kind.value,
        "" if rule.selector_value is None else str(rule.selector_value),
        int(rule.internal_address),
        rule.internal_port,
    )
