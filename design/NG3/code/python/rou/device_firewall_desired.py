"""Exact lower desired data for ordered Device firewall structure.

No semantic predicate compilation and no external configuration grammar live here.
"""

from __future__ import annotations

from dataclasses import dataclass
import json

from .interface_identity import InterfaceIdentity
from .device_firewall_structure import DeviceFirewallRuleAction


class DeviceFirewallDesiredError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DeviceFirewallRuleSpec:
    match_expr_json: tuple[str, ...]
    action: DeviceFirewallRuleAction
    action_json: str
    terminal_fallthrough: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.match_expr_json, tuple):
            raise DeviceFirewallDesiredError(
                "match_expr_json must be a tuple"
            )
        canonical_matches: list[str] = []
        for value in self.match_expr_json:
            canonical_matches.append(
                _canonical_expression(value, required_key="match")
            )
        if not isinstance(self.action, DeviceFirewallRuleAction):
            raise DeviceFirewallDesiredError(
                "action must be DeviceFirewallRuleAction"
            )
        action_json = _canonical_action(self.action_json, self.action)

        if self.terminal_fallthrough:
            if canonical_matches:
                raise DeviceFirewallDesiredError(
                    "terminal fallthrough cannot have match expressions"
                )
            if self.action is not DeviceFirewallRuleAction.DROP:
                raise DeviceFirewallDesiredError(
                    "terminal fallthrough action must be DROP"
                )
            if action_json != '{"drop":null}':
                raise DeviceFirewallDesiredError(
                    "terminal fallthrough must use plain drop"
                )

        object.__setattr__(self, "match_expr_json", tuple(canonical_matches))
        object.__setattr__(self, "action_json", action_json)


@dataclass(frozen=True, slots=True)
class DeviceFirewallChainSpec:
    """One exact lower jump + owned child chain.

    child_chain_name is a lower realization identifier supplied by the caller;
    this type does not define how a production name is derived.
    """

    ingress: InterfaceIdentity
    egress: InterfaceIdentity
    child_chain_name: str
    rules: tuple[DeviceFirewallRuleSpec, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.ingress, InterfaceIdentity):
            raise DeviceFirewallDesiredError(
                "ingress must be InterfaceIdentity"
            )
        if not isinstance(self.egress, InterfaceIdentity):
            raise DeviceFirewallDesiredError(
                "egress must be InterfaceIdentity"
            )
        if (
            not isinstance(self.child_chain_name, str)
            or not self.child_chain_name
        ):
            raise DeviceFirewallDesiredError(
                "child_chain_name must be non-empty text"
            )
        if not isinstance(self.rules, tuple):
            raise DeviceFirewallDesiredError("rules must be a tuple")
        if not all(
            isinstance(rule, DeviceFirewallRuleSpec)
            for rule in self.rules
        ):
            raise DeviceFirewallDesiredError(
                "rules must contain DeviceFirewallRuleSpec"
            )

        fallthrough = [
            rule for rule in self.rules if rule.terminal_fallthrough
        ]
        if len(fallthrough) > 1:
            raise DeviceFirewallDesiredError(
                "at most one terminal fallthrough is allowed"
            )
        if fallthrough and self.rules[-1] is not fallthrough[0]:
            raise DeviceFirewallDesiredError(
                "terminal fallthrough must be the final rule"
            )


@dataclass(frozen=True, slots=True)
class DeviceFirewallDesiredState:
    chains: tuple[DeviceFirewallChainSpec, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.chains, tuple):
            raise DeviceFirewallDesiredError(
                "chains must be a tuple"
            )
        if not all(
            isinstance(chain, DeviceFirewallChainSpec)
            for chain in self.chains
        ):
            raise DeviceFirewallDesiredError(
                "chains must contain DeviceFirewallChainSpec"
            )

        names: set[str] = set()
        jumps: set[tuple[InterfaceIdentity, InterfaceIdentity]] = set()
        for chain in self.chains:
            if chain.child_chain_name in names:
                raise DeviceFirewallDesiredError(
                    "duplicate desired Device firewall child chain name"
                )
            names.add(chain.child_chain_name)

            jump_key = (chain.ingress, chain.egress)
            if jump_key in jumps:
                raise DeviceFirewallDesiredError(
                    "duplicate desired Device firewall jump pair"
                )
            jumps.add(jump_key)


def _canonical_expression(value: str, *, required_key: str) -> str:
    if not isinstance(value, str) or not value:
        raise DeviceFirewallDesiredError(
            "expression JSON must be non-empty text"
        )
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        raise DeviceFirewallDesiredError(
            "expression JSON is invalid"
        ) from None
    if not isinstance(parsed, dict) or set(parsed) != {required_key}:
        raise DeviceFirewallDesiredError(
            f"expression JSON must contain only {required_key!r}"
        )
    return json.dumps(parsed, sort_keys=True, separators=(",", ":"))


def _canonical_action(
    value: str,
    action: DeviceFirewallRuleAction,
) -> str:
    if not isinstance(value, str) or not value:
        raise DeviceFirewallDesiredError(
            "action_json must be non-empty text"
        )
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        raise DeviceFirewallDesiredError(
            "action_json is invalid"
        ) from None

    if action is DeviceFirewallRuleAction.RETURN:
        expected = {"return": None}
        if parsed != expected:
            raise DeviceFirewallDesiredError(
                "RETURN must use plain return action"
            )
    elif action is DeviceFirewallRuleAction.DROP:
        expected = {"drop": None}
        if parsed != expected:
            raise DeviceFirewallDesiredError(
                "DROP must use plain drop action"
            )
    else:
        if not isinstance(parsed, dict) or set(parsed) != {"reject"}:
            raise DeviceFirewallDesiredError(
                "REJECT must use one reject action"
            )
        reject = parsed["reject"]
        if reject is not None and not isinstance(reject, dict):
            raise DeviceFirewallDesiredError(
                "REJECT payload must be null or object"
            )

    return json.dumps(parsed, sort_keys=True, separators=(",", ":"))
