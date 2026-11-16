"""Atomic reconciliation planning for EXP-046-backed local publication rules."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address

from .interface_identity import InterfaceIdentity
from .local_publication_observation import (
    LocalPublicationComparison,
    ObservedLocalPublicationRule,
)
from .local_publication_policy import (
    LocalPublicationDesiredState,
    LocalPublicationHook,
    LocalPublicationRuleSpec,
    PublicationProtocol,
)


@dataclass(frozen=True, slots=True)
class LocalPublicationEndpointSpec:
    protocol: PublicationProtocol
    host_boundary: InterfaceIdentity
    local_address: IPv4Address
    local_port: int

    @property
    def input_rule(self) -> LocalPublicationRuleSpec:
        return LocalPublicationRuleSpec(
            LocalPublicationHook.INPUT,
            self.protocol,
            self.host_boundary,
            self.local_address,
            self.local_port,
        )

    @property
    def output_rule(self) -> LocalPublicationRuleSpec:
        return LocalPublicationRuleSpec(
            LocalPublicationHook.OUTPUT,
            self.protocol,
            self.host_boundary,
            self.local_address,
            self.local_port,
        )


@dataclass(frozen=True, slots=True)
class LocalPublicationMutationStep:
    """One endpoint-scoped nft transaction.

    delete_handles are applied first in the same nft batch. add_rules then adds
    the desired missing exact rules for that endpoint. Either side may be empty,
    but the step itself must change physical state.
    """

    delete_handles: tuple[int, ...]
    add_rules: tuple[LocalPublicationRuleSpec, ...]

    def __post_init__(self) -> None:
        if not self.delete_handles and not self.add_rules:
            raise ValueError("local publication mutation step must change state")
        if len(set(self.delete_handles)) != len(self.delete_handles):
            raise ValueError("duplicate local publication delete handle")
        if any(type(handle) is not int or handle < 0 for handle in self.delete_handles):
            raise ValueError("invalid local publication delete handle")
        if not all(
            isinstance(rule, LocalPublicationRuleSpec)
            for rule in self.add_rules
        ):
            raise ValueError("add_rules must contain LocalPublicationRuleSpec")


class LocalPublicationPlanError(ValueError):
    pass


def select_local_publication_step(
    comparison: LocalPublicationComparison,
    desired: LocalPublicationDesiredState,
) -> LocalPublicationMutationStep | None:
    """Choose one endpoint-scoped atomic repair transaction."""
    if not isinstance(comparison, LocalPublicationComparison):
        raise LocalPublicationPlanError(
            "comparison must be LocalPublicationComparison"
        )
    if not isinstance(desired, LocalPublicationDesiredState):
        raise LocalPublicationPlanError(
            "desired must be LocalPublicationDesiredState"
        )
    if comparison.conflicts:
        raise LocalPublicationPlanError(
            "local publication comparison has conflicts"
        )
    if comparison.desired_confirmed:
        return None

    stale_groups: dict[tuple[object, ...], list[ObservedLocalPublicationRule]] = {}
    for rule in comparison.stale:
        key = (
            rule.protocol,
            rule.host_boundary,
            rule.local_address,
            rule.local_port,
        )
        stale_groups.setdefault(key, []).append(rule)

    if stale_groups:
        key = sorted(
            stale_groups,
            key=lambda value: (
                str(value[0]),
                repr(value[1]),
                int(value[2]),
                value[3],
            ),
        )[0]
        rules = stale_groups[key]
        return LocalPublicationMutationStep(
            delete_handles=tuple(sorted(rule.handle for rule in rules)),
            add_rules=(),
        )

    missing_by_endpoint: dict[tuple[object, ...], list[LocalPublicationRuleSpec]] = {}
    for rule in comparison.missing:
        key = (
            rule.protocol,
            rule.host_boundary,
            rule.local_address,
            rule.local_port,
        )
        missing_by_endpoint.setdefault(key, []).append(rule)

    if not missing_by_endpoint:
        raise LocalPublicationPlanError(
            "local publication desired state is not confirmed but no repair step exists"
        )

    key = sorted(
        missing_by_endpoint,
        key=lambda value: (
            str(value[0]),
            value[1].ifindex,
            int(value[2]),
            value[3],
        ),
    )[0]
    rules = tuple(
        sorted(
            missing_by_endpoint[key],
            key=lambda rule: 0 if rule.hook is LocalPublicationHook.OUTPUT else 1,
        )
    )
    return LocalPublicationMutationStep(
        delete_handles=(),
        add_rules=rules,
    )
