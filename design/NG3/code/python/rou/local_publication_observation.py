"""Read-only observation/comparison for EXP-046-backed publication-local rules."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address
import json
from typing import Iterable

from .interface_identity import InterfaceIdentity
from .local_publication_policy import (
    LocalPublicationDesiredState,
    LocalPublicationHook,
    LocalPublicationRuleSpec,
    PublicationProtocol,
)
from .nft_namespace_inventory import NftNamespaceObservation
from .nft_payload_scaffold import compare_payload_nft_scaffold


LOCAL_PUBLICATION_RULE_COMMENT = "vpn-gate:ng3:local-publication-v1"


@dataclass(frozen=True, slots=True)
class ObservedLocalPublicationRule:
    handle: int
    hook: LocalPublicationHook
    protocol: PublicationProtocol
    host_boundary: InterfaceIdentity | int
    local_address: IPv4Address
    local_port: int

    @property
    def stale(self) -> bool:
        return type(self.host_boundary) is int


@dataclass(frozen=True, slots=True)
class LocalPublicationConflict:
    handle: int | None
    reason: str


@dataclass(frozen=True, slots=True)
class LocalPublicationComparison:
    confirmed: tuple[LocalPublicationRuleSpec, ...]
    missing: tuple[LocalPublicationRuleSpec, ...]
    stale: tuple[ObservedLocalPublicationRule, ...]
    conflicts: tuple[LocalPublicationConflict, ...]

    @property
    def desired_confirmed(self) -> bool:
        return not self.missing and not self.stale and not self.conflicts


def compare_local_publication(
    observation: NftNamespaceObservation,
    interfaces: Iterable[InterfaceIdentity],
    desired: LocalPublicationDesiredState,
) -> LocalPublicationComparison:
    if not isinstance(desired, LocalPublicationDesiredState):
        raise ValueError("desired must be LocalPublicationDesiredState")

    scaffold = compare_payload_nft_scaffold(observation)
    if not scaffold.scaffold_confirmed:
        raise ValueError("invariant nft scaffold is not confirmed")

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
    for spec in desired.rules:
        if spec.host_boundary not in current_set:
            raise ValueError("desired local publication boundary is not current")

    observed: list[ObservedLocalPublicationRule] = []
    conflicts: list[LocalPublicationConflict] = []
    seen_handles: set[int] = set()

    for item in observation.objects:
        if item.kind != "rule":
            continue
        payload = _rule_payload(item)
        if payload.get("comment") != LOCAL_PUBLICATION_RULE_COMMENT:
            continue
        chain = payload.get("chain")
        if chain not in {"stack_input", "stack_output"}:
            conflicts.append(
                LocalPublicationConflict(
                    _valid_handle(payload.get("handle")),
                    "publication-local owner marker is on wrong chain",
                )
            )
            continue
        handle = payload.get("handle")
        if type(handle) is not int or handle < 0:
            conflicts.append(
                LocalPublicationConflict(None, "invalid publication-local rule handle")
            )
            continue
        if handle in seen_handles:
            conflicts.append(
                LocalPublicationConflict(handle, "duplicate publication-local rule handle")
            )
            continue
        seen_handles.add(handle)
        try:
            observed.append(_decode_rule(payload, by_name, by_index))
        except ValueError as exc:
            conflicts.append(LocalPublicationConflict(handle, str(exc)))

    expected = {_spec_key(spec): spec for spec in desired.rules}
    confirmed_keys: set[tuple[object, ...]] = set()
    stale: list[ObservedLocalPublicationRule] = []
    physical_seen: set[tuple[object, ...]] = set()

    for rule in observed:
        key = _observed_key(rule)
        if key in physical_seen:
            conflicts.append(
                LocalPublicationConflict(
                    rule.handle,
                    "duplicate physical publication-local rule",
                )
            )
            continue
        physical_seen.add(key)
        if rule.stale or key not in expected:
            stale.append(rule)
        else:
            confirmed_keys.add(key)

    confirmed = tuple(
        spec for spec in desired.rules if _spec_key(spec) in confirmed_keys
    )
    missing = tuple(
        spec for spec in desired.rules if _spec_key(spec) not in confirmed_keys
    )
    return LocalPublicationComparison(
        confirmed=confirmed,
        missing=missing,
        stale=tuple(stale),
        conflicts=tuple(conflicts),
    )


def _decode_rule(
    payload: dict,
    by_name: dict[str, InterfaceIdentity],
    by_index: dict[int, InterfaceIdentity],
) -> ObservedLocalPublicationRule:
    allowed = {"family", "table", "chain", "handle", "comment", "expr"}
    if set(payload) - allowed:
        raise ValueError("unsupported publication-local rule fields")
    if (payload.get("family"), payload.get("table")) != ("ip", "vpn_gate"):
        raise ValueError("wrong publication-local rule scope")

    chain = payload["chain"]
    if chain == "stack_input":
        hook = LocalPublicationHook.INPUT
        interface_key = "iif"
        address_field = "daddr"
        port_field = "dport"
    elif chain == "stack_output":
        hook = LocalPublicationHook.OUTPUT
        interface_key = "oif"
        address_field = "saddr"
        port_field = "sport"
    else:
        raise ValueError("wrong publication-local chain")

    expr = payload.get("expr")
    if not isinstance(expr, list) or len(expr) != 4:
        raise ValueError("publication-local rule must contain four expressions")

    boundary = _interface_match(expr[0], interface_key, by_name, by_index)
    local_address = _address_match(expr[1], address_field)
    protocol, local_port = _port_match(expr[2], port_field)
    if expr[3] != {"accept": None}:
        raise ValueError("publication-local rule action must be plain accept")

    return ObservedLocalPublicationRule(
        handle=payload["handle"],
        hook=hook,
        protocol=protocol,
        host_boundary=boundary,
        local_address=local_address,
        local_port=local_port,
    )


def _interface_match(
    expr: object,
    key: str,
    by_name: dict[str, InterfaceIdentity],
    by_index: dict[int, InterfaceIdentity],
) -> InterfaceIdentity | int:
    match = _match(expr)
    if match["left"] != {"meta": {"key": key}}:
        raise ValueError(f"invalid publication-local {key} match")
    operand = match["right"]
    if type(operand) is not str or not operand:
        raise ValueError(f"invalid publication-local {key} operand")
    if operand.isascii() and operand.isdecimal():
        index = int(operand)
        if index <= 0:
            raise ValueError(f"invalid publication-local {key} index")
        return by_index.get(index, index)
    identity = by_name.get(operand)
    if identity is None:
        raise ValueError(f"unresolved publication-local {key} interface")
    return identity


def _address_match(expr: object, field: str) -> IPv4Address:
    match = _match(expr)
    if match["left"] != {"payload": {"protocol": "ip", "field": field}}:
        raise ValueError("invalid publication-local IPv4 match")
    right = match["right"]
    if not isinstance(right, str):
        raise ValueError("publication-local IPv4 operand must be address string")
    try:
        return IPv4Address(right)
    except ValueError:
        raise ValueError("invalid publication-local IPv4 address") from None


def _port_match(expr: object, field: str) -> tuple[PublicationProtocol, int]:
    match = _match(expr)
    left = match["left"]
    right = match["right"]
    if not isinstance(left, dict) or set(left) != {"payload"}:
        raise ValueError("invalid publication-local port selector")
    payload = left["payload"]
    if not isinstance(payload, dict) or payload.get("field") != field:
        raise ValueError("invalid publication-local port field")
    try:
        protocol = PublicationProtocol(payload.get("protocol"))
    except ValueError:
        raise ValueError("unsupported publication-local protocol") from None
    if type(right) is not int or not 1 <= right <= 65535:
        raise ValueError("invalid publication-local port")
    return protocol, right


def _match(expr: object) -> dict:
    if not isinstance(expr, dict) or set(expr) != {"match"}:
        raise ValueError("invalid publication-local match expression")
    match = expr["match"]
    if (
        not isinstance(match, dict)
        or set(match) != {"op", "left", "right"}
        or match["op"] != "=="
    ):
        raise ValueError("invalid publication-local match structure")
    return match


def _rule_payload(item) -> dict:
    try:
        row = json.loads(item.canonical_json)
    except (TypeError, ValueError):
        raise ValueError("invalid canonical publication-local rule JSON") from None
    if (
        not isinstance(row, dict)
        or set(row) != {"rule"}
        or not isinstance(row["rule"], dict)
    ):
        raise ValueError("invalid canonical publication-local rule shape")
    return row["rule"]


def _spec_key(spec: LocalPublicationRuleSpec) -> tuple[object, ...]:
    return (
        spec.hook,
        spec.protocol,
        spec.host_boundary,
        spec.local_address,
        spec.local_port,
    )


def _observed_key(rule: ObservedLocalPublicationRule) -> tuple[object, ...]:
    return (
        rule.hook,
        rule.protocol,
        rule.host_boundary,
        rule.local_address,
        rule.local_port,
    )


def _valid_handle(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None
