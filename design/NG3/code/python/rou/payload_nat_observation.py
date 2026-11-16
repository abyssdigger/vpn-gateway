"""Read-only authoritative observation and comparison of owned payload NAT rules."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Iterable

from .interface_identity import InterfaceIdentity
from .nft_namespace_inventory import NftNamespaceObject, NftNamespaceObservation
from .nft_payload_scaffold import (
    PAYLOAD_POSTROUTING_CHAIN,
    compare_payload_nft_scaffold,
)
from .payload_nat_desired import PayloadNatDesiredState, PayloadMasqueradeSpec


PAYLOAD_NAT_RULE_COMMENT = "vpn-gate:ng3:payload-nat-v1"


class PayloadNatObservationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ObservedPayloadMasquerade:
    handle: int
    ingress: InterfaceIdentity | int
    egress: InterfaceIdentity | int

    @property
    def stale(self) -> bool:
        return type(self.ingress) is int or type(self.egress) is int


@dataclass(frozen=True, slots=True)
class PayloadNatRuleConflict:
    handle: int | None
    reason: str


@dataclass(frozen=True, slots=True)
class PayloadNatComparison:
    confirmed: tuple[PayloadMasqueradeSpec, ...]
    missing: tuple[PayloadMasqueradeSpec, ...]
    stale: tuple[ObservedPayloadMasquerade, ...]
    conflicts: tuple[PayloadNatRuleConflict, ...]

    @property
    def conflict_free(self) -> bool:
        """No conflicts inside the observed payload NAT chain only.

        This does not certify full nft-table ownership or authorize mutation:
        unrelated owned objects, whole-policy verification and ForwardingGate
        remain separate structural safety gates.
        """
        return not self.conflicts


def compare_payload_nat(
    observation: NftNamespaceObservation,
    interfaces: Iterable[InterfaceIdentity],
    desired: PayloadNatDesiredState,
) -> PayloadNatComparison:
    """Classify every rule in the owned NAT chain; never mutate kernel state.

    A missing or conflicting table/scaffold is a hard observation failure:
    the caller must not interpret it as an empty chain and add rules.
    """
    if not isinstance(observation, NftNamespaceObservation):
        raise PayloadNatObservationError("observation must be NftNamespaceObservation")
    if not isinstance(desired, PayloadNatDesiredState):
        raise PayloadNatObservationError("desired must be PayloadNatDesiredState")
    scaffold = compare_payload_nft_scaffold(observation)
    if not scaffold.scaffold_confirmed:
        raise PayloadNatObservationError("NAT table/scaffold ownership is not confirmed")

    by_name: dict[str, InterfaceIdentity] = {}
    by_index: dict[int, InterfaceIdentity] = {}
    for identity in interfaces:
        if not isinstance(identity, InterfaceIdentity):
            raise PayloadNatObservationError("inventory must contain InterfaceIdentity")
        if identity.ifname in by_name or identity.ifindex in by_index:
            raise PayloadNatObservationError("ambiguous current interface inventory")
        by_name[identity.ifname] = identity
        by_index[identity.ifindex] = identity

    expected: dict[tuple[InterfaceIdentity, InterfaceIdentity], PayloadMasqueradeSpec] = {}
    for spec in desired.masquerade_rules:
        if not isinstance(spec, PayloadMasqueradeSpec):
            raise PayloadNatObservationError("invalid desired masquerade spec")
        if spec.ingress not in by_name.values() or spec.egress not in by_name.values():
            raise PayloadNatObservationError("desired NAT endpoints are not current")
        key = (spec.ingress, spec.egress)
        if key in expected:
            raise PayloadNatObservationError("duplicate desired physical NAT rule")
        expected[key] = spec

    observed: list[ObservedPayloadMasquerade] = []
    conflicts: list[PayloadNatRuleConflict] = []
    seen_handles: set[int] = set()
    for item in observation.objects:
        if item.kind != "rule":
            continue
        try:
            payload = _rule_payload(item)
        except PayloadNatObservationError as exc:
            conflicts.append(PayloadNatRuleConflict(None, str(exc)))
            continue
        chain = payload.get("chain")
        if not isinstance(chain, str) or not chain:
            conflicts.append(PayloadNatRuleConflict(None, "rule has missing/invalid chain"))
            continue
        if chain != PAYLOAD_POSTROUTING_CHAIN:
            continue
        handle = payload.get("handle")
        if type(handle) is not int or handle < 0:
            conflicts.append(PayloadNatRuleConflict(None, "invalid NAT rule handle"))
            continue
        if handle in seen_handles:
            conflicts.append(PayloadNatRuleConflict(handle, "duplicate NAT rule handle"))
            continue
        seen_handles.add(handle)
        try:
            observed.append(_decode_rule(payload, by_name, by_index))
        except PayloadNatObservationError as exc:
            conflicts.append(PayloadNatRuleConflict(handle, str(exc)))

    physical_seen: set[tuple[InterfaceIdentity | int, InterfaceIdentity | int]] = set()
    confirmed_keys: set[tuple[InterfaceIdentity, InterfaceIdentity]] = set()
    stale: list[ObservedPayloadMasquerade] = []
    for rule in observed:
        key = (rule.ingress, rule.egress)
        if key in physical_seen:
            conflicts.append(PayloadNatRuleConflict(rule.handle, "duplicate physical NAT rule"))
            continue
        physical_seen.add(key)
        if rule.stale:
            stale.append(rule)
        elif key in expected:
            confirmed_keys.add(key)
        else:
            stale.append(rule)

    confirmed = tuple(spec for key, spec in expected.items() if key in confirmed_keys)
    missing = tuple(spec for key, spec in expected.items() if key not in confirmed_keys)
    return PayloadNatComparison(confirmed, missing, tuple(stale), tuple(conflicts))


def _rule_payload(item: NftNamespaceObject) -> dict:
    try:
        row = json.loads(item.canonical_json)
    except (TypeError, ValueError):
        raise PayloadNatObservationError("invalid canonical NAT rule JSON") from None
    if not isinstance(row, dict) or set(row) != {"rule"} or not isinstance(row["rule"], dict):
        raise PayloadNatObservationError("invalid canonical NAT rule shape")
    return row["rule"]


def _decode_rule(
    payload: dict,
    by_name: dict[str, InterfaceIdentity],
    by_index: dict[int, InterfaceIdentity],
) -> ObservedPayloadMasquerade:
    allowed = {"family", "table", "chain", "handle", "comment", "expr"}
    if set(payload) - allowed:
        raise PayloadNatObservationError("unsupported NAT rule fields")
    if (payload.get("family"), payload.get("table"), payload.get("chain")) != (
        "ip", "vpn_gate", PAYLOAD_POSTROUTING_CHAIN
    ):
        raise PayloadNatObservationError("wrong NAT rule scope")
    if payload.get("comment") != PAYLOAD_NAT_RULE_COMMENT:
        raise PayloadNatObservationError("missing/wrong NAT owner comment")
    expressions = payload.get("expr")
    if not isinstance(expressions, list) or len(expressions) != 3:
        raise PayloadNatObservationError("NAT rule must contain exactly three expressions")
    ingress = _match_operand(expressions[0], "iif", by_name, by_index)
    egress = _match_operand(expressions[1], "oif", by_name, by_index)
    if expressions[2] != {"masquerade": None} and expressions[2] != {"masquerade": {}}:
        raise PayloadNatObservationError("unsupported NAT action")
    return ObservedPayloadMasquerade(payload["handle"], ingress, egress)


def _match_operand(
    expr: object,
    key: str,
    by_name: dict[str, InterfaceIdentity],
    by_index: dict[int, InterfaceIdentity],
) -> InterfaceIdentity | int:
    if not isinstance(expr, dict) or set(expr) != {"match"}:
        raise PayloadNatObservationError(f"invalid {key} match")
    match = expr["match"]
    if not isinstance(match, dict) or set(match) != {"op", "left", "right"}:
        raise PayloadNatObservationError(f"invalid {key} match structure")
    if match["op"] != "==" or match["left"] != {"meta": {"key": key}}:
        raise PayloadNatObservationError(f"invalid {key} match expression")
    operand = match["right"]
    if type(operand) is not str or not operand:
        raise PayloadNatObservationError(f"invalid {key} interface operand")
    if operand.isascii() and operand.isdecimal():
        index = int(operand)
        if index <= 0:
            raise PayloadNatObservationError(f"invalid {key} interface index")
        return by_index.get(index, index)
    identity = by_name.get(operand)
    if identity is None:
        raise PayloadNatObservationError(f"unresolved {key} interface name")
    return identity
