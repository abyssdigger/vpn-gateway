"""Structural read-only observation for ordered Device firewall nft objects.

This layer proves owner shape, current interface identity and physical rule order.
It deliberately does not interpret the semantic meaning of match predicates and
does not authorize mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Iterable

from .interface_identity import InterfaceIdentity
from .nft_namespace_inventory import NftNamespaceObject, NftNamespaceObservation
from .nft_payload_scaffold import (
    PAYLOAD_FORWARD_CHAIN,
    PAYLOAD_NFT_SCAFFOLD,
    compare_payload_nft_scaffold,
)


DEVICE_FIREWALL_CHILD_COMMENT = "vpn-gate:ng3:device-fw-child-v1"
DEVICE_FIREWALL_JUMP_COMMENT = "vpn-gate:ng3:device-fw-jump-v1"
DEVICE_FIREWALL_RULE_COMMENT = "vpn-gate:ng3:device-fw-rule-v1"
DEVICE_FIREWALL_FALLTHROUGH_COMMENT = "vpn-gate:ng3:device-fw-fallthrough-v1"


class DeviceFirewallStructureError(ValueError):
    pass


class DeviceFirewallRuleAction(str, Enum):
    RETURN = "return"
    DROP = "drop"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class ObservedDeviceFirewallJump:
    handle: int
    source_order: int
    ingress: InterfaceIdentity | int
    egress: InterfaceIdentity | int
    target_chain: str

    @property
    def stale(self) -> bool:
        return type(self.ingress) is int or type(self.egress) is int


@dataclass(frozen=True, slots=True)
class ObservedDeviceFirewallRule:
    handle: int
    source_order: int
    chain_name: str
    match_expr_json: tuple[str, ...]
    action: DeviceFirewallRuleAction
    action_json: str
    terminal_fallthrough: bool


@dataclass(frozen=True, slots=True)
class ObservedDeviceFirewallChain:
    name: str
    handle: int | None
    source_order: int
    rules: tuple[ObservedDeviceFirewallRule, ...]


@dataclass(frozen=True, slots=True)
class DeviceFirewallStructureConflict:
    handle: int | None
    chain_name: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class DeviceFirewallStructureObservation:
    chains: tuple[ObservedDeviceFirewallChain, ...]
    current_jumps: tuple[ObservedDeviceFirewallJump, ...]
    stale_jumps: tuple[ObservedDeviceFirewallJump, ...]
    conflicts: tuple[DeviceFirewallStructureConflict, ...]

    @property
    def conflict_free(self) -> bool:
        return not self.conflicts


def observe_device_firewall_structure(
    observation: NftNamespaceObservation,
    interfaces: Iterable[InterfaceIdentity],
) -> DeviceFirewallStructureObservation:
    """Observe Device firewall child chains and jumps without mutation.

    Match predicates are preserved as exact canonical JSON but are not assigned
    product semantics here. This unit is therefore not sufficient deletion or
    mutation authority by itself.
    """
    if not isinstance(observation, NftNamespaceObservation):
        raise DeviceFirewallStructureError(
            "observation must be NftNamespaceObservation"
        )

    scaffold = compare_payload_nft_scaffold(observation)
    if not scaffold.scaffold_confirmed:
        raise DeviceFirewallStructureError(
            "payload nft table/scaffold ownership is not confirmed"
        )

    by_name: dict[str, InterfaceIdentity] = {}
    by_index: dict[int, InterfaceIdentity] = {}
    for identity in interfaces:
        if not isinstance(identity, InterfaceIdentity):
            raise DeviceFirewallStructureError(
                "inventory must contain InterfaceIdentity"
            )
        if identity.ifname in by_name or identity.ifindex in by_index:
            raise DeviceFirewallStructureError(
                "ambiguous current interface inventory"
            )
        by_name[identity.ifname] = identity
        by_index[identity.ifindex] = identity

    child_meta: dict[str, tuple[int | None, int]] = {}
    conflicts: list[DeviceFirewallStructureConflict] = []

    for item in observation.objects:
        if item.kind != "chain":
            continue
        payload = _payload(item, "chain")
        if payload.get("comment") != DEVICE_FIREWALL_CHILD_COMMENT:
            continue
        try:
            name, handle = _decode_child_chain(payload)
        except DeviceFirewallStructureError as exc:
            conflicts.append(
                DeviceFirewallStructureConflict(
                    handle=_valid_handle_or_none(payload.get("handle")),
                    chain_name=(
                        payload.get("name")
                        if isinstance(payload.get("name"), str)
                        else None
                    ),
                    reason=str(exc),
                )
            )
            continue
        if name in child_meta:
            conflicts.append(
                DeviceFirewallStructureConflict(
                    handle=handle,
                    chain_name=name,
                    reason="duplicate Device firewall child chain",
                )
            )
            continue
        child_meta[name] = (handle, item.source_order)

    rule_rows: dict[str, list[tuple[NftNamespaceObject, dict]]] = {
        name: [] for name in child_meta
    }
    jumps: list[ObservedDeviceFirewallJump] = []

    for item in observation.objects:
        if item.kind != "rule":
            continue
        payload = _payload(item, "rule")
        chain = payload.get("chain")
        if chain == PAYLOAD_FORWARD_CHAIN and (
            payload.get("comment") == DEVICE_FIREWALL_JUMP_COMMENT
        ):
            try:
                jumps.append(
                    _decode_jump(
                        payload,
                        item.source_order,
                        by_name,
                        by_index,
                    )
                )
            except DeviceFirewallStructureError as exc:
                conflicts.append(
                    DeviceFirewallStructureConflict(
                        handle=_valid_handle_or_none(payload.get("handle")),
                        chain_name=PAYLOAD_FORWARD_CHAIN,
                        reason=str(exc),
                    )
                )
            continue

        if isinstance(chain, str) and chain in rule_rows:
            rule_rows[chain].append((item, payload))

    observed_chains: list[ObservedDeviceFirewallChain] = []
    for name, (handle, source_order) in child_meta.items():
        decoded: list[ObservedDeviceFirewallRule] = []
        rows = sorted(rule_rows[name], key=lambda pair: pair[0].source_order)
        for item, payload in rows:
            try:
                decoded.append(
                    _decode_child_rule(payload, item.source_order, name)
                )
            except DeviceFirewallStructureError as exc:
                conflicts.append(
                    DeviceFirewallStructureConflict(
                        handle=_valid_handle_or_none(payload.get("handle")),
                        chain_name=name,
                        reason=str(exc),
                    )
                )

        fallthrough = [
            rule for rule in decoded if rule.terminal_fallthrough
        ]
        if len(fallthrough) > 1:
            conflicts.append(
                DeviceFirewallStructureConflict(
                    handle=None,
                    chain_name=name,
                    reason="multiple Device firewall terminal fallthrough rules",
                )
            )
        elif fallthrough and decoded[-1] != fallthrough[0]:
            conflicts.append(
                DeviceFirewallStructureConflict(
                    handle=fallthrough[0].handle,
                    chain_name=name,
                    reason="Device firewall terminal fallthrough is not last",
                )
            )

        observed_chains.append(
            ObservedDeviceFirewallChain(
                name=name,
                handle=handle,
                source_order=source_order,
                rules=tuple(decoded),
            )
        )

    child_names = set(child_meta)
    for jump in jumps:
        if jump.target_chain not in child_names:
            conflicts.append(
                DeviceFirewallStructureConflict(
                    handle=jump.handle,
                    chain_name=PAYLOAD_FORWARD_CHAIN,
                    reason="Device firewall jump target is not an owned child chain",
                )
            )

    current_jumps = tuple(j for j in jumps if not j.stale)
    stale_jumps = tuple(j for j in jumps if j.stale)

    return DeviceFirewallStructureObservation(
        chains=tuple(sorted(observed_chains, key=lambda c: c.source_order)),
        current_jumps=tuple(sorted(current_jumps, key=lambda j: j.source_order)),
        stale_jumps=tuple(sorted(stale_jumps, key=lambda j: j.source_order)),
        conflicts=tuple(conflicts),
    )


def _payload(item: NftNamespaceObject, kind: str) -> dict:
    try:
        row = json.loads(item.canonical_json)
    except (TypeError, ValueError):
        raise DeviceFirewallStructureError(
            f"invalid canonical {kind} JSON"
        ) from None
    if (
        not isinstance(row, dict)
        or set(row) != {kind}
        or not isinstance(row[kind], dict)
    ):
        raise DeviceFirewallStructureError(
            f"invalid canonical {kind} shape"
        )
    return row[kind]


def _decode_child_chain(payload: dict) -> tuple[str, int | None]:
    allowed = {
        "family",
        "table",
        "name",
        "handle",
        "comment",
    }
    if set(payload) - allowed:
        raise DeviceFirewallStructureError(
            "Device firewall child chain has unsupported fields"
        )
    if (payload.get("family"), payload.get("table")) != ("ip", "vpn_gate"):
        raise DeviceFirewallStructureError(
            "Device firewall child chain has wrong scope"
        )
    name = payload.get("name")
    if not isinstance(name, str) or not name:
        raise DeviceFirewallStructureError(
            "Device firewall child chain name is invalid"
        )
    if name in {spec.name for spec in PAYLOAD_NFT_SCAFFOLD}:
        raise DeviceFirewallStructureError(
            "Device firewall child chain collides with invariant scaffold"
        )
    if payload.get("comment") != DEVICE_FIREWALL_CHILD_COMMENT:
        raise DeviceFirewallStructureError(
            "Device firewall child chain owner marker mismatch"
        )
    handle = payload.get("handle")
    if handle is not None and (
        type(handle) is not int or handle < 0
    ):
        raise DeviceFirewallStructureError(
            "Device firewall child chain handle is invalid"
        )
    return name, handle


def _decode_jump(
    payload: dict,
    source_order: int,
    by_name: dict[str, InterfaceIdentity],
    by_index: dict[int, InterfaceIdentity],
) -> ObservedDeviceFirewallJump:
    allowed = {
        "family",
        "table",
        "chain",
        "handle",
        "comment",
        "expr",
    }
    if set(payload) - allowed:
        raise DeviceFirewallStructureError(
            "Device firewall jump has unsupported fields"
        )
    if (
        payload.get("family"),
        payload.get("table"),
        payload.get("chain"),
        payload.get("comment"),
    ) != (
        "ip",
        "vpn_gate",
        PAYLOAD_FORWARD_CHAIN,
        DEVICE_FIREWALL_JUMP_COMMENT,
    ):
        raise DeviceFirewallStructureError(
            "Device firewall jump scope/marker mismatch"
        )
    handle = _required_handle(payload.get("handle"), "jump")
    expr = payload.get("expr")
    if not isinstance(expr, list) or len(expr) != 3:
        raise DeviceFirewallStructureError(
            "Device firewall jump must contain exactly iif, oif and jump expressions"
        )
    ingress = _interface_match(expr[0], "iif", by_name, by_index)
    egress = _interface_match(expr[1], "oif", by_name, by_index)
    target = expr[2]
    if not isinstance(target, dict) or set(target) != {"jump"}:
        raise DeviceFirewallStructureError(
            "Device firewall jump action is invalid"
        )
    jump = target["jump"]
    if (
        not isinstance(jump, dict)
        or set(jump) != {"target"}
        or not isinstance(jump["target"], str)
        or not jump["target"]
    ):
        raise DeviceFirewallStructureError(
            "Device firewall jump target is invalid"
        )
    return ObservedDeviceFirewallJump(
        handle=handle,
        source_order=source_order,
        ingress=ingress,
        egress=egress,
        target_chain=jump["target"],
    )


def _decode_child_rule(
    payload: dict,
    source_order: int,
    chain_name: str,
) -> ObservedDeviceFirewallRule:
    allowed = {
        "family",
        "table",
        "chain",
        "handle",
        "comment",
        "expr",
    }
    if set(payload) - allowed:
        raise DeviceFirewallStructureError(
            "Device firewall rule has unsupported fields"
        )
    if (
        payload.get("family"),
        payload.get("table"),
        payload.get("chain"),
    ) != ("ip", "vpn_gate", chain_name):
        raise DeviceFirewallStructureError(
            "Device firewall rule has wrong scope"
        )
    handle = _required_handle(payload.get("handle"), "rule")
    comment = payload.get("comment")
    expr = payload.get("expr")
    if not isinstance(expr, list) or not expr:
        raise DeviceFirewallStructureError(
            "Device firewall rule expressions are missing"
        )

    if comment == DEVICE_FIREWALL_FALLTHROUGH_COMMENT:
        if expr != [{"drop": None}]:
            raise DeviceFirewallStructureError(
                "Device firewall terminal fallthrough must be plain drop"
            )
        return ObservedDeviceFirewallRule(
            handle=handle,
            source_order=source_order,
            chain_name=chain_name,
            match_expr_json=(),
            action=DeviceFirewallRuleAction.DROP,
            action_json=_canonical(expr[-1]),
            terminal_fallthrough=True,
        )

    if comment != DEVICE_FIREWALL_RULE_COMMENT:
        raise DeviceFirewallStructureError(
            "Device firewall rule owner marker mismatch"
        )

    action = _action(expr[-1])
    matches = expr[:-1]
    for item in matches:
        if not isinstance(item, dict) or set(item) != {"match"}:
            raise DeviceFirewallStructureError(
                "Device firewall explicit rule may contain only match expressions before action"
            )

    return ObservedDeviceFirewallRule(
        handle=handle,
        source_order=source_order,
        chain_name=chain_name,
        match_expr_json=tuple(_canonical(item) for item in matches),
        action=action,
        action_json=_canonical(expr[-1]),
        terminal_fallthrough=False,
    )


def _action(value: object) -> DeviceFirewallRuleAction:
    if value == {"return": None}:
        return DeviceFirewallRuleAction.RETURN
    if value == {"drop": None}:
        return DeviceFirewallRuleAction.DROP
    if isinstance(value, dict) and set(value) == {"reject"}:
        reject = value["reject"]
        if reject is not None and not isinstance(reject, dict):
            raise DeviceFirewallStructureError(
                "Device firewall reject action is invalid"
            )
        return DeviceFirewallRuleAction.REJECT
    raise DeviceFirewallStructureError(
        "Device firewall rule action is not return/drop/reject"
    )


def _interface_match(
    expr: object,
    key: str,
    by_name: dict[str, InterfaceIdentity],
    by_index: dict[int, InterfaceIdentity],
) -> InterfaceIdentity | int:
    if not isinstance(expr, dict) or set(expr) != {"match"}:
        raise DeviceFirewallStructureError(
            f"invalid Device firewall {key} match"
        )
    match = expr["match"]
    if not isinstance(match, dict) or set(match) != {
        "op",
        "left",
        "right",
    }:
        raise DeviceFirewallStructureError(
            f"invalid Device firewall {key} match structure"
        )
    if (
        match["op"] != "=="
        or match["left"] != {"meta": {"key": key}}
    ):
        raise DeviceFirewallStructureError(
            f"invalid Device firewall {key} match expression"
        )
    operand = match["right"]
    if type(operand) is not str or not operand:
        raise DeviceFirewallStructureError(
            f"invalid Device firewall {key} interface operand"
        )
    if operand.isascii() and operand.isdecimal():
        index = int(operand)
        if index <= 0:
            raise DeviceFirewallStructureError(
                f"invalid Device firewall {key} interface index"
            )
        return by_index.get(index, index)
    identity = by_name.get(operand)
    if identity is None:
        raise DeviceFirewallStructureError(
            f"unresolved Device firewall {key} interface name"
        )
    return identity


def _required_handle(value: object, noun: str) -> int:
    if type(value) is not int or value < 0:
        raise DeviceFirewallStructureError(
            f"Device firewall {noun} handle is invalid"
        )
    return value


def _valid_handle_or_none(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
