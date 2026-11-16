"""Exact lower desired data for payload_forward; no semantic policy compilation."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Network

from .interface_identity import InterfaceIdentity
from .payload_forward_observation import (
    PayloadForwardRemoteField,
    PayloadForwardRuleKind,
)


class PayloadForwardDesiredError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PayloadForwardRuleSpec:
    kind: PayloadForwardRuleKind
    ingress: InterfaceIdentity
    egress: InterfaceIdentity
    remote_field: PayloadForwardRemoteField
    remote_prefix: IPv4Network

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PayloadForwardRuleKind):
            raise PayloadForwardDesiredError(
                "kind must be PayloadForwardRuleKind"
            )
        if not isinstance(self.ingress, InterfaceIdentity):
            raise PayloadForwardDesiredError(
                "ingress must be InterfaceIdentity"
            )
        if not isinstance(self.egress, InterfaceIdentity):
            raise PayloadForwardDesiredError(
                "egress must be InterfaceIdentity"
            )
        if not isinstance(self.remote_field, PayloadForwardRemoteField):
            raise PayloadForwardDesiredError(
                "remote_field must be PayloadForwardRemoteField"
            )
        if not isinstance(self.remote_prefix, IPv4Network):
            raise PayloadForwardDesiredError(
                "remote_prefix must be IPv4Network"
            )


@dataclass(frozen=True, slots=True)
class PayloadForwardDesiredState:
    rules: tuple[PayloadForwardRuleSpec, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.rules, tuple):
            raise PayloadForwardDesiredError(
                "rules must be a tuple"
            )
        seen: set[PayloadForwardRuleSpec] = set()
        for rule in self.rules:
            if not isinstance(rule, PayloadForwardRuleSpec):
                raise PayloadForwardDesiredError(
                    "rules must contain PayloadForwardRuleSpec"
                )
            if rule in seen:
                raise PayloadForwardDesiredError(
                    "duplicate desired physical forward rule"
                )
            seen.add(rule)

        object.__setattr__(
            self,
            "rules",
            tuple(sorted(self.rules, key=_rule_sort_key)),
        )


def _rule_sort_key(rule: PayloadForwardRuleSpec) -> tuple[object, ...]:
    return (
        rule.kind.value,
        rule.ingress.ifindex,
        rule.ingress.ifname,
        rule.egress.ifindex,
        rule.egress.ifname,
        rule.remote_field.value,
        int(rule.remote_prefix.network_address),
        rule.remote_prefix.prefixlen,
    )
