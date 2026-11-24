# NG3 bounded availability observation tick review

**Date:** 2026-11-19  
**Cycle:** `ng3-design-cycle-20261119-probe-continuous-availability-loop-35m`  
**Scope:** one externally triggered availability observation cycle over already-materialized
and freshly verified probe policy.

## Reviewed contracts

- `VPNG-U003-R3.R5.R1`
- `VPNG-U003-R3.R5.R2`
- `VPNG-U003-R3.R6`
- `VPNG-U003-R3.R6.R1`
- `VPNG-U003-R3.R6.R2`
- architecture §7 AvailabilityProbeAgent;
- architecture §8.2 exact probe execution precondition.

No product requirement or user-facing configuration changed.

## Implementation

`availability_observation_tick.py::run_availability_observation_tick` performs one bounded
outer-runtime wakeup:

```text
current normalized ProbeDesiredAssembly
+ current path realization
+ fresh ProbeExecutionPrecondition
        |
        v
synchronize current AvailabilityProbeRuntime contexts
        |
        v
synchronize AvailabilityManager context state
        |
        +-- precondition not exact -> no probe I/O, no fabricated negative evidence
        |
        +-- exact -> at most one attempt per current subject
                        |
                        v
                    fresh ProbeEvidence only
                        |
                        v
                  AvailabilityManager
                        |
                        v
                  effective Profile order
```

The function does not schedule itself, repair probe policy or mutate route priority.

## Findings and dispositions

### F1 — unready probe policy must not be translated into path failure

A missing RPDB rule, local nft admission or other local materialization defect says nothing
about remote reachability. Running a check anyway, or converting readiness failure to
negative evidence, would lower a path because of VPN-GATE's own local defect.

**Disposition:** fixed by contract. An unconfirmed precondition runs no Driver I/O and emits
no evidence. The current bounded Manager state is merely projected unchanged.

### F2 — one wakeup must be bounded across all current subjects

A tick must not contain a hidden retry/scheduler loop. It may attempt each currently active
subject once and return control to the outer Manager cadence.

**Disposition:** fixed by construction. The function iterates the finite current context set
once; each subject enters the existing one-shot attempt boundary at most once.

### F3 — runtime must consume normalized intents directly, not reverse-engineer lower rules

Reconstructing `AvailabilityProbeIntent` from RPDB/nft desired objects would invert the
normalization boundary and make lower implementation representation authoritative for product
semantics.

**Disposition:** fixed. `ProbeDesiredAssembly` now retains the already-resolved concrete
intent tuple alongside the lower desired state.

### F4 — local execution failure remains no_evidence

A Driver-local failure must not establish an availability problem.

**Disposition:** preserved by the existing Driver/Agent mapping and covered at tick level;
effective order remains unchanged when one attempt produces `NO_EVIDENCE`.

## Evidence

Focused tests cover:

- one external tick attempts every current subject exactly once;
- one negative subject with threshold 1 changes effective order;
- unconfirmed execution precondition causes zero Driver calls and no path degradation;
- local execution failure produces no availability state change.

The exact readiness and one-shot attempt boundaries remain independently covered by their
existing suites.

## Simplification review

No scheduler framework, retry queue, worker pool, timer abstraction, durable task state or
new evidence type was introduced. The tick is deliberately externally driven and bounded.

## Requirement-state inventory

### decomp

All existing occurrences remain resolved:

- `VPNG-U005-R5 -> VPNG-U005-R5.R6`
- `VPNG-U004-R4.R6 -> VPNG-U004-R4.R6.R1`
- `VPNG-U001-R1.R3 -> VPNG-U001-R1.R3.R2`
- `VPNG-U001-R1.R2 -> VPNG-U001-R1.R2.R2`

### unreal

none

### broken

none

### rejected_closure

none

## Verdict

**ACCEPT**, subject to current branch unit evidence passing. The unit implements already
closed semantics.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005-R5` -> `VPNG-M001-R1.R1`
- `VPNG-U005-R5.R6` -> `VPNG-M001-R1.R1.R6`

The original IDs in the historical body are intentionally preserved.
