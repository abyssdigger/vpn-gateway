# VPN-GATE — mainline snapshot semantics and history repair review

**Date:** 2026-11-16  
**Branch:** `ng3-process-snapshot-semantics-20261116`

## Scope

Review and normalize the project process for publishing logical development snapshots to
`main`, after intermediate working-branch commits were accidentally imported into mainline
history after snapshot 49.

## Repaired mainline

Snapshot 49 remains:

```text
62d86f584649b7736d3f3fa16e75eea9b3dd74e0
Main snapshot 49: unreal method, grammar deferral and four-chain nft scaffold
```

The post-49 mainline was reconstructed as exactly three logical snapshots:

```text
50  d277abb345b50da259a59df0202d1d6db593320c
    Device firewall lower structural observer
    source tree: 05d2e402b1945806d8256600d497038335081b53

51  aa2195f567124679c7a6fab7fa55c9f3869df75a
    Device firewall compiler and guarded mutation
    source tree: cb49feda7e75a030626f5510ace60255a7001c1e

52  e27ba8d2e041f3e77ed25f9bedcf41f872a86366
    combined Profile Device NAT nft convergence
    source logical result tree: f983046ceea352acb8d0a00bdad6c8970f70964d
```

Mechanical comparison from snapshot 49 to snapshot 52 reports exactly three commits. The
intermediate development history beginning with `db852d6b…` remains on the working branches
and is no longer in `main` ancestry.

The old incorrectly numbered `7dbbe11c…` commit is superseded by snapshot 52; its logical
result tree is preserved, while the snapshot number and ancestry are corrected.

## Process findings

### F1 — CD-window and logical-snapshot terminology was inconsistent

`CONTINUOUS-DEVELOPMENT.md` already described the CD cycle as a session-safety window, but
`AGENTS.md` still said to snapshot the final state of each completed development cycle.

**Disposition:** fixed. `AGENTS.md` now defers to normative `CD-SNAPSHOT-R1..R7`.

### F2 — one-commit mainline publication was insufficiently mechanical

The old text said “one linear snapshot commit” but did not explicitly require candidate
parent/tree checks or prove that source branch ancestry was excluded.

**Disposition:** fixed by `CD-SNAPSHOT-R2` and `CD-SNAPSHOT-R5`:

- one logical snapshot = exactly one new mainline commit;
- parent = previous accepted main snapshot;
- tree = exact selected source commit tree;
- previous snapshot -> candidate comparison must report `ahead_by = 1`;
- source branch intermediate commits never enter main ancestry.

### F3 — source snapshot state may precede working-branch HEAD

A branch can already contain unfinished work for the next logical block.

**Disposition:** fixed by `CD-SNAPSHOT-R3`: every snapshot records an exact
`SOURCE_SNAPSHOT_COMMIT`; current branch HEAD is not implicitly the source.

### F4 — snapshot numbering was not stated as an invariant

This allowed a logically correct tree to retain an obsolete snapshot number after history
repair.

**Disposition:** fixed by `CD-SNAPSHOT-R4`: gap-free chronological numbering, including
renumbering after an explicitly approved reconstruction.

### F5 — CHANGELOG policy needs future synchronization without NG3 churn

**Disposition:** fixed by `CD-SNAPSHOT-R7` and `PROJECT-CONVENTIONS.md`:

- during active NG3, per-snapshot CHANGELOG edits are deferred;
- NG3 snapshot results are reconciled/backfilled at NG3 closure;
- after NG3, each snapshot includes a concise corresponding CHANGELOG entry unless a later
  explicit project decision changes the rule.

No CHANGELOG edit is made by this process block.

## Documents changed

- `CONTINUOUS-DEVELOPMENT.md` — normative `CD-SNAPSHOT-R1..R7`;
- `AGENTS.md` — operational workflow aligned to logical snapshots;
- `PROJECT-CONVENTIONS.md` — concise mainline snapshot and stage-gated CHANGELOG rules.

## Verification

- old “final state of each completed development cycle” snapshot wording is absent from the
  updated process documents;
- `CD-SNAPSHOT-R1..R7` are present in the normative CD document;
- mechanical `ahead_by = 1` verification is explicit;
- NG3 CHANGELOG deferral/backfill is explicit;
- repaired mainline from snapshot 49 contains exactly snapshots 50, 51 and 52.

## Requirement-state impact

This is project-process governance only; it does not change VPN-GATE product requirements.

- `decomp`: unchanged; current six links remain resolved, pending none.
- `unreal`: none.
- `[rejected_closure]`: none.
- human product decision: none.

## Verdict

**PASS.** Snapshot publication is now explicitly tied to logical development blocks and
mechanically excludes working-branch history from `main`.
