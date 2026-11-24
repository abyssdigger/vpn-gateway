# VPN-GATE NG3 — Pure structural pipeline integration review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-post-closure-implementation-readiness-40m`

## Scope

Reviewed the cross-contract rootless scenario artifact:

- `design/NG3/code/python/rou/tests/test_pure_structural_pipeline.py`.

It composes only production contracts already accepted in preceding review units.

## Scenario 1 — outbound multi-path

Pipeline:

```text
TOML
-> structural config
-> ip-link inventory
-> stable Device binding slots
-> PayloadProfileRequest
-> outbound Profile classification
-> availability priority transformation
```

PASS by contract review.

The test proves these seams preserve different kinds of ordering correctly:

- Device selector order remains user policy;
- interface observation order only selects candidates inside one selector;
- logical path membership remains stable;
- availability changes only effective order, not membership.

## Scenario 2 — zero-binding Profile

Pipeline retains an enabled Profile with:

```text
ordered_paths = ()
```

The remote destination still classifies to that Profile policy domain.

This is the required structural precondition for lower fail-closed materialization: loss of
all paths cannot make the destination fall out of VPN-GATE policy ownership.

## Scenario 3 — Release 1 inbound single-path

An accepted `inbound` Profile with configured path capacity 1:

- binds one logical path;
- classifies a matching remote source only when the actual ingress LogicalPathId belongs to
  the Profile;
- rejects a different ingress path.

This composes the Release 1 capacity constraint with current inbound classification semantics
without introducing return-path pinning.

## Scope / evidence boundary

This integration artifact does not add or claim:

- Linux route/filter/NAT realization;
- probe execution;
- route metric allocation;
- transport-policy grammar;
- publication;
- multi-path inbound support.

Those remain separate evidence/implementation units.

## Verdict

**PASS — CURRENT PURE STRUCTURAL CONTRACTS COMPOSE WITHOUT A NEW SEMANTIC GAP.**

No blocker was found by the integration review.
