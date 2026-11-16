"""Atomic reconciliation planning for EXP-046-backed local publication rules."""

from __future__ import annotations

from dataclasses import dataclass
from .local_publication_observation import LocalPublicationComparison
from .local_publication_policy import (
    LocalPublicationDesiredState,
    LocalPublicationHook,
    LocalPublicationRuleSpec,
)


@dataclass(frozen=True, order=True, slots=True)
class LocalPublicationDeleteRef:
    hook: LocalPublicationHook
    handle: int

    def __post_init__(self) -> None:
        if not isinstance(self.hook, LocalPublicationHook):
            raise ValueError("hook must be LocalPublicationHook")
        if type(self.handle) is not int or self.handle < 0:
            raise ValueError("invalid local publication delete handle")


@dataclass(frozen=True, slots=True)
class LocalPublicationMutationStep:
    """One publication-owner full-diff nft transaction.

    Stale exact delete refs are applied first in the same nft batch, followed
    by all missing exact desired rules. Either side may be empty, but the step
    itself must change physical state.
    """

    delete_rules: tuple[LocalPublicationDeleteRef, ...]
    add_rules: tuple[LocalPublicationRuleSpec, ...]

    def __post_init__(self) -> None:
        if not self.delete_rules and not self.add_rules:
            raise ValueError("local publication mutation step must change state")
        if not all(
            isinstance(ref, LocalPublicationDeleteRef)
            for ref in self.delete_rules
        ):
            raise ValueError("delete_rules must contain LocalPublicationDeleteRef")
        if len(set(self.delete_rules)) != len(self.delete_rules):
            raise ValueError("duplicate local publication delete ref")
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
    """Choose one atomic full-diff publication-local repair transaction.

    EXP-047 proves nft batch rollback for the complete local publication diff.
    All stale exact-handle deletions and all missing desired additions therefore
    belong to one transaction. No old->new endpoint pairing is inferred.
    """
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

    delete_rules = tuple(
        sorted(
            (
                LocalPublicationDeleteRef(rule.hook, rule.handle)
                for rule in comparison.stale
            ),
            key=lambda ref: (
                ref.hook.value,
                ref.handle,
            ),
        )
    )
    add_rules = tuple(
        sorted(
            comparison.missing,
            key=lambda rule: (
                rule.protocol.value,
                rule.host_boundary.ifindex,
                int(rule.local_address),
                rule.local_port,
                0 if rule.hook is LocalPublicationHook.OUTPUT else 1,
            ),
        )
    )

    if not delete_rules and not add_rules:
        raise LocalPublicationPlanError(
            "local publication desired state is not confirmed but full diff is empty"
        )

    return LocalPublicationMutationStep(
        delete_rules=delete_rules,
        add_rules=add_rules,
    )
