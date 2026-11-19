# NG3 Rust availability routing-state parity review

**Date:** 2026-11-19  
**Cycle:** `ng3-design-cycle-20261119-post-probing-frontier-35m`  
**Scope:** Rust parity for bounded sticky/reserve routing state projection.

## Requirements

- `VPNG0003-R3.R2`
- `VPNG0003-R3.R4`
- `VPNG0003-R3.R7`
- `VPNG0007-R7.R8`
- `VPNG0007-R7.R8.R3`

No product behavior changed.

## Implementation

Added `availability_routing_state.rs` and exported it from the crate root.

The Rust projection preserves the accepted Python behavior:

- initial state selects the first usable baseline path;
- active-path failure selects the next usable path;
- ordinary recovery keeps a healthy active path sticky;
- reserve active path yields to a higher-baseline recovered path;
- disappeared active identity is treated as stale bounded state rather than an input error;
- all-problem and empty membership clear the active identity;
- ordering semantics are delegated to the already ported Rust availability-priority calculator.

No Linux I/O, route mutation, probing or confirmation state is owned by this module.

## Evidence

- NG3 Rust run `44527999287` on
  `0ca921edd64d62c70d9fc9caeecc56f6243445b1`: **PASS**;
- active-lineage guard on the same source: **PASS**.

As with the previous unit, evidence is taken only after the module is exported into the crate
graph. The first exported run exposed only rustfmt drift; after correction both formatting and
tests pass.

## Simplification review

No separate routing Manager, route writer, scheduler, FFI layer or state history was added.
The module retains exactly one optional active logical-path identity for one Profile and
returns a pure projection.

## Requirement-state inventory

### decomp

All accumulated occurrences remain resolved:

- `VPNG0005-R5 -> VPNG0005-R5.R6`;
- `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`;
- `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`;
- `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`.

### unreal

none

### broken

none

### rejected_closure

none

## Verdict

**ACCEPT.**

The Rust production-boundary now covers confirmation, effective-order calculation and bounded
active-path projection as three adjacent pure contracts.
