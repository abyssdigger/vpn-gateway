# VPN-GATE NG3 — Pure route-priority move planner code review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-post-closure-implementation-readiness-40m`

## Scope

Reviewed:

- `design/NG3/code/python/rou/route_priority.py`;
- `design/NG3/code/python/rou/tests/test_route_priority.py`;
- EXP-027;
- current pure-priority transition architecture.

## Evidence

Combined rootless suite:

```text
59 tests
PASS
```

Python compilation passed.

## 1. Transition-class boundary

PASS.

The planner requires identical current/desired logical path membership.

Membership change is rejected and remains a structural fail-closed transition responsibility.

## 2. Make-before-break primitive

PASS.

Every emitted `RoutePriorityMove` targets a metric that is free in the planner's simulated
current assignment.

Execution semantics remain:

```text
add same path at to_metric
delete same path at from_metric
```

Therefore the planner itself never requires delete-before-add.

## 3. Emergent working metric

PASS.

The planner does not model a semantic/configured hole.

It receives a caller-owned ordinary metric set and infers currently free metrics.

A cycle in an all-live assignment can be broken by the next unused metric, matching EXP-027.

## 4. Direct target and permutation cycles

PASS.

If a desired metric is already free, the corresponding path is moved directly.

If all desired positions are occupied by the wrong paths, the planner deterministically moves
the occupant of the lowest blocked desired metric to the lowest free scratch metric and then
continues.

Two-path swap and three-path cycle tests reach exact desired assignments.

## 5. Validation

PASS.

Rejected:

- membership changes;
- duplicate current metric assignment;
- duplicate desired metric assignment;
- non-integer/negative metrics;
- current/desired metric outside owned working set;
- permutation cycle with no free owned metric.

## 6. Determinism

PASS.

Working metric input iteration order does not affect the plan.

Tie decisions use stable metric and `LogicalPathId` ordering.

## 7. Scope boundary

The planner does not decide:

- desired availability order;
- metric allocation policy;
- Linux route syntax;
- transaction concurrency;
- execution success;
- final observation verification.

Those remain higher/lower adjacent contracts.

## Verdict

**PASS — PURE ROUTE-PRIORITY MOVE PLANNER ACCEPTED.**
