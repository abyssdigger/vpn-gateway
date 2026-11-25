# NG3 typed architecture trace and stable-evidence gate review — 2026-11-25

**Review unit:** typed Requirement/Constraint architecture traceability and stable evidence-address enforcement  
**Reviewed implementation head:** `ede2432af7dd2cbf32e8b13084bff37a14ec5e83`  
**Requirements/model:** `VPNG-D001-R1.R1.R6`, `VPNG-D001-R1.R1.R6.R1`; `design/requirements-model.md` §14  
**Evidence:** `EV-00250`

## Verdict

**PASS — architecture coverage is now checked through structured trace edges rather than arbitrary ID presence, component edges preserve Requirement/Constraint semantics, and stable architecture Evidence fields accept only registered EV addresses.**

The current Python manifest is also explicitly named as the current executable reference implementation trace rather than the target production implementation trace.

## Findings and dispositions

### F1 — Constraint IDs were accepted as Implements edges

**Disposition:** accepted / fixed.

The previous parser treated every `VPNG-*` entry under Implements-like headings as the same edge type. Three live Constraint nodes were therefore represented as materialized Requirements:

- `VPNG-U001-R1.R3.R8.R2.C1`;
- `VPNG-U003-R3.R8.C1`;
- `VPNG-M001-R2.R3.R6.C1`.

They now appear only under `Constrained by`. The gate derives node kind from the canonical requirement-tree ID leaf and rejects future type mismatches.

### F2 — E.002 used Requirement nodes as constraints

**Disposition:** accepted / fixed.

`VPNG-D001-R1.R1.R8` and `VPNG-D001-R1.R1.R8.R3` were removed from E.002 `Constrained by`. The host-routing helper remains constrained by the applicable C1/C2/C3 language-transition constraints.

### F3 — arbitrary prose mention could satisfy closed architecture coverage

**Disposition:** accepted / fixed; additional hidden gap found.

The old closure test considered a closed node directly covered whenever its backticked ID appeared anywhere in the architecture. The replacement uses only structured component edges, the explicit §2.10 coverage index and explicit `Covers` blocks, then applies recursive complete-child aggregation.

The first semantically working run exposed that removing the false E.002 edges left `VPNG-D001-R1.R1.R8` and `.R8.R3` without structured direct coverage. §2.9.3 already owns those target-Rust/Python-reference semantics, so its explicit `Covers` list was corrected rather than restoring the false E.002 relationship.

### F4 — stable Evidence test checked only direct EXP IDs

**Disposition:** accepted / fixed.

A.011 still embedded integration-test and release-QA paths directly after `EV-00030`. Stable architecture now contains only the EV address. The gate parses every `Evidence:` field, rejects any non-EV payload and verifies every referenced `EV-xxxxx` exists in `evidence-index.md`.

### F5 — Python reference trace used target-production terminology

**Disposition:** accepted / fixed.

`implementation-traceability.md` now describes the **current executable Python reference implementation**. The exhaustive file check uses the same terminology. This avoids conflating the currently executable early-release/reference implementation with the Rust target production boundary in `VPNG-D001-R1.R1.R8*`.

## Executable evidence

- architecture/trace normalization: `9c783607e60ec942715ece6da0ce223679a09b4d`;
- typed/structured gate: `ac0580322253ade6ca79f4a628ca0a19dbbbd70c`;
- harness-regex correction: `1655e6a44deffeb19a707c593c4efab9290733b4`;
- structured Rust-boundary coverage correction: `ede2432af7dd2cbf32e8b13084bff37a14ec5e83`;
- initial exact-head gate run `45594192220`, unit `139135979955` — FAIL due to generated regex escaping; fixed;
- next exact-head run `45594442459`, unit `139136850531` — FAIL usefully exposed missing structured R8/R8.R3 coverage; fixed;
- final implementation-head run `45594591421`, unit `139137371221` — **PASS**;
- actual-main lineage run `45594591509` — **PASS**.

## Remaining scope

This unit intentionally does not rewrite §2.10 terminology or release methodology. Those are separate documentation/process review units. The strengthened gate now prevents the specific semantic trace/evidence regressions found here.
