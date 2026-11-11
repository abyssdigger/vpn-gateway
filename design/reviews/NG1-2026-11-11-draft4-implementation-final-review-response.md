# Response to NG1 Draft 4 + implementation final review

Disposition: **accepted; maintenance cleanups applied without changing Draft 4 semantics.**

## C1 — device-scoped firewall intent

Accepted. `NewFlowRuleIntent` now documents that it is Device-scoped and that kernel
materialization expands it only across currently bound interfaces of that Device.
Absent, over-quota and otherwise unbound interfaces receive no materialized rule.

## C2 — diagnostic classifier role

Accepted. `classify_device_to_host_profile()` now documents that it exists for
diagnostics/status/policy explanation. Kernel firewall materialization uses equivalent
ordered prefix-match rules directly rather than calling the helper per packet.

## C3 — assertion

Accepted. Manual/in-memory `ActiveConfig` construction now receives a descriptive
`ValueError` for an enabled Profile with no direction instead of relying on
`AssertionError`.

## C4 — three-level overlap test

Accepted. Added a three-level Device→host ordering regression:
`10.20.0.0/16 DROP -> 10.0.0.0/8 ACCEPT -> 0.0.0.0/0 DROP`.

## C5 — multi-step metric promotion

Accepted. `project_normal_metrics()` now documents the two-commit lifecycle:
verified removal first frees the old metric, then a later reconcile may assign that slot
to a promoted/new candidate, followed by its own apply/verify/commit.

## Additional stale commentary

During cleanup, an obsolete statement that unavailable fallback was still pending EXP-013
was found in `traffic_state.py`. It was removed and replaced with the current ownership
boundary: normal-tier allocation lives in `traffic_state.py`; fallback projection lives
in `route_intent.py`.

## Baseline

No architecture change was required. **NG1 Draft 4 remains the implementation baseline.**

## Follow-up verification verdict

The reviewer re-checked all five cleanup items plus the stale EXP-013 commentary removal and confirmed that all six changes were applied correctly, with no semantic change to Draft 4 and no observed side effects.

The verification verdict is archived in:

`design/reviews/NG1-2026-11-11-draft4-implementation-cleanup-verdict.md`

**Baseline remains NG1 Draft 4.** The next implementation stage remains the kernel materialization slice, beginning with live EnvironmentSnapshot collection and routing-table/RPDB allocation.
