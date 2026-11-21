# NG3 rou Rust transition ordering correction review

**Date:** 2026-11-19  
**Cycle:** `ng3-design-cycle-20261119-post-probing-frontier-35m`  
**Scope:** development-ordering correction for `VPNG0007-R7.R8`.

## Finding

The cycle began porting already-proven pure availability contracts to Rust because
`VPNG0007-R7.R8` defines Rust as the production runtime language and the immediate pure
contracts were technically safe to port.

That ordering was nevertheless wrong for the current project phase.

`VPNG0007-R7.R8.C1` explicitly permits early alpha/beta releases to remain on the Python
reference implementation so product semantics, integration applicability and operational
behavior can be proven before paying migration cost. Porting `rou` while significant `rou`
decisions are still changing creates two executable implementations that must be kept in sync
and consumes development effort without improving current product evidence.

## Normative correction

Added `VPNG0007-R7.R8.C2`:

- the Rust transition of production `rou` is not current development work while the target
  `rou` decision set is still changing or lacks sufficient Python evidence;
- the relevant `rou` behavior must first exist as one coherent executable Python reference;
- that Python reference must be exercised by sufficient unit/integration/operational evidence;
- until that gate is satisfied, new Rust `rou` ports, production cutover work and expansion
  of the Rust runtime surface are postponed;
- after the gate, Rust migration is implementation replacement preserving the already proven
  contracts.

This is a development-ordering Constraint, not a relaxation of the final Rust production
boundary.

## Existing Rust snapshots

Main snapshots 123–125 already contain small safe-Rust parity prototypes for:

- availability confirmation;
- availability effective-order calculation;
- bounded availability routing-state projection.

They are retained in history and tree as **frozen prototypes**, not as an active migration
frontier and not as a reason to dual-maintain evolving semantics.

Before eventual reuse after the Python-completion gate, they require re-review against the
then-current accepted Python contracts.

The unsnapshotted Rust `AvailabilityManager` / probe-context work started later in this CD
was removed from the working branch and is not published to `main`.

## Architecture correction

The active architecture now states:

```text
changing rou semantics
    -> Python executable reference
    -> unit/integration/operational proof
    -> Python-completion gate
    -> Rust production implementation replacement
```

No further Rust runtime surface is part of the current project frontier before that gate.

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

The production-language target remains Rust, but the active development frontier returns to
Python `rou` until its intended behavior is coherently implemented and proven.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG0005-R5` -> `VPNG9101-R1.R1`
- `VPNG0005-R5.R6` -> `VPNG9101-R1.R1.R6`
- `VPNG0007-R7.R8` -> `VPNG9001-R1.R1.R8`
- `VPNG0007-R7.R8.C1` -> `VPNG9001-R1.R1.R8.C1`
- `VPNG0007-R7.R8.C2` -> `VPNG9001-R1.R1.R8.C2`

The original IDs in the historical body are intentionally preserved.
