# NG3 2026-11-22 — structured architecture authority handover review

**Scope:** complete the already-effective migration from the flat NG3 architecture report to
the structured architecture document and remove dual-source ambiguity.

## Verdict

**PASS — `design/NG3/structured-architecture.md` IS THE SOLE CURRENT NG3 ARCHITECTURE SOURCE.**

## Finding

The repository had already functionally moved to the structured architecture:

- production implementation traceability names
  `design/NG3/structured-architecture.md` as its normative architecture;
- the evidence index names the same document;
- mechanical architecture traceability tests read only that document;
- recent architecture components and requirement closures were being added there.

However the structured document header still called itself a projection and said the old flat
`design/NG3/architecture.md` remained authoritative. The old flat report simultaneously
still labelled itself current. That was a real dual-source documentation defect.

## Resolution

`design/NG3/structured-architecture.md` now explicitly states that it is the single current
source for accepted NG3 architecture, component/API/interaction contracts and architecture
closure.

`design/NG3/architecture.md` now carries an explicit **OBSOLETE / superseded** header and
points to the structured document. Its body is retained so historical reviews/research/evidence
can still be read against the pre-structured architecture report they referenced.

Historical references to the flat document are intentionally not rewritten: they identify
their recorded baseline, not a current source of architecture.

## Evidence

This handover changes source-of-truth metadata only. No architecture semantics, component
contracts, requirement closure or implementation changed.

Current live trace machinery already targets the structured document:

- `design/NG3/implementation-traceability.md`;
- `design/NG3/evidence-index.md`;
- `test_architecture_traceability.py`.

The immediately preceding requirement-ID migration workflow `44959465853` passed all 21
jobs and 793 unit tests against the structured architecture baseline.

## Disposition

No active architecture document now claims the flat report as authoritative. New NG3
architecture work must update `structured-architecture.md` only.
