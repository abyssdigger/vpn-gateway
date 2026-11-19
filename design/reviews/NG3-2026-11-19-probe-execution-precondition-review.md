# NG3 probe execution precondition review

**Date:** 2026-11-19  
**Scope:** read-only exactness gate between probe-policy materialization and physical ICMP
execution.

## Reviewed contracts

- architecture §8.2 probe network preconditions;
- architecture §8.3 pure probe network-policy projection;
- `VPNG0003-R3.R6`;
- `VPNG0003-R3.R6.R2`;
- `VPNG0003-R3.R6.R3`;
- `VPNG0004-R4.R5`;
- `VPNG0007-R7.R3.R2`.

No product requirement or configuration semantics changed.

## Implementation

`probe_precondition.py::verify_probe_execution_precondition` consumes one
`StructuralPolicyPhysicalSnapshot` and the complete current
`ProbeNetworkPolicyDesiredState`.

It independently compares:

- probe route/RPDB exactness through `compare_probe_routing`;
- probe-local nft exactness through `compare_probe_local`.

The returned `ProbeExecutionPrecondition.confirmed` is true only when both are exact.
The interface inventory from the same structural snapshot is retained as part of the
readiness evidence.

The verifier is read-only. It neither repairs policy nor executes a probe.

## Findings and dispositions

### F1 — routing exactness alone is insufficient

A correct dedicated probe table/RPDB selector with missing local OUTPUT/INPUT admission would
make physical execution fail locally. Treating routing-only confirmation as readiness would
confuse incomplete local materialization with remote unavailability.

**Disposition:** fixed by contract. Readiness requires both routing and probe-local nft
exactness.

### F2 — local nft exactness alone is insufficient

Correct local ICMP admission without the dedicated route/RPDB owner could allow an attempt to
follow ambient or wrong-path routing.

**Disposition:** fixed by contract. Missing routing selector makes readiness false even when
local policy is exact.

### F3 — readiness must be observational, not another mutation path

Repair belongs to the existing convergence machinery. A verifier that silently repaired one
side before execution would duplicate ownership and make attempt provenance harder to audit.

**Disposition:** fixed by construction. The gate only compares a fresh structural snapshot.

### F4 — verifier correctly requires the invariant nft scaffold

The first focused test fixture supplied an owned nft namespace without the invariant base
chains. `compare_probe_local` rejected that snapshot before evaluating probe-local rules.
This is the intended lower safety contract: local exactness cannot be claimed in an
unconfirmed reserved nft namespace.

**Disposition:** test-harness defect fixed. The readiness fixture now includes the canonical
`PAYLOAD_NFT_SCAFFOLD`; the verifier was not weakened to accept an incomplete namespace.

## Evidence

Focused tests cover:

- empty probe plane is exactly ready;
- missing routing selector blocks readiness while local side remains exact;
- missing probe-local admission blocks readiness while routing side remains exact.

The branch NG3 unit workflow for the final code SHA is the execution authority.

## Simplification review

No new convergence engine, transaction, scheduler, retry loop or Linux observer was added.
The gate reuses the existing authoritative structural snapshot and exact comparison
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
