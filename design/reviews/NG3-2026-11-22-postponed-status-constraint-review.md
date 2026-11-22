# NG3 2026-11-22 — postponed requirement status and constraint-backed frontier review

**Scope:** introduce normative `postponed` status and apply it to requirements already
accepted as outside the current Release-1/development frontier.

## Verdict

**PASS — ACCEPT MODEL CHANGE AND POSTPONEMENT CLASSIFICATION.**

## Model decision

`postponed` is a fourth mutually exclusive value of the same closure/frontier status enum:

```text
pending_closure | closed | rejected_closure | postponed
```

It is independent of `decomposition: complete|incomplete`.

A postponed node remains a normative Requirement/Constraint, but further decomposition,
architecture closure, implementation and/or acceptance are explicitly outside the current
development/release frontier until re-entry.

Direct `postponed -> closed` is permitted. It requires an applicability/re-entry review
showing that the requirement meaning is still current and that already-existing architecture
and evidence are sufficient for that exact node. An artificial intermediate
`pending_closure` state is not required.

## Release-1 capability postponements backed by accepted constraints

### Per-path Device firewall

Postpone:

- `VPNG-U001-R1.R4.R2.R1`;
- `VPNG-U001-R4.R4.R6.R2.R5`.

Accepted Release-1 constraints:

- `VPNG-U001-R1.R4.R2.R1.C1` — Release 1 may apply additional restrictions only at
  whole-Device/resource scope;
- `VPNG-U001-R4.R4.R6.R2.R5.C1` — Release-1 config need not expose a per-path selector.

Both constraints are decomposition-complete and are closed by this review. The ordinary
Device-wide firewall remains inside Release 1 and is not postponed.

### Aggressive host-routing helper

Postpone:

- `VPNG-U001-R5.R2`;
- `VPNG-U001-R5.R2.R2`;
- `VPNG-U001-R5.R2.R3`.

Existing accepted constraint:

- `VPNG-U001-R5.R2.C1` — already `closed`; Release 1 need not provide the aggressive
  helper or its continuous-recovery/unrecoverable-alarm guarantees.

The already closed `VPNG-U001-R5.R2.R1` and EXP-074 evidence remain valid partial future
evidence. A closed child does not force its postponed parent back into the active frontier.
The Release-1 peaceful helper remains unaffected.

### Administrative protective mode

Postpone:

- `VPNG-U004-R5`.

Accepted Release-1 constraint:

- `VPNG-U004-R5.C1` — Release 1 need not provide the separate administrative protective
  mode; existing mandatory fail-closed core guarantees remain in force.

The constraint is decomposition-complete and is closed by this review.

## Explicit deferral-backed postponements

The new model status should also represent previously explicit future deferrals rather than
leaving them unlabeled.

### Developer execution trace

Postpone:

- `VPNG-D001-R2`;
- `VPNG-D001-R2.R1`–`R4`.

The accepted need remains normative. The separate trace deferral defines re-entry and requires
the future owner to complete the four descendant contracts before architecture/implementation.

### Raspberry Pi 2 resource envelope

Postpone:

- `VPNG-M001-R3.R2`;
- `VPNG-M001-R3.R2.R1`.

The Pi 2 workload/envelope remains an accepted future target and explicitly not a current
release gate. Its deferral defines the benchmark-methodology re-entry conditions.

## Non-postponed neighboring work

This review intentionally does **not** postpone the Device-wide restriction parent
`VPNG-U001-R1.R4.R2` or its Release-1 config parent
`VPNG-U001-R4.R4.R6.R2`: the Device-wide firewall is current Release-1 functionality.

Likewise this review does not postpone peaceful host routing, current fail-closed safety,
ordinary Profile availability or other active Release-1 obligations.

## Consistency rule

After this review, `pending_closure` means a current closure candidate awaiting acceptance;
it must no longer be used merely as a visual marker for "maybe later".

`postponed` means "accepted normative future work, explicitly outside the current frontier"
and must carry a review/evidence basis and re-entry semantics.
