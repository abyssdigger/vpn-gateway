"""Read-only authoritative observation and comparison of owned payload NAT rules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Address, IPv4Network
import json
from typing import Iterable

from .interface_identity import InterfaceIdentity
from .nft_namespace_inventory import NftNamespaceObject, NftNamespaceObservation
from .nft_payload_scaffold import (
    PAYLOAD_POSTROUTING_CHAIN,
    compare_payload_nft_scaffold,
)
from .payload_nat_desired import (
    PayloadMasqueradeSpec,
    PayloadNatDesiredState,
    PayloadNatRuleSpec,
    ProfileGatewayMasqueradeSpec,
)


PAYLOAD_NAT_RULE_COMMENT = "vpn-gate:ng3:payload-nat-v1"
PROFILE_GATEWAY_NAT_RULE_COMMENT = "vpn-gate:ng3:profile-gateway-nat-v1"


class PayloadNatObservationError(ValueError):
    pass


class PayloadNatRuleKind(str, Enum):
    DEVICE = "device"
    PROFILE_GATEWAY = "profile_gateway"


@dataclass(frozen=True, slots=True)
class ObservedPayloadMasquerade:
    handle: int
    kind: PayloadNatRuleKind
    ingress: InterfaceIdentity | int
    egress: InterfaceIdentity | int
    remote_source: IPv4Network | None = None
    excluded_host_destinations: tuple[IPv4Address, ...] = ()

    @property
    def stale(self) -> bool:
        return type(self.ingress) is int or type(self.egress) is int


@dataclass(frozen=True, slots=True)
class PayloadNatRuleConflict:
    handle: int | None
    reason: str


@dataclass(frozen=True, slots=True)
class PayloadNatComparison:
    confirmed: tuple[PayloadNatRuleSpec, ...]
    missing: tuple[PayloadNatRuleSpec, ...]
    stale: tuple[ObservedPayloadMasquerade, ...]
    conflicts: tuple[PayloadNatRuleConflict, ...]

    @property
    def conflict_free(self) -> bool:
        """No conflicts inside the observed payload NAT chain only."""
        return not self.conflicts


def compare_payload_nat(
    observation: NftNamespaceObservation,
    interfaces: Iterable[InterfaceIdentity],
    desired: PayloadNatDesiredState,
) -> PayloadNatComparison:
    """Classify every owned payload-postrouting NAT rule; never mutate."""
    if not isinstance(observation, NftNamespaceObservation):
        raise PayloadNatObservationError(
            "observation must be NftNamespaceObservation"
        )
    if not isinstance(desired, PayloadNatDesiredState):
        raise PayloadNatObservationError(
            "desired must be PayloadNatDesiredState"
        )
    scaffold = compare_payload_nft_scaffold(observation)
    if not scaffold.scaffold_confirmed:
        raise PayloadNatObservationError(
            "NAT table/scaffold ownership is not confirmed"
        )

    by_name: dict[str, InterfaceIdentity] = {}
    by_index: dict[int, InterfaceIdentity] = {}
    for identity in interfaces:
        if not isinstance(identity, InterfaceIdentity):
            raise PayloadNatObservationError(
                "inventory must contain InterfaceIdentity"
            )
        if identity.ifname in by_name or identity.ifindex in by_index:
            raise PayloadNatObservationError(
                "ambiguous current interface inventory"
            )
        by_name[identity.ifname] = identity
        by_index[identity.ifindex] = identity

    expected: dict[tuple[object, ...], PayloadNatRuleSpec] = {}
    current_identities = frozenset(by_name.values())
    for spec in desired.masquerade_rules:
        if not isinstance(
            spec,
            (PayloadMasqueradeSpec, ProfileGatewayMasqueradeSpec),
        ):
            raise PayloadNatObservationError(
                "invalid desired masquerade spec"
            )
        if (
            spec.ingress not in current_identities
            or spec.egress not in current_identities
        ):
            raise PayloadNatObservationError(
                "desired NAT endpoints are not current"
            )
        key = _desired_key(spec)
        if key in expected:
            raise PayloadNatObservationError(
                "duplicate desired physical NAT rule"
            )
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
            conflicts.append(
                PayloadNatRuleConflict(
                    None,
                    "rule has missing/invalid chain",
                )
            )
            continue
        if chain != PAYLOAD_POSTROUTING_CHAIN:
            continue
        handle = payload.get("handle")
        if type(handle) is not int or handle < 0:
            conflicts.append(
                PayloadNatRuleConflict(None, "invalid NAT rule handle")
            )
            continue
        if handle in seen_handles:
            conflicts.append(
                PayloadNatRuleConflict(
                    handle,
                    "duplicate NAT rule handle",
                )
            )
            continue
        seen_handles.add(handle)
        try:
            observed.append(
                _decode_rule(payload, by_name, by_index)
            )
        except PayloadNatObservationError as exc:
            conflicts.append(
                PayloadNatRuleConflict(handle, str(exc))
            )

    physical_seen: set[tuple[object, ...]] = set()
    confirmed_keys: set[tuple[object, ...]] = set()
    stale: list[ObservedPayloadMasquerade] = []
    for rule in observed:
        key = _observed_key(rule)
        if key in physical_seen:
            conflicts.append(
                PayloadNatRuleConflict(
                    rule.handle,
                    "duplicate physical NAT rule",
                )
            )
            continue
        physical_seen.add(key)
        if rule.stale:
            stale.append(rule)
        elif key in expected:
            confirmed_keys.add(key)
        else:
            stale.append(rule)

    confirmed = tuple(
        spec for key, spec in expected.items()
        if key in confirmed_keys
    )
    missing = tuple(
        spec for key, spec in expected.items()
        if key not in confirmed_keys
    )
    return PayloadNatComparison(
        confirmed,
        missing,
        tuple(stale),
        tuple(conflicts),
    )


def _desired_key(spec: PayloadNatRuleSpec) -> tuple[object, ...]:
    if isinstance(spec, PayloadMasqueradeSpec):
        return (
            PayloadNatRuleKind.DEVICE,
            spec.ingress,
            spec.egress,
            None,
            (),
        )
    if isinstance(spec, ProfileGatewayMasqueradeSpec):
        return (
            PayloadNatRuleKind.PROFILE_GATEWAY,
            spec.ingress,
            spec.egress,
            spec.remote_source,
            spec.excluded_host_destinations,
        )
    raise PayloadNatObservationError("unsupported desired NAT rule")


def _observed_key(
    rule: ObservedPayloadMasquerade,
) -> tuple[object, ...]:
    return (
        rule.kind,
        rule.ingress,
        rule.egress,
        rule.remote_source,
        rule.excluded_host_destinations,
    )


def _rule_payload(item: NftNamespaceObject) -> dict:
    try:
        row = json.loads(item.canonical_json)
    except (TypeError, ValueError):
        raise PayloadNatObservationError(
            "invalid canonical NAT rule JSON"
        ) from None
    if (
        not isinstance(row, dict)
        or set(row) != {"rule"}
        or not isinstance(row["rule"], dict)
    ):
        raise PayloadNatObservationError(
            "invalid canonical NAT rule shape"
        )
    return row["rule"]


def _decode_rule(
    payload: dict,
    by_name: dict[str, InterfaceIdentity],
    by_index: dict[int, InterfaceIdentity],
) -> ObservedPayloadMasquerade:
    allowed = {
        "family",
        "table",
        "chain",
        "handle",
        "comment",
        "expr",
    }
    if set(payload) - allowed:
        raise PayloadNatObservationError(
            "unsupported NAT rule fields"
        )
    if (
        payload.get("family"),
        payload.get("table"),
        payload.get("chain"),
    ) != ("ip", "vpn_gate", PAYLOAD_POSTROUTING_CHAIN):
        raise PayloadNatObservationError("wrong NAT rule scope")

    comment = payload.get("comment")
    expressions = payload.get("expr")
    if not isinstance(expressions, list):
        raise PayloadNatObservationError(
            "NAT rule expr must be an array"
        )

    if comment == PAYLOAD_NAT_RULE_COMMENT:
        if len(expressions) != 3:
            raise PayloadNatObservationError(
                "Device NAT rule must contain exactly three expressions"
            )
        ingress = _match_operand(
            expressions[0], "iif", by_name, by_index
        )
        egress = _match_operand(
            expressions[1], "oif", by_name, by_index
        )
        _masquerade(expressions[2])
        return ObservedPayloadMasquerade(
            payload["handle"],
            PayloadNatRuleKind.DEVICE,
            ingress,
            egress,
        )

    if comment != PROFILE_GATEWAY_NAT_RULE_COMMENT:
        raise PayloadNatObservationError(
            "missing/wrong NAT owner comment"
        )
    if len(expressions) < 4:
        raise PayloadNatObservationError(
            "Profile gateway NAT rule is incomplete"
        )
    ingress = _match_operand(
        expressions[0], "iif", by_name, by_index
    )
    egress = _match_operand(
        expressions[1], "oif", by_name, by_index
    )
    remote_source = _ipv4_match(
        expressions[2],
        field="saddr",
        op="==",
    )
    exclusions = tuple(
        _exact_ipv4_match(
            expression,
            field="daddr",
            op="!=",
        )
        for expression in expressions[3:-1]
    )
    if tuple(sorted(set(exclusions), key=int)) != exclusions:
        raise PayloadNatObservationError(
            "gateway NAT host-local exclusions are duplicated or unsorted"
        )
    _masquerade(expressions[-1])
    return ObservedPayloadMasquerade(
        handle=payload["handle"],
        kind=PayloadNatRuleKind.PROFILE_GATEWAY,
        ingress=ingress,
        egress=egress,
        remote_source=remote_source,
        excluded_host_destinations=exclusions,
    )


def _masquerade(expr: object) -> None:
    if expr not in ({"masquerade": None}, {"masquerade": {}}):
        raise PayloadNatObservationError(
            "unsupported NAT action"
        )


def _match_operand(
    expr: object,
    key: str,
    by_name: dict[str, InterfaceIdentity],
    by_index: dict[int, InterfaceIdentity],
) -> InterfaceIdentity | int:
    match = _match(expr)
    if (
        match["op"] != "=="
        or match["left"] != {"meta": {"key": key}}
    ):
        raise PayloadNatObservationError(
            f"invalid {key} match expression"
        )
    operand = match["right"]
    if type(operand) is not str or not operand:
        raise PayloadNatObservationError(
            f"invalid {key} interface operand"
        )
    if operand.isascii() and operand.isdecimal():
        index = int(operand)
        if index <= 0:
            raise PayloadNatObservationError(
                f"invalid {key} interface index"
            )
        return by_index.get(index, index)
    identity = by_name.get(operand)
    if identity is None:
        raise PayloadNatObservationError(
            f"unresolved {key} interface name"
        )
    return identity


def _match(expr: object) -> dict:
    if not isinstance(expr, dict) or set(expr) != {"match"}:
        raise PayloadNatObservationError(
            "invalid NAT match"
        )
    match = expr["match"]
    if not isinstance(match, dict) or set(match) != {
        "op", "left", "right"
    }:
        raise PayloadNatObservationError(
            "invalid NAT match structure"
        )
    return match


def _ipv4_match(
    expr: object,
    *,
    field: str,
    op: str,
) -> IPv4Network:
    match = _match(expr)
    if (
        match["op"] != op
        or match["left"]
        != {"payload": {"protocol": "ip", "field": field}}
    ):
        raise PayloadNatObservationError(
            f"invalid IPv4 {field} match"
        )
    return _ipv4_prefix(match["right"])


def _exact_ipv4_match(
    expr: object,
    *,
    field: str,
    op: str,
) -> IPv4Address:
    network = _ipv4_match(expr, field=field, op=op)
    if network.prefixlen != 32:
        raise PayloadNatObservationError(
            f"IPv4 {field} exclusion must be exact /32"
        )
    return network.network_address


def _ipv4_prefix(value: object) -> IPv4Network:
    if isinstance(value, str):
        if "/" in value:
            raise PayloadNatObservationError(
                "string IPv4 operand must be a plain address"
            )
        try:
            return IPv4Network((IPv4Address(value), 32))
        except ValueError:
            raise PayloadNatObservationError(
                "invalid exact IPv4 operand"
            ) from None

    if not isinstance(value, dict) or set(value) != {"prefix"}:
        raise PayloadNatObservationError(
            "unsupported IPv4 prefix operand"
        )
    prefix = value["prefix"]
    if (
        not isinstance(prefix, dict)
        or set(prefix) != {"addr", "len"}
    ):
        raise PayloadNatObservationError(
            "invalid nft IPv4 prefix object"
        )
    addr = prefix["addr"]
    length = prefix["len"]
    if (
        not isinstance(addr, str)
        or type(length) is not int
        or not 0 <= length <= 31
    ):
        raise PayloadNatObservationError(
            "invalid nft IPv4 prefix fields"
        )
    try:
        return IPv4Network(
            f"{addr}/{length}",
            strict=True,
        )
    except ValueError:
        raise PayloadNatObservationError(
            "non-canonical or invalid IPv4 prefix object"
        ) from None
