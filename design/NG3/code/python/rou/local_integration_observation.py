"""Read-only observation/comparison for supported VPN integration local transport rules."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address
import json
from typing import Iterable

from .interface_identity import InterfaceIdentity
from .local_integration_policy import (
    IntegrationLocalDesiredState,
    IntegrationLocalHook,
    IntegrationLocalRuleSpec,
    IntegrationTransportProtocol,
)
from .nft_namespace_inventory import NftNamespaceObservation
from .nft_payload_scaffold import compare_payload_nft_scaffold


LOCAL_INTEGRATION_RULE_COMMENT = "vpn-gate:ng3:local-integration-v1"


@dataclass(frozen=True, slots=True)
class ObservedIntegrationLocalRule:
    handle: int
    hook: IntegrationLocalHook
    protocol: IntegrationTransportProtocol
    host_boundary: InterfaceIdentity | int
    local_address: IPv4Address
    remote_address: IPv4Address
    remote_port: int
    local_port: int | None

    @property
    def stale(self) -> bool:
        return type(self.host_boundary) is int


@dataclass(frozen=True, slots=True)
class IntegrationLocalConflict:
    handle: int | None
    reason: str


@dataclass(frozen=True, slots=True)
class IntegrationLocalComparison:
    confirmed: tuple[IntegrationLocalRuleSpec, ...]
    missing: tuple[IntegrationLocalRuleSpec, ...]
    stale: tuple[ObservedIntegrationLocalRule, ...]
    conflicts: tuple[IntegrationLocalConflict, ...]

    @property
    def desired_confirmed(self) -> bool:
        return not self.missing and not self.stale and not self.conflicts


def compare_integration_local(
    observation: NftNamespaceObservation,
    interfaces: Iterable[InterfaceIdentity],
    desired: IntegrationLocalDesiredState,
) -> IntegrationLocalComparison:
    if not isinstance(desired, IntegrationLocalDesiredState):
        raise ValueError("desired must be IntegrationLocalDesiredState")
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
            raise ValueError("desired integration-local boundary is not current")

    observed: list[ObservedIntegrationLocalRule] = []
    conflicts: list[IntegrationLocalConflict] = []
    seen_handles: set[int] = set()

    for item in observation.objects:
        if item.kind != "rule":
            continue
        payload = _rule_payload(item)
        if payload.get("comment") != LOCAL_INTEGRATION_RULE_COMMENT:
            continue
        handle = payload.get("handle")
        if type(handle) is not int or handle < 0:
            conflicts.append(IntegrationLocalConflict(None, "invalid integration-local handle"))
            continue
        if handle in seen_handles:
            conflicts.append(IntegrationLocalConflict(handle, "duplicate integration-local handle"))
            continue
        seen_handles.add(handle)
        try:
            observed.append(_decode_rule(payload, by_name, by_index))
        except ValueError as exc:
            conflicts.append(IntegrationLocalConflict(handle, str(exc)))

    expected = {_spec_key(spec): spec for spec in desired.rules}
    confirmed_keys: set[tuple[object, ...]] = set()
    stale: list[ObservedIntegrationLocalRule] = []
    physical_seen: set[tuple[object, ...]] = set()
    for rule in observed:
        key = _observed_key(rule)
        if key in physical_seen:
            conflicts.append(
                IntegrationLocalConflict(rule.handle, "duplicate physical integration-local rule")
            )
            continue
        physical_seen.add(key)
        if rule.stale or key not in expected:
            stale.append(rule)
        else:
            confirmed_keys.add(key)

    return IntegrationLocalComparison(
        confirmed=tuple(spec for spec in desired.rules if _spec_key(spec) in confirmed_keys),
        missing=tuple(spec for spec in desired.rules if _spec_key(spec) not in confirmed_keys),
        stale=tuple(stale),
        conflicts=tuple(conflicts),
    )


def _decode_rule(payload, by_name, by_index):
    allowed = {"family", "table", "chain", "handle", "comment", "expr"}
    if set(payload) - allowed:
        raise ValueError("unsupported integration-local rule fields")
    if (payload.get("family"), payload.get("table")) != ("ip", "vpn_gate"):
        raise ValueError("wrong integration-local rule scope")

    chain = payload.get("chain")
    if chain == "stack_output":
        hook = IntegrationLocalHook.OUTPUT
        iface_key = "oif"
        local_field = "saddr"
        remote_field = "daddr"
        remote_port_field = "dport"
        local_port_field = "sport"
    elif chain == "stack_input":
        hook = IntegrationLocalHook.INPUT
        iface_key = "iif"
        local_field = "daddr"
        remote_field = "saddr"
        remote_port_field = "sport"
        local_port_field = "dport"
    else:
        raise ValueError("integration-local owner marker is on wrong chain")

    expr = payload.get("expr")
    if not isinstance(expr, list) or len(expr) not in (5, 6):
        raise ValueError("integration-local rule must contain five or six expressions")

    boundary = _interface_match(expr[0], iface_key, by_name, by_index)
    if hook is IntegrationLocalHook.INPUT:
        remote_address = _address_match(expr[1], remote_field)
        local_address = _address_match(expr[2], local_field)
    else:
        local_address = _address_match(expr[1], local_field)
        remote_address = _address_match(expr[2], remote_field)
    local_port = None
    if len(expr) == 6 and not (
        hook is IntegrationLocalHook.INPUT
        and _is_established_match(expr[4])
    ):
        parsed_ports = (
            _port_match_any(expr[3]),
            _port_match_any(expr[4]),
        )
        remote_matches = [
            item for item in parsed_ports if item[1] == remote_port_field
        ]
        local_matches = [
            item for item in parsed_ports if item[1] == local_port_field
        ]
        if len(remote_matches) != 1 or len(local_matches) != 1:
            raise ValueError(
                "integration-local exact port selectors are incomplete/ambiguous"
            )
        protocol, _, remote_port = remote_matches[0]
        local_protocol, _, local_port = local_matches[0]
        if local_protocol is not protocol:
            raise ValueError("integration-local protocol mismatch")
        action = expr[5]
    else:
        protocol, remote_port = _port_match(expr[3], remote_port_field)
        if len(expr) == 6:
            action = expr[5]
        else:
            if hook is IntegrationLocalHook.INPUT:
                raise ValueError(
                    "integration-local INPUT without local port must carry conntrack state"
                )
            action = expr[4]

    if hook is IntegrationLocalHook.INPUT and local_port is None:
        if len(expr) != 6 or not _is_established_match(expr[4]):
            raise ValueError("integration-local dynamic-port INPUT must be established/related")

    if action != {"accept": None}:
        raise ValueError("integration-local rule action must be plain accept")

    return ObservedIntegrationLocalRule(
        handle=payload["handle"],
        hook=hook,
        protocol=protocol,
        host_boundary=boundary,
        local_address=local_address,
        remote_address=remote_address,
        remote_port=remote_port,
        local_port=local_port,
    )


def _interface_match(expr, key, by_name, by_index):
    match = _match(expr)
    if match["left"] != {"meta": {"key": key}}:
        raise ValueError(f"invalid integration-local {key} match")
    operand = match["right"]
    if type(operand) is not str or not operand:
        raise ValueError(f"invalid integration-local {key} operand")
    if operand.isascii() and operand.isdecimal():
        index = int(operand)
        if index <= 0:
            raise ValueError(f"invalid integration-local {key} index")
        return by_index.get(index, index)
    identity = by_name.get(operand)
    if identity is None:
        raise ValueError(f"unresolved integration-local {key} interface")
    return identity


def _address_match(expr, field):
    match = _match(expr)
    if match["left"] != {"payload": {"protocol": "ip", "field": field}}:
        raise ValueError("invalid integration-local IPv4 match")
    right = match["right"]
    if not isinstance(right, str):
        raise ValueError("integration-local IPv4 operand must be address string")
    try:
        return IPv4Address(right)
    except ValueError:
        raise ValueError("invalid integration-local IPv4 address") from None


def _port_match_any(expr):
    match = _match(expr)
    left = match["left"]
    right = match["right"]
    if not isinstance(left, dict) or set(left) != {"payload"}:
        raise ValueError("invalid integration-local port selector")
    payload = left["payload"]
    if not isinstance(payload, dict):
        raise ValueError("invalid integration-local port payload selector")
    field = payload.get("field")
    if field not in {"sport", "dport"}:
        raise ValueError("invalid integration-local port field")
    try:
        protocol = IntegrationTransportProtocol(payload.get("protocol"))
    except ValueError:
        raise ValueError("unsupported integration-local protocol") from None
    if type(right) is not int or not 1 <= right <= 65535:
        raise ValueError("invalid integration-local port")
    return protocol, field, right


def _port_match(expr, field):
    protocol, observed_field, port = _port_match_any(expr)
    if observed_field != field:
        raise ValueError("invalid integration-local port field")
    return protocol, port


def _is_established_match(expr):
    if not isinstance(expr, dict) or set(expr) != {"match"}:
        return False
    match = expr["match"]
    return (
        isinstance(match, dict)
        and set(match) == {"op", "left", "right"}
        and match["op"] == "in"
        and match["left"] == {"ct": {"key": "state"}}
        and match["right"] == ["established", "related"]
    )


def _match(expr):
    if not isinstance(expr, dict) or set(expr) != {"match"}:
        raise ValueError("invalid integration-local match expression")
    match = expr["match"]
    if (
        not isinstance(match, dict)
        or set(match) != {"op", "left", "right"}
        or match["op"] != "=="
    ):
        raise ValueError("invalid integration-local match structure")
    return match


def _rule_payload(item):
    try:
        row = json.loads(item.canonical_json)
    except (TypeError, ValueError):
        raise ValueError("invalid canonical integration-local rule JSON") from None
    if (
        not isinstance(row, dict)
        or set(row) != {"rule"}
        or not isinstance(row["rule"], dict)
    ):
        raise ValueError("invalid canonical integration-local rule shape")
    return row["rule"]


def _spec_key(spec):
    return (
        spec.hook,
        spec.protocol,
        spec.host_boundary,
        spec.local_address,
        spec.remote_address,
        spec.remote_port,
        spec.local_port,
    )


def _observed_key(rule):
    return (
        rule.hook,
        rule.protocol,
        rule.host_boundary,
        rule.local_address,
        rule.remote_address,
        rule.remote_port,
        rule.local_port,
    )
