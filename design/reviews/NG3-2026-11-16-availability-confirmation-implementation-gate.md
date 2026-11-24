# VPN-GATE NG3 — Availability confirmation state implementation gate

**Cycle:** `ng3-design-cycle-20261116-post-closure-implementation-readiness-40m`  
**Review unit:** bounded Profile/path availability confirmation transition

## Scope

Implement only the bounded semantic state transition owned by `PayloadTrafficManager` after
fresh/current `AvailabilityEvidence` has already been accepted for the correct observation
context.

Inputs:

```text
current confirmation state
outcome = positive | negative | no_evidence
degradation_threshold
recovery_threshold
```

Output: next bounded confirmation state.

Freshness/context validation and physical probing are outside this unit.

## Requirements

- `VPNG-R3.R3`;
- `VPNG-R3.R4`;
- `VPNG-R3.R5`;
- `VPNG-R3.R5.R1`;
- `VPNG-R3.R5.R2`;
- `VPNG-R7.R1.R1`.

## State

```text
availability_problem: bool
degradation_progress
recovery_progress
```

Only progress relevant to the current problem state is retained.

Thresholds are positive finite local policy parameters passed to the transition helper; this
unit does not make them user-facing config.

## Transitions

When no problem is established:

- negative increments bounded degradation progress;
- positive clears degradation progress;
- no_evidence changes nothing;
- reaching degradation threshold establishes problem and resets obsolete progress.

When problem is established:

- positive increments bounded recovery progress;
- negative clears recovery progress;
- no_evidence changes nothing;
- reaching recovery threshold clears problem and resets obsolete progress.

No evidence history/window/replay is retained.

## Component design

This is bounded state-transition logic inside current `PayloadTrafficManager` ownership.

It is not a new Calculator component because establishment/confirmation state spans
observations and is Manager-owned.

## Evidence plan

Rootless tests for threshold transitions, progress reset, no_evidence neutrality, opposite
evidence reset and invalid threshold rejection.

## Verdict

**PASS — bounded availability confirmation transition may be implemented.**
