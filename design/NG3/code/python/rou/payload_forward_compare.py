"""Pure actual-vs-desired comparison for strict payload_forward rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .interface_identity import InterfaceIdentity
from .nft_namespace_inventory import NftNamespaceObservation
from .payload_forward_desired import (
    PayloadForwardDesiredState,
    PayloadForwardRuleSpec,
)
from .payload_forward_observation import (
    ObservedPayloadForwardRule,
    PayloadForwardRuleConflict,
    observe_payload_forward,
)


class PayloadForwardComparisonError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PayloadForwardComparison:
    confirmed: tuple[PayloadForwardRuleSpec, ...]
    missing: tuple[PayloadForwardRuleSpec, ...]
    stale: tuple[ObservedPayloadForwardRule, ...]
    conflicts: tuple[PayloadForwardRuleConflict, ...]

    @property
    def desired_confirmed(self) -> bool:
        """Exact lower desired state is observed; no mutation authority implied."""
        return (
            not self.missing
            and not self.stale
            and not self.conflicts
        )


def compare_payload_forward(
    observation: NftNamespaceObservation,
    interfaces: Iterable[InterfaceIdentity],
    desired: PayloadForwardDesiredState,
) -> PayloadForwardComparison:
    """Compare strict owner-shaped rules to exact lower desired data.

    This does not compile Profile/Device semantics and does not authorize nft
    writes or forwarding activation.
    """
    if not isinstance(desired, PayloadForwardDesiredState):
        raise PayloadForwardComparisonError(
            "desired must be PayloadForwardDesiredState"
        )

    current_interfaces = tuple(interfaces)
    observed = observe_payload_forward(
        observation,
        current_interfaces,
    )
    current_set = set(current_interfaces)
    for rule in desired.rules:
        if (
            rule.ingress not in current_set
            or rule.egress not in current_set
        ):
            raise PayloadForwardComparisonError(
                "desired forward endpoints are not current"
            )

    expected = {
        _spec_key(rule): rule
        for rule in desired.rules
    }
    confirmed_keys: set[tuple[object, ...]] = set()
    stale: list[ObservedPayloadForwardRule] = list(
        observed.stale_identity_rules
    )

    for rule in observed.current_identity_rules:
        key = _observed_key(rule)
        if key in expected:
            confirmed_keys.add(key)
        else:
            stale.append(rule)

    confirmed = tuple(
        rule
        for rule in desired.rules
        if _spec_key(rule) in confirmed_keys
    )
    missing = tuple(
        rule
        for rule in desired.rules
        if _spec_key(rule) not in confirmed_keys
    )
    return PayloadForwardComparison(
        confirmed=confirmed,
        missing=missing,
        stale=tuple(stale),
        conflicts=observed.conflicts,
    )


def _spec_key(rule: PayloadForwardRuleSpec) -> tuple[object, ...]:
    return (
        rule.kind,
        rule.ingress,
        rule.egress,
        rule.remote_field,
        rule.remote_prefix,
    )


def _observed_key(rule: ObservedPayloadForwardRule) -> tuple[object, ...]:
    return (
        rule.kind,
        rule.ingress,
        rule.egress,
        rule.remote_field,
        rule.remote_prefix,
    )
