"""EXP-066-backed observation/comparison for probe-owned local nft admission."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address
import json
from typing import Iterable

from .interface_identity import InterfaceIdentity
from .nft_namespace_inventory import NftNamespaceObservation
from .nft_payload_scaffold import compare_payload_nft_scaffold
from .probe_policy import (
    AvailabilityProbeMechanism,
    ProbeLocalHook,
    ProbeLocalRuleSpec,
)


PROBE_LOCAL_RULE_COMMENT = "vpn-gate:ng3:probe-local-v1"


@dataclass(frozen=True, slots=True)
class ObservedProbeLocalRule:
    handle: int
    hook: ProbeLocalHook
    endpoint: InterfaceIdentity | int
    target: IPv4Address
    conntrack_mark: int
    process_uid: int | None = None

    @property
    def stale(self) -> bool:
        return type(self.endpoint) is int


@dataclass(frozen=True, slots=True)
class ProbeLocalConflict:
    handle: int | None
    reason: str


@dataclass(frozen=True, slots=True)
class ProbeLocalComparison:
    confirmed: tuple[ProbeLocalRuleSpec, ...]
    missing: tuple[ProbeLocalRuleSpec, ...]
    stale: tuple[ObservedProbeLocalRule, ...]
    conflicts: tuple[ProbeLocalConflict, ...]

    @property
    def desired_confirmed(self) -> bool:
        return not self.missing and not self.stale and not self.conflicts


def compare_probe_local(
    observation: NftNamespaceObservation,
    interfaces: Iterable[InterfaceIdentity],
    desired: Iterable[ProbeLocalRuleSpec],
) -> ProbeLocalComparison:
    scaffold = compare_payload_nft_scaffold(observation)
    if not scaffold.scaffold_confirmed:
        raise ValueError("invariant nft scaffold is not confirmed")

    desired_rules = tuple(desired)
    if not all(isinstance(rule, ProbeLocalRuleSpec) for rule in desired_rules):
        raise ValueError("desired must contain ProbeLocalRuleSpec")

    current = tuple(interfaces)
    by_name: dict[str, InterfaceIdentity] = {}
    by_index: dict[int, InterfaceIdentity] = {}
    for identity in current:
        if not isinstance(identity, InterfaceIdentity):
            raise ValueError("interfaces must contain InterfaceIdentity")
        if identity.ifname in by_name or identity.ifindex in by_index:
            raise ValueError("ambiguous current interface inventory")
        by_name[identity.ifname] = identity
        by_index[identity.ifindex] = identity

    current_set = set(current)
    for spec in desired_rules:
        if spec.endpoint not in current_set:
            raise ValueError("desired probe-local endpoint is not current")
        if spec.mechanism is not AvailabilityProbeMechanism.ICMP:
            raise ValueError("Release 1 probe-local desired state must be ICMP")

    observed: list[ObservedProbeLocalRule] = []
    conflicts: list[ProbeLocalConflict] = []
    seen_handles: set[int] = set()

    for item in observation.objects:
        if item.kind != "rule":
            continue
        payload = _rule_payload(item)
        if payload.get("comment") != PROBE_LOCAL_RULE_COMMENT:
            continue
        handle = payload.get("handle")
        if type(handle) is not int or handle < 0:
            conflicts.append(ProbeLocalConflict(None, "invalid probe-local handle"))
            continue
        if handle in seen_handles:
            conflicts.append(ProbeLocalConflict(handle, "duplicate probe-local handle"))
            continue
        seen_handles.add(handle)
        try:
            observed.append(_decode_rule(payload, by_name, by_index))
        except ValueError as exc:
            conflicts.append(ProbeLocalConflict(handle, str(exc)))

    # Probe semantic owners are not encoded in nft. Several (Profile,path) subjects may
    # therefore project to one identical physical admission rule. Compare physical union.
    expected: dict[tuple[object, ...], ProbeLocalRuleSpec] = {}
    for spec in desired_rules:
        expected.setdefault(_spec_key(spec), spec)

    confirmed_keys: set[tuple[object, ...]] = set()
    stale: list[ObservedProbeLocalRule] = []
    physical_seen: set[tuple[object, ...]] = set()
    for rule in observed:
        key = _observed_key(rule)
        if key in physical_seen:
            conflicts.append(
                ProbeLocalConflict(
                    rule.handle,
                    "duplicate physical probe-local rule",
                )
            )
            continue
        physical_seen.add(key)
        if rule.stale or key not in expected:
            stale.append(rule)
        else:
            confirmed_keys.add(key)

    return ProbeLocalComparison(
        confirmed=tuple(
            expected[key]
            for key in sorted(
                confirmed_keys,
                key=_physical_sort_key,
            )
        ),
        missing=tuple(
            expected[key]
            for key in sorted(
                set(expected) - confirmed_keys,
                key=_physical_sort_key,
            )
        ),
        stale=tuple(sorted(stale, key=lambda rule: (rule.hook.value, rule.handle))),
        conflicts=tuple(conflicts),
    )


def _decode_rule(payload, by_name, by_index):
    allowed = {"family", "table", "chain", "handle", "comment", "expr"}
    if set(payload) - allowed:
        raise ValueError("unsupported probe-local rule fields")
    if (payload.get("family"), payload.get("table")) != ("ip", "vpn_gate"):
        raise ValueError("wrong probe-local rule scope")

    chain = payload.get("chain")
    expr = payload.get("expr")
    if chain == "stack_output":
        if not isinstance(expr, list) or len(expr) != 6:
            raise ValueError("probe-local OUTPUT must contain six expressions")
        endpoint = _interface_match(expr[1], "oif", by_name, by_index)
        process_uid = _uid_match(expr[0])
        target = _address_match(expr[2], "daddr")
        _icmp_match(expr[3])
        mark = _ct_mark_set(expr[4])
        if expr[5] != {"accept": None}:
            raise ValueError("probe-local OUTPUT action must be plain accept")
        return ObservedProbeLocalRule(
            handle=payload["handle"],
            hook=ProbeLocalHook.OUTPUT,
            endpoint=endpoint,
            target=target,
            conntrack_mark=mark,
            process_uid=process_uid,
        )

    if chain == "stack_input":
        if not isinstance(expr, list) or len(expr) != 5:
            raise ValueError("probe-local INPUT must contain five expressions")
        endpoint = _interface_match(expr[0], "iif", by_name, by_index)
        target = _address_match(expr[1], "saddr")
        _icmp_match(expr[2])
        mark = _ct_mark_match(expr[3])
        if expr[4] != {"accept": None}:
            raise ValueError("probe-local INPUT action must be plain accept")
        return ObservedProbeLocalRule(
            handle=payload["handle"],
            hook=ProbeLocalHook.INPUT,
            endpoint=endpoint,
            target=target,
            conntrack_mark=mark,
        )

    raise ValueError("probe-local owner marker is on wrong chain")


def _match(expr):
    if not isinstance(expr, dict) or set(expr) != {"match"}:
        raise ValueError("invalid probe-local match expression")
    match = expr["match"]
    if (
        not isinstance(match, dict)
        or set(match) != {"op", "left", "right"}
        or match["op"] != "=="
    ):
        raise ValueError("invalid probe-local match structure")
    return match


def _interface_match(expr, key, by_name, by_index):
    match = _match(expr)
    if match["left"] != {"meta": {"key": key}}:
        raise ValueError(f"invalid probe-local {key} match")
    operand = match["right"]
    if type(operand) is not str or not operand:
        raise ValueError(f"invalid probe-local {key} operand")
    if operand.isascii() and operand.isdecimal():
        index = int(operand)
        if index <= 0:
            raise ValueError(f"invalid probe-local {key} index")
        return by_index.get(index, index)
    identity = by_name.get(operand)
    if identity is None:
        raise ValueError(f"unresolved probe-local {key} interface")
    return identity


def _uid_match(expr):
    match = _match(expr)
    if match["left"] != {"meta": {"key": "skuid"}}:
        raise ValueError("invalid probe-local skuid match")
    uid = match["right"]
    if type(uid) is not int or not 1 <= uid <= 0xFFFFFFFE:
        raise ValueError("probe-local skuid must be a non-root Linux uid")
    return uid


def _address_match(expr, field):
    match = _match(expr)
    if match["left"] != {"payload": {"protocol": "ip", "field": field}}:
        raise ValueError("invalid probe-local IPv4 match")
    right = match["right"]
    if not isinstance(right, str):
        raise ValueError("probe-local IPv4 operand must be address string")
    try:
        return IPv4Address(right)
    except ValueError:
        raise ValueError("invalid probe-local IPv4 address") from None


def _icmp_match(expr):
    match = _match(expr)
    if match["left"] != {"payload": {"protocol": "ip", "field": "protocol"}}:
        raise ValueError("invalid probe-local protocol selector")
    # nft JSON renders the IPv4 protocol constant as either numeric 1
    # or symbolic "icmp" depending on nftables/libnftables version.
    if match["right"] not in (1, "icmp"):
        raise ValueError("Release 1 probe-local protocol must be ICMP")


def _ct_mark_set(expr):
    if not isinstance(expr, dict) or set(expr) != {"mangle"}:
        raise ValueError("probe-local OUTPUT must assign conntrack mark")
    body = expr["mangle"]
    if (
        not isinstance(body, dict)
        or set(body) != {"key", "value"}
        or body["key"] != {"ct": {"key": "mark"}}
    ):
        raise ValueError("invalid probe-local conntrack mark assignment")
    return _mark(body["value"])


def _ct_mark_match(expr):
    match = _match(expr)
    if match["left"] != {"ct": {"key": "mark"}}:
        raise ValueError("invalid probe-local conntrack mark match")
    return _mark(match["right"])


def _mark(value):
    if type(value) is not int or not 1 <= value <= 0xFFFFFFFF:
        raise ValueError("probe-local conntrack mark must be non-zero u32")
    return value


def _rule_payload(item):
    try:
        row = json.loads(item.canonical_json)
    except (TypeError, ValueError):
        raise ValueError("invalid canonical probe-local rule JSON") from None
    if (
        not isinstance(row, dict)
        or set(row) != {"rule"}
        or not isinstance(row["rule"], dict)
    ):
        raise ValueError("invalid canonical probe-local rule shape")
    return row["rule"]


def _spec_key(spec):
    return (
        spec.hook,
        spec.endpoint,
        spec.target,
        spec.conntrack_mark,
        spec.process_uid,
    )


def _observed_key(rule):
    return (
        rule.hook,
        rule.endpoint,
        rule.target,
        rule.conntrack_mark,
        rule.process_uid,
    )


def _physical_sort_key(key):
    hook, endpoint, target, mark, uid = key
    return (
        hook.value,
        endpoint.ifindex,
        int(target),
        mark,
        -1 if uid is None else uid,
    )
