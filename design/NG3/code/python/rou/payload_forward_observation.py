"""Strict read-only observation of owned payload_forward rules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Address, IPv4Network
import json
from typing import Iterable

from .interface_identity import InterfaceIdentity
from .nft_namespace_inventory import NftNamespaceObject, NftNamespaceObservation
from .nft_payload_scaffold import (
    PAYLOAD_FORWARD_CHAIN,
    compare_payload_nft_scaffold,
)


PAYLOAD_FORWARD_NEW_COMMENT = "vpn-gate:ng3:payload-forward-new-v1"
PAYLOAD_FORWARD_RETURN_COMMENT = "vpn-gate:ng3:payload-forward-return-v1"


class PayloadForwardObservationError(ValueError):
    pass


class PayloadForwardRuleKind(str, Enum):
    NEW = "new"
    RETURN = "return"


class PayloadForwardRemoteField(str, Enum):
    SOURCE = "saddr"
    DESTINATION = "daddr"


@dataclass(frozen=True, slots=True)
class ObservedPayloadForwardRule:
    handle: int
    kind: PayloadForwardRuleKind
    ingress: InterfaceIdentity | int
    egress: InterfaceIdentity | int
    remote_field: PayloadForwardRemoteField
    remote_prefix: IPv4Network

    @property
    def stale(self) -> bool:
        return type(self.ingress) is int or type(self.egress) is int


@dataclass(frozen=True, slots=True)
class PayloadForwardRuleConflict:
    handle: int | None
    reason: str


@dataclass(frozen=True, slots=True)
class PayloadForwardObservation:
    current: tuple[ObservedPayloadForwardRule, ...]
    stale: tuple[ObservedPayloadForwardRule, ...]
    conflicts: tuple[PayloadForwardRuleConflict, ...]

    @property
    def recognized(self) -> tuple[ObservedPayloadForwardRule, ...]:
        return self.current + self.stale

    @property
    def conflict_free(self) -> bool:
        return not self.conflicts


def observe_payload_forward(
    observation: NftNamespaceObservation,
    interfaces: Iterable[InterfaceIdentity],
) -> PayloadForwardObservation:
    """Classify every rule in the owned payload_forward chain; never mutate.

    This function does not decide whether a recognized rule is desired policy.
    It proves only that the physical rule has one accepted owner shape and
    records whether its concrete interface identities are still current.
    """
    if not isinstance(observation, NftNamespaceObservation):
        raise PayloadForwardObservationError(
            "observation must be NftNamespaceObservation"
        )

    scaffold = compare_payload_nft_scaffold(observation)
    if not scaffold.scaffold_confirmed:
        raise PayloadForwardObservationError(
            "payload nft table/scaffold ownership is not confirmed"
        )

    by_name: dict[str, InterfaceIdentity] = {}
    by_index: dict[int, InterfaceIdentity] = {}
    for identity in interfaces:
        if not isinstance(identity, InterfaceIdentity):
            raise PayloadForwardObservationError(
                "inventory must contain InterfaceIdentity"
            )
        if identity.ifname in by_name or identity.ifindex in by_index:
            raise PayloadForwardObservationError(
                "ambiguous current interface inventory"
            )
        by_name[identity.ifname] = identity
        by_index[identity.ifindex] = identity

    recognized: list[ObservedPayloadForwardRule] = []
    conflicts: list[PayloadForwardRuleConflict] = []
    seen_handles: set[int] = set()

    for item in observation.objects:
        if item.kind != "rule":
            continue
        try:
            payload = _rule_payload(item)
        except PayloadForwardObservationError as exc:
            conflicts.append(PayloadForwardRuleConflict(None, str(exc)))
            continue

        chain = payload.get("chain")
        if not isinstance(chain, str) or not chain:
            conflicts.append(
                PayloadForwardRuleConflict(
                    None,
                    "rule has missing/invalid chain",
                )
            )
            continue
        if chain != PAYLOAD_FORWARD_CHAIN:
            continue

        handle = payload.get("handle")
        if type(handle) is not int or handle < 0:
            conflicts.append(
                PayloadForwardRuleConflict(None, "invalid forward rule handle")
            )
            continue
        if handle in seen_handles:
            conflicts.append(
                PayloadForwardRuleConflict(
                    handle,
                    "duplicate forward rule handle",
                )
            )
            continue
        seen_handles.add(handle)

        try:
            recognized.append(
                _decode_rule(payload, by_name, by_index)
            )
        except PayloadForwardObservationError as exc:
            conflicts.append(
                PayloadForwardRuleConflict(handle, str(exc))
            )

    physical_seen: set[
        tuple[
            PayloadForwardRuleKind,
            InterfaceIdentity | int,
            InterfaceIdentity | int,
            PayloadForwardRemoteField,
            IPv4Network,
        ]
    ] = set()
    unique: list[ObservedPayloadForwardRule] = []
    for rule in recognized:
        key = (
            rule.kind,
            rule.ingress,
            rule.egress,
            rule.remote_field,
            rule.remote_prefix,
        )
        if key in physical_seen:
            conflicts.append(
                PayloadForwardRuleConflict(
                    rule.handle,
                    "duplicate physical forward rule",
                )
            )
            continue
        physical_seen.add(key)
        unique.append(rule)

    current = tuple(rule for rule in unique if not rule.stale)
    stale = tuple(rule for rule in unique if rule.stale)
    return PayloadForwardObservation(
        current=current,
        stale=stale,
        conflicts=tuple(conflicts),
    )


def _rule_payload(item: NftNamespaceObject) -> dict:
    try:
        row = json.loads(item.canonical_json)
    except (TypeError, ValueError):
        raise PayloadForwardObservationError(
            "invalid canonical forward rule JSON"
        ) from None
    if (
        not isinstance(row, dict)
        or set(row) != {"rule"}
        or not isinstance(row["rule"], dict)
    ):
        raise PayloadForwardObservationError(
            "invalid canonical forward rule shape"
        )
    return row["rule"]


def _decode_rule(
    payload: dict,
    by_name: dict[str, InterfaceIdentity],
    by_index: dict[int, InterfaceIdentity],
) -> ObservedPayloadForwardRule:
    allowed = {
        "family",
        "table",
        "chain",
        "handle",
        "comment",
        "expr",
    }
    if set(payload) - allowed:
        raise PayloadForwardObservationError(
            "unsupported forward rule fields"
        )
    if (
        payload.get("family"),
        payload.get("table"),
        payload.get("chain"),
    ) != ("ip", "vpn_gate", PAYLOAD_FORWARD_CHAIN):
        raise PayloadForwardObservationError(
            "wrong forward rule scope"
        )

    comment = payload.get("comment")
    if comment == PAYLOAD_FORWARD_NEW_COMMENT:
        kind = PayloadForwardRuleKind.NEW
    elif comment == PAYLOAD_FORWARD_RETURN_COMMENT:
        kind = PayloadForwardRuleKind.RETURN
    else:
        raise PayloadForwardObservationError(
            "missing/wrong forward rule owner comment"
        )

    expr = payload.get("expr")
    if not isinstance(expr, list) or len(expr) != 5:
        raise PayloadForwardObservationError(
            "forward rule must contain exactly five expressions"
        )

    _state_match(expr[0], kind)
    ingress = _interface_match(
        expr[1], "iif", by_name, by_index
    )
    egress = _interface_match(
        expr[2], "oif", by_name, by_index
    )
    remote_field, remote_prefix = _remote_match(expr[3])
    if expr[4] != {"accept": None}:
        raise PayloadForwardObservationError(
            "forward rule action must be plain accept"
        )

    return ObservedPayloadForwardRule(
        handle=payload["handle"],
        kind=kind,
        ingress=ingress,
        egress=egress,
        remote_field=remote_field,
        remote_prefix=remote_prefix,
    )


def _state_match(expr: object, kind: PayloadForwardRuleKind) -> None:
    if not isinstance(expr, dict) or set(expr) != {"match"}:
        raise PayloadForwardObservationError(
            "invalid conntrack state expression"
        )
    match = expr["match"]
    if not isinstance(match, dict) or set(match) != {
        "op",
        "left",
        "right",
    }:
        raise PayloadForwardObservationError(
            "invalid conntrack state match structure"
        )
    if (
        match["op"] != "in"
        or match["left"] != {"ct": {"key": "state"}}
    ):
        raise PayloadForwardObservationError(
            "invalid conntrack state match"
        )

    if kind is PayloadForwardRuleKind.NEW:
        expected: object = "new"
    else:
        expected = ["established", "related"]
    if match["right"] != expected:
        raise PayloadForwardObservationError(
            "unexpected conntrack state set for forward rule kind"
        )


def _interface_match(
    expr: object,
    key: str,
    by_name: dict[str, InterfaceIdentity],
    by_index: dict[int, InterfaceIdentity],
) -> InterfaceIdentity | int:
    if not isinstance(expr, dict) or set(expr) != {"match"}:
        raise PayloadForwardObservationError(
            f"invalid {key} match"
        )
    match = expr["match"]
    if not isinstance(match, dict) or set(match) != {
        "op",
        "left",
        "right",
    }:
        raise PayloadForwardObservationError(
            f"invalid {key} match structure"
        )
    if (
        match["op"] != "=="
        or match["left"] != {"meta": {"key": key}}
    ):
        raise PayloadForwardObservationError(
            f"invalid {key} match expression"
        )

    operand = match["right"]
    if type(operand) is not str or not operand:
        raise PayloadForwardObservationError(
            f"invalid {key} interface operand"
        )
    if operand.isascii() and operand.isdecimal():
        index = int(operand)
        if index <= 0:
            raise PayloadForwardObservationError(
                f"invalid {key} interface index"
            )
        return by_index.get(index, index)

    identity = by_name.get(operand)
    if identity is None:
        raise PayloadForwardObservationError(
            f"unresolved {key} interface name"
        )
    return identity


def _remote_match(
    expr: object,
) -> tuple[PayloadForwardRemoteField, IPv4Network]:
    if not isinstance(expr, dict) or set(expr) != {"match"}:
        raise PayloadForwardObservationError(
            "invalid remote-prefix match"
        )
    match = expr["match"]
    if not isinstance(match, dict) or set(match) != {
        "op",
        "left",
        "right",
    }:
        raise PayloadForwardObservationError(
            "invalid remote-prefix match structure"
        )
    if match["op"] != "==":
        raise PayloadForwardObservationError(
            "remote-prefix match must use equality"
        )

    left = match["left"]
    if left == {"payload": {"protocol": "ip", "field": "saddr"}}:
        field = PayloadForwardRemoteField.SOURCE
    elif left == {"payload": {"protocol": "ip", "field": "daddr"}}:
        field = PayloadForwardRemoteField.DESTINATION
    else:
        raise PayloadForwardObservationError(
            "remote-prefix match must use IPv4 saddr or daddr"
        )

    return field, _remote_prefix(match["right"])


def _remote_prefix(value: object) -> IPv4Network:
    if isinstance(value, str):
        if "/" in value:
            raise PayloadForwardObservationError(
                "string remote-prefix operand must be a plain IPv4 address"
            )
        try:
            address = IPv4Address(value)
        except ValueError:
            raise PayloadForwardObservationError(
                "invalid /32 IPv4 remote operand"
            ) from None
        return IPv4Network((address, 32))

    if not isinstance(value, dict) or set(value) != {"prefix"}:
        raise PayloadForwardObservationError(
            "unsupported remote-prefix operand"
        )
    prefix = value["prefix"]
    if (
        not isinstance(prefix, dict)
        or set(prefix) != {"addr", "len"}
    ):
        raise PayloadForwardObservationError(
            "invalid nft prefix object"
        )
    addr = prefix["addr"]
    length = prefix["len"]
    if not isinstance(addr, str) or type(length) is not int:
        raise PayloadForwardObservationError(
            "invalid nft prefix fields"
        )
    if not 0 <= length <= 31:
        raise PayloadForwardObservationError(
            "prefix object length must be in [0, 31]"
        )
    try:
        network = IPv4Network(f"{addr}/{length}", strict=True)
    except ValueError:
        raise PayloadForwardObservationError(
            "non-canonical or invalid IPv4 prefix object"
        ) from None
    return network
