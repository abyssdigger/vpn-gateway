# NG3 first Rust production-boundary parity slice review

**Date:** 2026-11-19  
**Cycle:** `ng3-design-cycle-20261119-post-probing-frontier-35m`  
**Scope:** first production-language replacement unit under `VPNG-U007-R7.R8`.

## Requirements

- `VPNG-U007-R7.R8`
- `VPNG-U007-R7.R8.C1`
- `VPNG-U007-R7.R8.R1`
- `VPNG-U007-R7.R8.R2`
- `VPNG-U007-R7.R8.R3`
- existing availability confirmation semantics under `VPNG-U003-R3.R5.R1` and
  `VPNG-U003-R3.R5.R2`.

No requirement or user-visible behavior changed.

## Selected first port

The first Rust production-boundary unit is the pure availability confirmation state machine:

```text
current confirmation state
+ fresh AvailabilityOutcome
+ finite local degradation/recovery thresholds
    ->
next confirmation state
```

Python remains the executable reference for early releases. The Rust implementation is not
wired into the alpha runtime yet and therefore does not change current release behavior.

## Implementation

Added minimal crate:

`design/NG3/code/rust/vpng-runtime`

with:

- crate-wide `#![forbid(unsafe_code)]`;
- no dependencies;
- no FFI;
- no I/O;
- no scheduler/runtime framework;
- one `availability_confirmation` module;
- unit tests mirroring the accepted Python reference cases.

The port preserves:

- negative confirmation threshold semantics;
- positive recovery threshold semantics;
- opposite evidence resetting partial progress;
- `NO_EVIDENCE` neutrality;
- invalid state-shape rejection;
- zero-threshold rejection;
- progress-vs-threshold validation.

## CI

Added `.github/workflows/ng3-rust.yml` with:

- `cargo fmt --check`;
- `cargo test --all-targets`.

The active-lineage hygiene workflow was extended narrowly to allow exactly the new
`ng3-rust.yml` workflow in addition to the existing workflow set.

Evidence:

- NG3 Rust run `44527331872` on `a2518d5a3d71c7a9d6de245d607bcabca9e6c72e`: **PASS**;
- active-lineage guard run `44527362748` on
  `97dca68eb38e4619fd4044de9b0744c19a879c66`: **PASS**.

The first Rust run failed only on canonical rustfmt output; source was reformatted and rerun
successfully. The first lineage run failed because its exact workflow allowlist predated the
new Rust workflow; the allowlist was extended only for that workflow and rerun successfully.

## Simplification review

Deliberately not introduced:

- Python/Rust FFI;
- dual-runtime dispatcher;
- generic serialization layer;
- async runtime;
- networking dependencies;
- configuration parser;
- lifecycle abstraction;
- compatibility wrapper.

Those would add migration machinery before a concrete ported boundary requires them.

## Requirement-state inventory

### decomp

All accumulated occurrences remain resolved:

- `VPNG-U005-R5 -> VPNG-U005-R5.R6`;
- `VPNG-U004-R4.R6 -> VPNG-U004-R4.R6.R1`;
- `VPNG-U001-R1.R3 -> VPNG-U001-R1.R3.R2`;
- `VPNG-U001-R1.R2 -> VPNG-U001-R1.R2.R2`.

### unreal

none

### broken

none

### rejected_closure

none

## Verdict

**ACCEPT.**

This is a valid first Rust production-boundary parity slice. It proves the crate/CI/safe-Rust
migration shape without changing alpha behavior. The next Rust review unit should remain a
pure dependency-adjacent contract rather than jumping directly to Linux actuation or adding a
cross-language runtime framework.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005-R5` -> `VPNG-M001-R1.R1`
- `VPNG-U005-R5.R6` -> `VPNG-M001-R1.R1.R6`
- `VPNG-U007-R7.R8` -> `VPNG-D001-R1.R1.R8`
- `VPNG-U007-R7.R8.C1` -> `VPNG-D001-R1.R1.R8.C1`
- `VPNG-U007-R7.R8.R1` -> `VPNG-D001-R1.R1.R8.R1`
- `VPNG-U007-R7.R8.R2` -> `VPNG-D001-R1.R1.R8.R2`
- `VPNG-U007-R7.R8.R3` -> `VPNG-D001-R1.R1.R8.R3`

The original IDs in the historical body are intentionally preserved.
