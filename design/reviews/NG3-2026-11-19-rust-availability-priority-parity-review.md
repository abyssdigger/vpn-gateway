# NG3 Rust availability-priority parity review

**Date:** 2026-11-19  
**Cycle:** `ng3-design-cycle-20261119-post-probing-frontier-35m`  
**Scope:** Rust parity for logical path identity and pure availability effective-order calculation.

## Requirements

- `VPNG0003-R3.R2`
- `VPNG0003-R3.R4`
- `VPNG0003-R3.R7`
- `VPNG0007-R7.R8`
- `VPNG0007-R7.R8.R2`
- `VPNG0007-R7.R8.R3`

No product semantics changed.

## Implementation

Added safe-Rust:

- `logical_path.rs` — reusable logical path identity value;
- `availability_priority.rs` — pure sticky/reserve effective-order calculator.

The calculator preserves the Python reference contract:

- availability changes only order, never membership;
- problem paths move behind usable paths while preserving relative baseline order;
- a healthy ordinary active path stays sticky on recovery;
- a reserve active path yields to a higher-baseline usable path;
- an active path with an established problem loses sticky position;
- unknown/duplicate membership inputs are rejected.

The unit performs no route mutation, probe I/O, Manager lifecycle, or Linux interaction.

## Findings and dispositions

### F1 — first green Rust run did not compile the new calculator

The initial `availability_priority.rs` source commit triggered the Rust workflow and reported
success before the module was exported from `lib.rs`. Cargo therefore did not include that
source file in the crate graph, making that green run insufficient evidence for the new unit.

**Disposition:** accepted and fixed.

The module and `logical_path` dependency are now exported from `lib.rs`. Once the source
entered the crate graph, CI exposed ordinary rustfmt drift, which was corrected. Final
evidence is taken only from a run whose source is reachable from the crate root.

This establishes a migration review rule: a new Rust source file is not considered covered by
crate CI until it is reachable from the crate graph.

## Evidence

- NG3 Rust run `44527702222` on
  `a9920952cc3a53ff08c57e59e3e685df8e79131b`: **PASS**;
- active-lineage guard on the same source lineage: **PASS**.

The accepted run executes `cargo fmt --check` and `cargo test --all-targets` with the
calculator module exported from the crate root.

## Simplification review

No route writer, Manager, scheduler, FFI layer, generic path registry, or Python/Rust bridge
was introduced. The shared Rust `LogicalPathId` exists only because the second pure contract
needs the same semantic identity that later adjacent ports will also consume.

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

The Rust production-boundary now contains two adjacent accepted pure contracts:
confirmation-state transition and effective availability path ordering.
