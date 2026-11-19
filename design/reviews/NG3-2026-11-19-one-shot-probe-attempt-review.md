# NG3 one-shot probe attempt review

**Date:** 2026-11-19  
**Scope:** one physical availability attempt after exact probe-plane readiness, without
scheduling or retry semantics.

## Reviewed contracts

- `VPNG0003-R3.R6`
- `VPNG0003-R3.R6.R1`
- `VPNG0003-R3.R6.R2`
- `VPNG0003-R3.R6.R3`
- architecture §7 AvailabilityProbeAgent;
- architecture §8.2 probe execution preconditions.

No product requirement or user-facing configuration changed.

## Implementation

`probe_attempt.py::execute_probe_attempt_once` is the narrow execution seam:

1. require a confirmed `ProbeExecutionPrecondition`;
2. require the requested `ProbePolicyOwner` to belong to that readiness owner set;
3. obtain the current immutable Agent attempt context;
4. require its concrete endpoint to be present in the readiness interface snapshot;
5. invoke exactly one bounded Driver check;
6. feed the technical observation back through the existing exact context/generation gate.

There is no cadence, retry, threshold accumulation or route-priority mutation in this unit.

## Findings and dispositions

### F1 — readiness must be bound to the exact probe owner set

A generic "probe plane is confirmed" boolean could be accidentally reused for an owner that
was not represented by the desired state used for verification.

**Disposition:** accepted and fixed. `ProbeExecutionPrecondition` carries the exact semantic
owner set derived from desired probe routing/local policy, and verification rejects a mismatch
between routing-owner and local-owner sets. Attempt execution requires membership.

### F2 — current context endpoint must still belong to the readiness snapshot

Even with an owner match, a caller could reconfigure the Agent context after readiness
observation and before invocation.

**Disposition:** fixed. Before Driver I/O the current context endpoint must occur in the
readiness snapshot's interface identity set. A changed same-name/new-ifindex endpoint cannot
reuse the preceding readiness value.

### F3 — reconfiguration during Driver I/O must not create evidence for the new context

The physical check is necessarily outside the immutable Python context. A target/path/context
change can occur while the Driver is running.

**Disposition:** preserved through the existing generation contract. The attempted immutable
context is passed back to `AvailabilityProbeRuntime.accept_result`; if current state changed,
the result is discarded and no availability evidence is emitted.

## Evidence

Focused tests cover:

- confirmed current attempt -> positive evidence;
- unconfirmed readiness -> no Driver I/O;
- owner absent from readiness -> no Driver I/O;
- context endpoint absent from readiness interface snapshot -> no Driver I/O;
- context reconfiguration during Driver execution -> returned observation is rejected as
  stale.

The branch NG3 unit workflow for the final code SHA is the execution authority.

## Simplification review

No scheduler, retry loop, worker pool or confirmation/routing policy was added. The boundary
executes exactly one already-normalized attempt and reuses the existing Driver and Agent
contracts.

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
