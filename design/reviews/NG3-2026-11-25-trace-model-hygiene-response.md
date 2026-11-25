# NG3 trace/model hygiene external-review response — 2026-11-25

**Review unit:** external trace/model hygiene findings and regression-gate hardening  
**External review:** `design/reviews/NG3-2026-11-25-external-trace-model-hygiene-review.md`  
**Reviewed implementation head:** `d772f9595e3989e1f4bf77b242a6d7ae9e2d2043`  
**Evidence:** `EV-00290`

## Verdict

**PASS — all accepted repository findings are fixed, the A.006 typed-edge blind spot is now
mechanically rejected, and no parallel validator was introduced.**

## Findings and dispositions

### F1 — A.006 contained a dangling Requirement edge after inline Constrained by

**Decision:** accepted.  
**Resolution:** fixed.

`VPNG-D001-R1.R1.R5` is now a canonical A.006 `Implements` edge with
[`full`] materialization. `VPNG-U003-R3.R8.C1` remains a Constraint and is represented
only in list-form `Constrained by`. All remaining inline `Constrained by: ID` forms were
normalized to the same list grammar.

The gate now rejects inline trace headings and any `- VPNG-...` trace-looking line outside
the canonical block or with the wrong edge syntax. Both Requirement and Constraint parser
entry points invoke the same syntax validator.

### F2 — EV-00110 exposed stale C.001 partial-for-R8 wording

**Decision:** accepted.  
**Resolution:** fixed.

EV-00110 remains immutable historical evidence of the lower seam, but its registry entry now
distinguishes the historical baseline disposition from current materialization. Current
composition/runtime/currentness is explicitly superseded by EV-00200, EV-00210 and EV-00280;
the old C.001 gap is not presented as current state.

### F3 — component-local Evidence field had no stated optionality rule

**Decision:** accepted.  
**Resolution:** fixed.

Architecture §2.9.1 now states that component-local `Evidence:` is optional. Evidence may be
shared/cross-component; absence of a local field does not alter `full|partial|none`.
When the field exists, its payload remains restricted to registered EV addresses.

### F4 — Coverage nodes semantics existed only in the gate

**Decision:** accepted.  
**Resolution:** fixed.

Requirement model §14 now defines neutral `Coverage nodes:` as an exact non-component
architecture reference for cross-cutting/root/parent contracts. It does not create a third
component-edge type. For Constraints the accompanying architecture-coverage text must expose
the limiting semantics rather than relying on neutral ID presence alone.

### F5 — materialization explanation labels were ad hoc

**Decision:** accepted.  
**Resolution:** fixed.

Current component specs use one canonical `Материализация:` label. R8-specific and
`Пробел материализации` labels were removed; the actual R/C and gap remain in the prose.
The gate rejects those old label forms and requires the canonical explanation label for every
non-full Requirement edge.

### F6 — projectholder terminology still had current synonyms

**Decision:** accepted.  
**Resolution:** fixed.

The already-established token `projectholder` remains canonical and is now explicitly
classified by PROJECT-CONVENTIONS as a literal role identifier. Current AGENTS, conventions,
requirement model and NG3 requirements are gated against spaced, hyphenated and Russian
synonyms, including whitespace-split `project holder`. Frozen release records and historical
reviews are not rewritten.

### F7 — open Requirement with full component edges was semantically underspecified

**Decision:** accepted.  
**Resolution:** fixed.

Architecture §2.9 now states explicitly that [`full`] is local to one component edge and
does not imply Requirement closure. An [`open`] Requirement may therefore have one or more
[`full`] component contributions while another required architecture contribution or
acceptance remains unresolved.

### F8a — requirements-model §6 heading hierarchy was wrong

**Decision:** accepted.  
**Resolution:** fixed.

§6.1–§6.6 are now level-3 children of §6 and their named subsections are level 4.

### F8b — closed aggregation rule was duplicated

**Decision:** accepted.  
**Resolution:** fixed.

§19 now refers to the canonical exact/aggregated architecture-coverage rule in §14 instead of
repeating a second prose formulation.

### F8c — alpha_runtime.py traces to many components

**Decision:** rejected as a defect.

The runtime file is the current composition root and legitimately participates in multiple
component realizations. The manifest already expresses this as an explicit many-to-many trace.
Forcing one component owner would make the trace less truthful; no change was made.

### Ancillary note — duplicate requirements-model delivery copies

**Decision:** rejected as a repository finding.

The duplicate names described by the reviewer were copies in the review delivery, not two
canonical repository model files. The repository continues to own one current
`design/requirements-model.md`; no repository deletion is required.

## Evidence

- implementation/hygiene commit: `d7be525227c745ce3f0817eff4698e2ded74b279`;
- corrective hierarchy/whitespace-role commit: `d772f9595e3989e1f4bf77b242a6d7ae9e2d2043`;
- GitHub Actions `NG3 Python` run `45616634226`: **25/25 PASS**;
- unit job `139213608704`: **PASS**;
- actual-main lineage run `45616634403`: **PASS**.

The external request for AGENTS/CD/status-basis/component-model/R8.R6 materials is not a
finding in this unit. Those materials were supplied separately for the reviewer's later pass.

No standalone CI script was added: useful checks from the external review were folded into
the existing `test_architecture_traceability.py` gate.
