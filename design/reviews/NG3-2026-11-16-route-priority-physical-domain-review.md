# VPN-GATE NG3 — Physical Route-Priority Domain Design Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-primary-requirements-basis-40m`

## Discovery

While preparing the physical Linux owned-route inventory boundary, the existing pure
convergence model exposed a representational ambiguity.

A Profile can contain multiple destinations. The kernel therefore may contain multiple
route rows for the same logical path, one per destination/route key.

A physical failure can occur between mutation of those rows.

Example:

```text
destination D1:
    path A -> metrics 10, 30   # add-new completed, delete-old not yet done

destination D2:
    path A -> metric 10        # old state
```

If both destinations were aggregated into one `path A -> {10,30}` snapshot, the planner
could not tell which route key actually has the duplicate. That would destroy the
authoritative-state property required by the Executor recovery contract.

## Classification

**Design insufficiency discovered before physical implementation.**

No product requirement is missing.

Relevant accepted requirements already constrain the answer:

- `VPNG0004-R4.R2` — do not treat unconfirmed desired state as actual;
- `VPNG0004-R4.R3.R1` — priority-only transition must retain every eligible path;
- `VPNG0004-R4.R5` — after partial mutation, re-establish authoritative actual state;
- `VPNG0005-R5.R2` / `R5.R3` — recover from current owned state, not stale command history.

## Resolution

Define one **priority convergence domain** as one independently observable owned route key
inside the Profile routing domain.

The current `logical_path -> metrics` convergence model is valid only inside that domain.

A Profile with multiple route keys is converged as multiple bounded domains. Profile-level
completion requires fresh verification of every affected domain.

This keeps partial physical state representable without adding a transaction journal.

## Safety

The resolution does not weaken the accepted make-before-break invariant.

For every route-key domain during a priority-only transition:

- every eligible path remains represented;
- no ineligible path is introduced;
- duplicate route copies are allowed only for the same already-eligible path;
- after failure, the next attempt starts from fresh observation.

Different route-key domains may be at different intermediate stages while convergence is in
flight. The requirements do not promise an atomic all-prefix metric permutation; they do
require safe membership throughout and verified configured order after convergence.

## Complexity review

This resolution is simpler than introducing:

- a cross-prefix transaction journal;
- a replay log;
- a synthetic aggregate state that attempts to encode every partial row combination.

It also matches the existing requirement to prefer current authoritative state over replay.

## Verdict

**PASS — architecture clarified.**

Physical route observation can now be implemented against one route-key domain without
losing partial-failure state.
