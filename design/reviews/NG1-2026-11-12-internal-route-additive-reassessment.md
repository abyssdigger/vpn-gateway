# Internal review — ROUTE_ADDITIVE Planner reassessment

Date: 2026-11-12

## Scope

Reviewed the accepted ROUTE_ADDITIVE transition through both Planner classification
points:

1. initial live-state assessment;
2. mandatory reassessment after namespace prerequisites are applied and a fresh snapshot is
   collected.

Also reviewed the existing rootless regression
`test_route_additive_reassessment_remains_incremental` and the privileged production-cycle
metric-promotion phase that exposed the defect.

## Finding F1 — initial and reassessment transition sets diverged

The initial Planner branch accepted:

- BINDING_LIFECYCLE;
- ROUTE_ADDITIVE.

The post-prerequisite reassessment accepted only BINDING_LIFECYCLE.

As a result, a route-additive metric-promotion transition was correctly proven safe twice
but was rejected on the second proof with an empty reason list.

Severity: medium/high control-plane liveness; safety remained fail-closed.

## Disposition

Accepted and fixed.

Both classification points now accept the same closed set of proven incremental
transitions:

- BINDING_LIFECYCLE;
- ROUTE_ADDITIVE.

No new transition kind is inferred and structural/unknown state still falls back to the
global protective barrier.

The existing rootless test already models the full three-snapshot path
(initial -> prepared/reassessment -> applied) and therefore directly covers this regression.

## Rust-alignment review

The fix preserves a closed enum-based transition set. A later Rust implementation should
factor the accepted incremental kinds into one helper/predicate to prevent duplicated match
sets from diverging again.

That refactor is recommended as a small maintenance improvement if another transition kind
is added; it is not required for current correctness.

## Verdict

CLOSED. No remaining recommendation for this review unit.
