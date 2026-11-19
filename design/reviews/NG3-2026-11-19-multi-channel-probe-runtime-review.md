# NG3 multi-channel probe runtime review

**Date:** 2026-11-19  
**Scope:** bounded current-context management for multiple simultaneous availability subjects.

## Reviewed contracts

- `VPNG0003-R3.R6`
- `VPNG0003-R3.R6.R1`
- `VPNG0003-R3.R6.R2`
- `VPNG0003-R3.R6.R3`
- `VPNG0006-R6.R3`
- architecture §7 AvailabilityProbeAgent.

No product requirement or user-facing configuration changed.

## Implementation

`AvailabilityProbeRuntime` is an implementation helper for the existing
`AvailabilityProbeAgent` component role, not a new component.

It owns a bounded set of child `AvailabilityProbeAgent` contexts keyed by
`ProbePolicyOwner(Profile, logical path)`.

It:

- configures all currently requested normalized subjects against exact current path endpoints;
- permits multiple subjects to be active concurrently;
- disables a subject that disappears;
- retains that subject's generation counter so reappearance cannot accept an old in-flight
  result merely because intent and endpoint happen to be textually identical again;
- exposes only current active contexts;
- accepts a technical result only through the still-current owner/context.

It does not schedule attempts, choose cadence, execute ICMP, accumulate hysteresis or alter
route preference.

## Findings and dispositions

### F1 — deleting inactive child Agents would allow generation reuse

If an owner disappeared and its child Agent were discarded, recreating the same owner could
start again at generation 1. An old attempt whose immutable context also had generation 1
could then become equal to the fresh context.

**Disposition:** fixed by design. Previously seen owners remain as disabled child Agents and
reuse their monotonic local generation on reappearance. Under the accepted static
configuration this set is bounded by configured Profile/path identity space and is not a
result/history store.

### F2 — reconfiguration initially allowed partial state mutation on validation failure

The first implementation updated owners in iteration order before proving that every new
owner had a current path realization. A later missing path could therefore raise after an
earlier owner had already changed generation/target.

**Disposition:** accepted and fixed. The entire desired owner/intent/endpoint tuple set is
validated first; only after successful validation are any child Agent contexts changed. A
regression test verifies that failed reconfiguration leaves the prior current context exact.

### F3 — one physical endpoint replacement must invalidate only the affected subject context

A same-name/new-ifindex replacement is a new concrete endpoint identity and must reject a
late result from the preceding endpoint generation.

**Disposition:** preserved by the existing child Agent contract and covered through the
multi-channel runtime.

## Evidence

Focused unit coverage includes:

- two subjects active concurrently;
- disappearance followed by reappearance receives a fresh generation;
- late result while disabled is rejected;
- old result after reappearance is rejected;
- concrete endpoint replacement invalidates the old attempt;
- missing path realization is rejected;
- duplicate owner is rejected;
- failed multi-owner reconfiguration does not partially mutate earlier contexts.

The branch NG3 unit workflow for the final code SHA is the execution authority; the workflow
may be queued independently of this review commit.

## Simplification review

No scheduler, worker pool, journal, history, event bus, retry policy or generic Agent
framework was added. Existing one-context semantics remain the only generation/evidence
authority; the new class only multiplexes them by semantic owner.

## Requirement-state inventory

### decomp

All existing occurrences remain resolved:

- `VPNG0005-R5 -> VPNG0005-R5.R6`
- `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`
- `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`
- `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`

### unreal

none

### broken

none

### rejected_closure

none

## Verdict

**ACCEPT**, conditional on the branch unit suite passing at the final code SHA or an exact
descendant with no semantic change to this unit.
