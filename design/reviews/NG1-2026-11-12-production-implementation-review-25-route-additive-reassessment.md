# Production implementation review 25 — route-additive reassessment

Date: 2026-11-12

Role: internal expert review under CONTINUOUS-DEVELOPMENT.md.

## Scope

Reviewed the Planner path for an already-proven incremental transition after namespace
prerequisites are applied and a fresh snapshot is collected.

The review focused on the newly introduced ROUTE_ADDITIVE transition and consistency
between initial assessment, reassessment and apply/verify behavior.

## Finding F1 — reassessment admitted a smaller transition set than initial assessment

Severity: medium/high, liveness/integration correctness.

Initial Planner assessment correctly allowed both:

- BINDING_LIFECYCLE;
- ROUTE_ADDITIVE.

After applying namespace prerequisites and collecting a fresh snapshot, reassessment
accepted only BINDING_LIFECYCLE. A stable ROUTE_ADDITIVE state therefore produced
PlannerRetryRequired even though no safety property had changed.

This was observed by the privileged production-cycle test during the second metric-promotion
reconcile.

### Disposition

Accepted and fixed.

Initial assessment and reassessment now use the same proven incremental transition set:

    { BINDING_LIFECYCLE, ROUTE_ADDITIVE }

Any other reassessment kind still aborts the incremental path and requests a fresh retry
rather than applying against an unproven generation.

The retry diagnostic now includes the observed transition kind.

## Regression coverage

A dedicated rootless Planner test now constructs:

- stable bindings and policy generations;
- desired normal route missing from observed kernel state;
- intact RPDB and terminal blackhole;
- forwarding already enabled.

It verifies that:

1. the initial state classifies as ROUTE_ADDITIVE;
2. the fresh post-prerequisite reassessment remains ROUTE_ADDITIVE;
3. Planner adds the missing route without global ip_forward=0;
4. the final verified state commits successfully.

The existing privileged production-cycle test remains the kernel integration gate.

## Whole-project consistency check

No architecture change is required.

The fix matches the existing Draft 5 rule that route-only additive repair with intact
terminal blackholes and known policy generations is incremental. It does not broaden the
set of accepted structural drift and does not change nft policy ownership.

## Rust-alignment review

The correction removes an accidental branch asymmetry. A future Rust state machine should
represent the set of incremental transition variants once and reuse it across initial and
post-prerequisite guards rather than duplicate variant tests.

## Verdict

Source change approved with no remaining recommendation in this review unit.

Final acceptance of the iteration requires rootless CI and the privileged production-cycle
test to pass.
