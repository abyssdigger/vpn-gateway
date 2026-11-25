# NG3 owner-scoped probe readiness review — 2026-11-25

**Review unit:** C.001 owner-scoped readiness over a shared physical probe plane  
**Reviewed implementation head:** `ff608b8b6fda124dfd8e98b0a365c2f5faad066b`  
**Architecture:** C.001  
**Evidence:** `EV-00160`

## Verdict

**PASS — scoped readiness can now distinguish semantic consumers without weakening full-union ownership safety.**

The new verifier takes the fresh physical snapshot, the complete accepted probe desired union
and an explicit requested owner subset. Mutation/convergence semantics are unchanged and
remain whole-union responsibilities.

## Findings and dispositions

### F1 — sibling accepted state must not be stale for a scoped consumer

**Decision:** accepted.

Scoped routing/local readiness derives requested confirmed/missing state from the requested
subset, but derives stale/conflict state from the complete accepted union. Therefore valid
A.007 state does not block a D.002 peer probe and valid D.002 state does not block A.007.

### F2 — missing sibling state must not become a global readiness failure

**Decision:** accepted.

A missing accepted sibling affects that sibling's own readiness but is not a reason to reject a
fully exact requested owner. Focused evidence proves this while the legacy whole-union verifier
continues to reject the same incomplete full plane.

### F3 — unknown owned physical state remains globally fail-closed

**Decision:** accepted.

Any reserved probe route/rule/local object not attributable to the complete accepted union
remains stale/conflicting in every scoped verdict. Scoped projection therefore cannot hide
foreign or obsolete state by labelling it “sibling”.

### F4 — shared nft physical identity does not merge semantic evidence

**Decision:** accepted.

Probe semantic owner identity is not encoded in nft. Two semantic owners with identical
endpoint/target/mechanism may therefore share one physical INPUT/OUTPUT pair. The same physical
pair can confirm each requested owner, but each returned precondition contains only that
owner's semantic execution context.

### F5 — legacy whole-scope behavior must remain stable

**Decision:** accepted.

`verify_probe_execution_precondition(snapshot, desired, platform)` retains its complete-plane
semantics. The new behavior is exposed only through
`verify_probe_execution_precondition_scoped(...)`, preventing an implicit contract change for
existing A.007 callers.

### F6 — first focused run contained a test-count error, not a semantic failure

**Decision:** fixed.

Run `45572035349`, unit job `139060769277` failed because the test expected one confirmed
local rule per owner, while a valid owner has the required INPUT+OUTPUT pair. Commit
`ff608b8b6fda124dfd8e98b0a365c2f5faad066b` corrected only that assertion; the final unit
suite passed.

## Evidence

- implementation: `f7b7b3e14f74067ae2a2d3046d5aa11c779e6aaa`;
- assertion correction: `ff608b8b6fda124dfd8e98b0a365c2f5faad066b`;
- final run `45572212707`, unit `139061480440`: **PASS**;
- actual-main lineage run `45572212811`: **PASS**.

## Remaining boundary

This closes the previously identified comparison/readiness seam only. Alpha still does not
compose A.007 and D.002 peer desired state into one full convergence union. Optional
recoverable-group endpoints still need a distinct semantic owner/projection/executor before
D.002 can consume them.
