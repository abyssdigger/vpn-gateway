# VPN-GATE NG3 — Availability priority transformation code review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-post-closure-implementation-readiness-40m`

## Scope

Reviewed:

- `design/NG3/code/python/rou/availability_priority.py`;
- `design/NG3/code/python/rou/tests/test_availability_priority.py`;
- current `AvailabilityPriorityCalculator` architecture contract.

## Evidence

The bounded unit contains 10 rootless test cases covering normal and invalid inputs.
The stable-partition transition was additionally checked independently during review.

## 1. Membership invariant

PASS.

The output contains exactly the configured logical path membership.

Problem flags cannot add or remove a path.

Unknown problem path IDs are rejected.

## 2. Stable configured ordering

PASS.

The transformation is:

```text
configured non-problem paths in configured relative order
+
configured problem paths in configured relative order
```

Examples:

```text
A > B > C
problem A
    -> B > C > A

A > B > C > D
problem B,D
    -> A > C > B > D
```

No lexical/path-ID sort changes policy order.

## 3. Recovery

PASS.

Removing an established problem flag automatically returns the path to its configured
position because the configured order remains the only baseline.

No additional recovery-order state is retained.

## 4. Invalid caller state

PASS.

Rejected:

- duplicate configured logical path IDs;
- duplicate problem IDs;
- problem ID outside configured membership.

Empty membership is valid and remains empty.

## 5. Ownership / simplification

PASS.

This is pure `AvailabilityPriorityCalculator` machinery.

It does not establish problems, count evidence, mutate membership, allocate metrics or retain
history.

Availability confirmation remains Manager-owned and route mutation remains Executor-owned.

## Verdict

**PASS — AVAILABILITY PRIORITY TRANSFORMATION ACCEPTED.**
