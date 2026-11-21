# VPN-GATE NG3 — Route-Priority Partial-State Convergence Code Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-primary-requirements-basis-40m`  
**Implementation commits reviewed:**  
- `40e41b5089eca5b2d8616a243d095ed2c87c9e1b`
- `50f4544897e3287a0dd3d1666706b329cb2f074a`

## 1. Scope

This review unit extends the already accepted clean-state route-priority planner with the
missing recovery semantics identified by the previous post-cycle review:

- consume one fresh authoritative **normalized owned-route observation**;
- represent a logical path temporarily observed at multiple owned metrics;
- recognize a partially completed make-before-break move;
- remove only already-confirmed redundant copies while retaining at least one route per path;
- converge to the desired one-metric-per-path assignment without replaying stale commands;
- reject states that no longer satisfy the pure-priority proof boundary.

The unit intentionally stops before physical Linux route collection/mutation and final
postcondition verification.

## 2. Requirement / design gate

Relevant accepted requirements:

- `VPNG0003-R3.R2`, `VPNG0003-R3.R3`, `VPNG0003-R3.R4`;
- `VPNG0004-R4.R2`, `VPNG0004-R4.R3`, `VPNG0004-R4.R3.R1`,
  `VPNG0004-R4.R5`;
- `VPNG0005-R5.R2`, `VPNG0005-R5.R3`;
- `VPNG0007-R7.R1`, `VPNG0007-R7.R3`, `VPNG0007-R7.R5`.

No new product semantics were required.

The architecture already requires:

- fresh observation when prior state is not authoritative;
- make-before-break for pure priority permutations;
- duplicate route copies during the add-before-delete window;
- re-observation after partial failure;
- convergence from actual state rather than replay of an old command sequence;
- final postcondition verification outside the planner.

The new code is therefore an implementation refinement of an already closed architecture
boundary.

## 3. Initial implementation

Commit `40e41b5` introduced:

- `route_priority_convergence.py`;
- recovery tests for partial add/delete states;
- the first NG3 Python GitHub Actions workflow.

GitHub Actions run `43818005779` completed successfully.

## 4. Expert-review finding F1 — raw add/delete API weakened the verified-move boundary

**Severity:** material design/API defect  
**Disposition:** accepted and fixed in `50f4544`

The first version returned independent `RoutePriorityAdd` and `RoutePriorityDelete`
mutations.

Although its simulated sequence was safe, that API allowed a future Executor to interpret
the two operations as ordinary replayable commands and thereby lose the architecture's
mandatory semantic boundary:

```text
add new copy
-> verify/continue
-> delete old copy
```

This would be especially dangerous after a partial failure because the tail of the old plan
could be replayed without fresh observation.

### Fix

The convergence surface now exposes only:

- `RoutePriorityDeleteDuplicate` — exact deletion of a redundant copy that was already
  present in the fresh observation while another copy of the same path remains;
- existing `RoutePriorityMove` — the semantic make-before-break primitive whose Executor
  realization is add-new -> verify -> delete-old.

After any partial execution failure the remaining steps are explicitly stale; the caller
must re-observe and re-plan.

## 5. Recovery behavior reviewed

The fixed planner correctly handles:

1. **clean swap** — delegates to semantic `RoutePriorityMove` sequence;
2. **failure after add, before delete** — fresh observation contains two metrics for one
   path; planner emits safe duplicate cleanup rather than replaying the add;
3. **desired add already completed** — only stale old copy is removed;
4. **previous move fully completed** — planning continues from the newly observed single
   metric, not from the prior plan index;
5. **no free metric but a redundant copy exists** — redundant copy can safely free the
   metric needed by another path;
6. **cycle with no free metric and no duplicate** — rejected rather than break-before-make;
7. **missing path route** — rejected from priority-only convergence because continuity is no
   longer provable;
8. **structural membership difference** — rejected for guarded structural convergence;
9. **same metric observed for two logical paths** — rejected as ambiguous/unsafe;
10. **observed route outside the owned metric space** — rejected;
11. **duplicate exact metric for the same path** — rejected rather than silently collapsed;
12. **input-order variation** — deterministic plan.

## 6. Evidence

Final fixed-code GitHub Actions run:

```text
workflow: NG3 Python
run:      43818243370
commit:   50f4544897e3287a0dd3d1666706b329cb2f074a
status:   completed
result:   success
tests:    97
summary:  Ran 97 tests ... OK
```

The workflow also runs `compileall` for the NG3 package.

## 7. Residual boundary

This unit closes the **normalized partial-state convergence algorithm**, not the complete
physical NetworkPolicyExecutor.

Still required:

- authoritative Linux owned-route observation and normalization into
  `logical_path -> observed metrics`;
- physical execution of `RoutePriorityMove` with add/verify/delete semantics;
- exact duplicate deletion at the physical route identity;
- re-observation after command failure;
- final desired-state postcondition verification;
- guarded structural convergence when membership or other policy dimensions differ.

Those remain the next implementation boundary; this review does not pretend that the pure
planner itself is an Executor.

## Final verdict

**PASS AFTER FIX.**

The fixed convergence API preserves the accepted make-before-break proof boundary and can
recover deterministically from the partial duplicate state that the previous clean-state
planner could not represent. The code is suitable as the pure convergence core beneath the
future physical NetworkPolicyExecutor.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG0005-R5.R2` -> `VPNG9101-R1.R1.R2`
- `VPNG0005-R5.R3` -> `VPNG9101-R1.R1.R3`
- `VPNG0007-R7.R1` -> `VPNG9001-R1.R1.R1`
- `VPNG0007-R7.R3` -> `VPNG9001-R1.R1.R3`
- `VPNG0007-R7.R5` -> `VPNG9001-R1.R1.R5`

The original IDs in the historical body are intentionally preserved.
