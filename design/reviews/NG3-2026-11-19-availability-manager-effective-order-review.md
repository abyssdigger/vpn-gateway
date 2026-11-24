# NG3 availability evidence-to-effective-order Manager review

**Date:** 2026-11-19  
**Cycle:** `ng3-design-cycle-20261119-probe-continuous-availability-loop-35m`  
**Scope:** bounded Manager state from current probe contexts and fresh semantic evidence to
effective Profile path order.

## Reviewed contracts

- `VPNG-U003-R3.R2`
- `VPNG-U003-R3.R3`
- `VPNG-U003-R3.R4`
- `VPNG-U003-R3.R5`
- `VPNG-U003-R3.R5.R1`
- `VPNG-U003-R3.R5.R2`
- `VPNG-U003-R3.R6.R1`
- `VPNG-U003-R3.R6.R2`
- architecture §4.3, §4.4 and §5 outbound sticky/reserve semantics.

No user-facing configuration or product requirement changed.

## Implementation

`availability_manager.py::AvailabilityManager` composes already accepted bounded
availability state:

```text
current ProbeObservationContext set
        |
        v
subject context synchronization
        |
fresh ProbeEvidence
        |
        v
AvailabilityConfirmationState
        |
        v
problem owner set
        |
        v
AvailabilityRoutingState
        |
        v
effective PayloadProfileRequest order
```

`AvailabilityManagerPolicy` carries finite degradation/recovery thresholds as local runtime
policy. It is not part of Release-1 user configuration.

## Findings and dispositions

### F1 — confirmation state must reset when observation context changes

Keeping degradation/recovery progress across target, endpoint generation or Agent generation
replacement would allow old evidence to contribute to a new observation context.

**Disposition:** fixed. `synchronize()` preserves confirmation state only when the complete
immutable `ProbeObservationContext` is equal. Any context replacement starts fresh bounded
confirmation state.

### F2 — stale evidence must fail closed at the Manager boundary too

The Probe Agent already rejects stale physical results, but the Manager should not silently
accept a `ProbeEvidence` object that does not match its synchronized current context.

**Disposition:** fixed. `apply_evidence()` requires exact current context equality or rejects
the evidence.

### F3 — recovery of an ordinary path must not force failback

After failover from A to ordinary B, recovery of A must clear A's problem state without moving
B away from active first position.

**Disposition:** verified through the existing `AvailabilityRoutingState` sticky semantics
and focused regression coverage.

### F4 — explicit reserve membership deliberately permits failback

When the active path belongs to a Profile-local `:reserve` Device membership, recovery of a
higher-baseline ordinary path must restore baseline preference.

**Disposition:** verified using canonical `device_order = ["wg", "oc:reserve"]` grammar.

### F5 — architecture retained a superseded outbound path-affinity gate

Architecture §10.1 still claimed availability-driven outbound priority permutation required a
per-flow path-affinity owner. That contradicted the later accepted sticky-active design in §5,
which explicitly removed that Release-1 gate.

**Disposition:** accepted and fixed. §10.1 now points to sticky active-path semantics and keeps
managed-stack return affinity separate.

## Evidence

Focused tests cover:

- baseline order after synchronization;
- finite degradation threshold;
- finite recovery threshold;
- ordinary-path sticky recovery without failback;
- reserve-path recovery failback;
- context replacement resetting confirmation progress;
- stale evidence rejection;
- `no_evidence` leaving availability state unchanged.

The authoritative branch CI is the NG3 Python workflow for this review unit.

## Simplification review

No event log, evidence history, time window, flow table, scheduler, retry queue or new routing
Manager was introduced. The implementation composes the existing bounded confirmation and
routing-state Calculators inside the already accepted PayloadTrafficManager responsibility.

Threshold values remain local implementation policy and are not exposed as user knobs.

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

**ACCEPT**, subject to current branch unit evidence passing. No requirement closure change is
required because this unit implements already closed semantics.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005-R5` -> `VPNG-M001-R1.R1`
- `VPNG-U005-R5.R6` -> `VPNG-M001-R1.R1.R6`

The original IDs in the historical body are intentionally preserved.
