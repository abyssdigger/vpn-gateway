# VPN-GATE NG3 — Availability priority transformation implementation gate

**Cycle:** `ng3-design-cycle-20261116-post-closure-implementation-readiness-40m`  
**Review unit:** pure effective path ordering from established availability-problem flags

## Scope

Implement current `AvailabilityPriorityCalculator` contract:

```text
configured ordered allowed paths
+
established problem path IDs
    ->
effective ordered allowed paths
```

## Requirements

- `VPNG-R3.R1`;
- `VPNG-R3.R2`;
- `VPNG-R3.R2.R1`;
- `VPNG-R3.R3`;
- `VPNG-R3.R4`;
- `VPNG-R3.R7`.

## Ordering semantics

The transformation is a stable partition:

1. paths without an established problem, in configured relative order;
2. paths with an established problem, in configured relative order.

Therefore:

```text
configured: A > B > C
problem:    A
effective:  B > C > A
```

Recovery removes the problem flag and therefore restores the configured position.

## Membership invariant

Output contains exactly the configured allowed path set.

Problem state cannot add/remove membership.

Duplicate configured path IDs or problem IDs outside configured membership are rejected as
invalid caller state rather than guessed.

## Component design

Pure current `AvailabilityPriorityCalculator`.

It consumes already-established problem flags; confirmation/hysteresis remains Manager-owned.

## Evidence plan

Rootless tests for no problems, one/multiple problems, stable relative order, recovery,
membership preservation and invalid inputs.

## Verdict

**PASS — AvailabilityPriorityCalculator may be implemented.**
