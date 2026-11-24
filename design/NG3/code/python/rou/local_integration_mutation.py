"""Atomic reconciliation planning for supported-integration local transport rules."""

from __future__ import annotations

from dataclasses import dataclass

from .local_integration_observation import IntegrationLocalComparison
from .local_integration_policy import (
    IntegrationLocalDesiredState,
    IntegrationLocalHook,
    IntegrationLocalRuleSpec,
)


@dataclass(frozen=True, order=True, slots=True)
class IntegrationLocalDeleteRef:
    hook: IntegrationLocalHook
    handle: int


@dataclass(frozen=True, slots=True)
class IntegrationLocalMutationStep:
    delete_rules: tuple[IntegrationLocalDeleteRef, ...]
    add_rules: tuple[IntegrationLocalRuleSpec, ...]

    def __post_init__(self) -> None:
        if not self.delete_rules and not self.add_rules:
            raise ValueError("integration-local mutation step must change state")


class IntegrationLocalPlanError(ValueError):
    pass


def select_integration_local_step(
    comparison: IntegrationLocalComparison,
    desired: IntegrationLocalDesiredState,
) -> IntegrationLocalMutationStep | None:
    if not isinstance(comparison, IntegrationLocalComparison):
        raise IntegrationLocalPlanError("comparison must be IntegrationLocalComparison")
    if not isinstance(desired, IntegrationLocalDesiredState):
        raise IntegrationLocalPlanError("desired must be IntegrationLocalDesiredState")
    if comparison.conflicts:
        raise IntegrationLocalPlanError("integration-local comparison has conflicts")
    if comparison.desired_confirmed:
        return None
    delete_rules = tuple(
        sorted(
            (
                IntegrationLocalDeleteRef(rule.hook, rule.handle)
                for rule in comparison.stale
            ),
            key=lambda item: (item.hook.value, item.handle),
        )
    )
    add_rules = tuple(
        sorted(
            comparison.missing,
            key=lambda rule: (
                rule.protocol.value,
                rule.host_boundary.ifindex,
                int(rule.local_address),
                int(rule.remote_address),
                rule.remote_port,
                -1 if rule.local_port is None else rule.local_port,
                rule.hook.value,
            ),
        )
    )
    if not delete_rules and not add_rules:
        raise IntegrationLocalPlanError("integration-local full diff is empty")
    return IntegrationLocalMutationStep(delete_rules, add_rules)
