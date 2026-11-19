"""Atomic full-diff planning for probe-owned local nft admission."""

from __future__ import annotations

from dataclasses import dataclass

from .probe_local_observation import ProbeLocalComparison
from .probe_policy import ProbeLocalHook, ProbeLocalRuleSpec


@dataclass(frozen=True, order=True, slots=True)
class ProbeLocalDeleteRef:
    hook: ProbeLocalHook
    handle: int

    def __post_init__(self) -> None:
        if not isinstance(self.hook, ProbeLocalHook):
            raise ValueError("hook must be ProbeLocalHook")
        if type(self.handle) is not int or self.handle < 0:
            raise ValueError("invalid probe-local delete handle")


@dataclass(frozen=True, slots=True)
class ProbeLocalMutationStep:
    delete_rules: tuple[ProbeLocalDeleteRef, ...]
    add_rules: tuple[ProbeLocalRuleSpec, ...]

    def __post_init__(self) -> None:
        if not self.delete_rules and not self.add_rules:
            raise ValueError("probe-local mutation step must change state")
        if not all(isinstance(ref, ProbeLocalDeleteRef) for ref in self.delete_rules):
            raise ValueError("delete_rules must contain ProbeLocalDeleteRef")
        if len(set(self.delete_rules)) != len(self.delete_rules):
            raise ValueError("duplicate probe-local delete ref")
        if not all(isinstance(rule, ProbeLocalRuleSpec) for rule in self.add_rules):
            raise ValueError("add_rules must contain ProbeLocalRuleSpec")


class ProbeLocalPlanError(ValueError):
    pass


def select_probe_local_step(
    comparison: ProbeLocalComparison,
) -> ProbeLocalMutationStep | None:
    if not isinstance(comparison, ProbeLocalComparison):
        raise ProbeLocalPlanError("comparison must be ProbeLocalComparison")
    if comparison.conflicts:
        raise ProbeLocalPlanError("probe-local comparison has conflicts")
    if comparison.desired_confirmed:
        return None

    delete_rules = tuple(
        sorted(
            (
                ProbeLocalDeleteRef(rule.hook, rule.handle)
                for rule in comparison.stale
            ),
            key=lambda ref: (ref.hook.value, ref.handle),
        )
    )
    add_rules = tuple(
        sorted(
            comparison.missing,
            key=lambda rule: (
                rule.hook.value,
                rule.endpoint.ifindex,
                int(rule.target),
                rule.conntrack_mark,
                -1 if rule.process_uid is None else rule.process_uid,
            ),
        )
    )
    if not delete_rules and not add_rules:
        raise ProbeLocalPlanError(
            "probe-local desired state is not confirmed but full diff is empty"
        )
    return ProbeLocalMutationStep(delete_rules, add_rules)
