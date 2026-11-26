# NG3 2026-11-26 — follow-up external documentation review

**Status:** complete / current-main re-check  
**Reviewed baseline:** `main@729096f2d056d9c797fa61dc942a679b78e5e010`  
**Source:** projectholder-provided follow-up from the external reviewer; the source review was based on documents roughly two days older than this baseline.  
**Purpose:** separate still-actionable findings from points already corrected by later project work.

## Verdict

The external review remains useful, but several findings are already obsolete on current `main`.

Current disposition:

- **4 findings remain materially actionable**;
- **3 findings remain useful as low-priority process/documentation hardening**;
- **5 findings are already resolved or are historical/frozen-record effects rather than current defects**.

No product/runtime semantics are changed by this review.

## Findings

### F1 — A.006 / `VPNG-D001-R1.R1.R5` traceability hole

**External finding:** a status line could sit outside both `Implements` and `Constrained by`, and the parser would miss it.

**Current result:** **RESOLVED for the reported instance; generic parser hardening still useful.**

On current architecture, `VPNG-D001-R1.R1.R5` is explicitly inside A.006 `Implements`, before `Constrained by`.
The concrete reported A.006 hole no longer exists.

The generic defensive test remains worthwhile: every architecture line matching a requirement ID plus
materialization status should be required to occur inside an `Implements` block. That is a tooling-hardening
candidate, not a currently observed traceability defect.

### F2 — `requirement-status-basis.md` postponed set

**Current result:** **PASS / RESOLVED.**

The registry still names exactly the eight current postponed nodes:

- `VPNG-D001-R2` + four descendants;
- `VPNG-M001-R3`, `VPNG-M001-R3.R2`, `VPNG-M001-R3.R2.R1`.

The referenced deferral artifacts exist in the repository and are already used by current reviews and release
coverage.

A separate low-priority process issue remains under F9: the common lifecycle/schema of deferral artifacts is
not described in one obvious owner document.

### F3 — R8 review said A.004/C.001 partial while architecture said full

**Current result:** **RESOLVED.**

The later dedicated review
`design/reviews/NG3-2026-11-25-r8-materialization-status-review.md`
explicitly recognized the old `partial` annotations as stale and corrected A.004/C.001 R8 materialization to
`full`.

The old R8.R6 review is historical evidence and should not be rewritten to match later status cleanup.

### F4 — frozen release coverage has 220 nodes while current tree has grown

**Current result:** **NOT A CURRENT DEFECT; historical snapshot behavior is correct.**

The release-attempt-2 coverage is candidate-bound and intentionally frozen. It must not be updated to current
`main` merely because the live tree later grew.

The external review correctly predicted that future release preparation must handle open nodes. Current
`PROJECT-CONVENTIONS.md §10.3` already does: `open`, `pending_closure`, and `rejected_closure` must preserve
their actual status and receive an explicit release disposition. The previously noted “no dictionary value for
open” gap therefore no longer exists.

### F5 — release scope says all permanent requirements remain conformance obligations, then excludes M001-R5

**Current result:** **ACTIONABLE / HIGH.**

`release/0.1.0/RELEASE-SCOPE.md` currently states:

> Permanent requirements remain conformance obligations.

but later explicitly exercises `VPNG-M001-R5.C1` and says the release does not require the
`VPNG-M001-R5*` family.

Those statements are not textually compatible without an explicit exception rule.

Recommended correction for the next active release scope/model revision:

- define the baseline as “permanent requirements remain conformance obligations **except where an applicable
  normative Constraint explicitly permits release omission and the approved release scope exercises it**”; or
- express the baseline in terms of the requirement/constraint frontier selected by approved omissions, then
  apply `conformance-applicable` only to permanent nodes still inside that frontier.

Do not silently retrofit a frozen historical release record unless that release candidate is deliberately
reopened.

### F6 — supported integration set is not normative in approved release scope

**Current result:** **ACTIONABLE / HIGH.**

Current methodology says the concrete mandatory documentation walkthrough set is derived from:

1. approved `RELEASE-SCOPE.md`; and
2. published administrator/user documentation.

But the approved 0.1.0 scope says only “release-supported integration boundary” and does not explicitly name
WireGuard, OpenConnect, or L2TP/PPP.

The concrete trio appears in `DEPLOYMENT.md`, QA, and fulfillment evidence. Therefore a missing integration in
published documentation could potentially shrink the tested set instead of being detected as a scope
violation.

This also conflicts with `PROJECT-CONVENTIONS.md §10.1`, which requires the approved release scope to state
explicitly included capabilities/feature families.

Recommended fix for future release scope:
explicitly enumerate the supported VPN integration families that the release commits to, while keeping the
generic §10.4 methodology technology-neutral.

### F7 — QA / coverage / frozen-candidate SHA relationship

**Current result:** **ACTIONABLE / MEDIUM, narrower than the external finding.**

The final fulfillment review *does* connect the important identities:

- reviewed frozen candidate: `8055eb0dd655de91a7a93e77669e426493dbc6e6`;
- project-snapshot requirement blob: `9bb6cb44...`;
- project-snapshot architecture blob: `dea03313...`;
- exact frozen-candidate workflow: `45313940729`;
- exact frozen-candidate release QA job: `138176107360`.

So the identities are not globally unconnected.

However, the persistent `release/0.1.0/QA-REPORT.md` still identifies:

- tested release-set head `a48350396c6ff22f06ca6f59e404a6e9e38c040b`;
- workflow `45313040992`;

and does not name the final frozen candidate `8055eb0...`.

Thus the final exact-candidate rerun is evidenced only by the fulfillment review, while the QA record itself
still describes the predecessor tested state.

Recommended rule for the next release attempt:
the final candidate-bound QA record should itself identify the exact candidate/run it claims, or explicitly
state a permitted predecessor-QA relation and the proven non-affecting delta under §10.4. Do not rely solely on
a later fulfillment review to repair the identity chain.

### F8 — ownership of `PROJECT-CONVENTIONS.md §10` release methodology

**Current result:** **ACTIONABLE / MEDIUM.**

`AGENTS.md §7` describes `PROJECT-CONVENTIONS.md` as owning project-artifact maintenance conventions:
language, formatting, review/experiment artifact handling, layout/lineage, naming and CHANGELOG.

But `PROJECT-CONVENTIONS.md §10` is a substantial normative release-development methodology, not merely
artifact maintenance.

`PROJECT-CONVENTIONS.md §9` likewise lists “this document” mainly as artifact/layout/lineage/CHANGELOG owner
without explicitly naming release methodology.

Recommended fix:
make release methodology an explicit ownership subject of `PROJECT-CONVENTIONS.md` in both responsibility
maps, or move §10 to a dedicated owner document. The smaller change is sufficient; no duplication is needed.

### F9 — `CDC` abbreviation is used but not defined

**Current result:** **ACTIONABLE / LOW.**

The term now appears in `AGENTS.md`, `EXECUTION-LOOP.md`, `CONTINUOUS-DEVELOPMENT.md`, reviews and branch
names, but no governing document defines what the second C means or whether `CD` and `CDC` are exact
synonyms.

Recommended fix:
one definition at the loop/development entry point, e.g. “CD/CDC are accepted activation aliases for the
continuous-development overlay; they have identical process semantics.” Avoid trying to reverse-engineer a
historical expansion if none is normative.

### F10 — deferral artifact lifecycle is distributed rather than explicitly owned

**Current result:** **ACTIONABLE / LOW.**

The current status-basis registry states that a referenced deferral contains reasons, scope boundaries and
re-entry conditions. Existing deferral files are actively referenced and validated.

What is still missing is one compact owner contract for:

- when a deferral record is required;
- minimum fields/content;
- relation between `postponed` requirement status and the deferral artifact;
- how re-entry invalidates/updates the current status basis without rewriting history.

This is process/documentation hardening, not evidence that current postponed statuses are unsupported.

### F11 — “development block completion” vs active-CD authorization wording

**Current result:** **RESOLVED.**

The older wording that looked contradictory is no longer present in the reported form. Current authority rules
separate mutation authorization from local unit/block completion and explicitly require active CD context for
CD-derived publication authority.

No change needed from this finding.

### F12 — clock checks only after commits

**Current result:** **RESOLVED.**

Current `EXECUTION-LOOP.md §6` requires fresh real time:

- at overlay-defined unit/block/handoff boundaries;
- after bounded WAIT;
- before `PRE_FINAL_GATE`;
- whenever elapsed-time uncertainty threatens the safety reserve.

This closes the long-block/no-commit hole identified by the external review.

### F13 — `REF-HYGIENE.tsv` is defined only in AGENTS

**Current result:** **ACTIONABLE / LOW.**

The canonical ledger and its helper scripts are defined operationally in `AGENTS.md`, while
`PROJECT-CONVENTIONS.md` contains no repository-layout entry for `REF-HYGIENE.tsv`.

Because the ledger is both an authorization-sensitive operational mechanism and a root repository artifact,
the clean split is:

- keep operation/authorization semantics only in `AGENTS.md`;
- add a short layout/reference entry in `PROJECT-CONVENTIONS.md` saying the root file is the canonical
  deferred ref-hygiene ledger and deferring all execution rules back to `AGENTS.md`.

### F14 — hard-coded `ng3-...-source` tag naming

**Current result:** **LOW-PRIORITY MAINTAINABILITY ISSUE.**

`AGENTS.md` currently hard-codes NG3 source-tag naming. That is acceptable for the current generation but is
not generation-neutral governance.

No immediate defect exists. Before a new normative generation, move the generation-specific naming pattern to
project conventions/configuration or define a stage-derived naming rule.

## Recommended action order

1. Fix future/current release-scope semantics for permanent omissions (F5).
2. Make supported integration families explicit in approved release scope (F6).
3. Tighten candidate-bound QA record identity (F7).
4. Clarify §10 ownership (F8).
5. Add the generic architecture-status-line parser guard (F1 hardening).
6. Clean up CDC definition, deferral lifecycle and REF-HYGIENE layout reference (F9/F10/F13).
7. Leave frozen historical reviews/coverage untouched unless a release candidate is explicitly reopened.

## Overall assessment

The external reviewer again found useful boundary defects, but current project work has already eliminated
several of the concrete inconsistencies in the older document set.

The highest-value remaining issues are not runtime defects. They are release/governance identity problems:
scope wording, explicit release capability enumeration, and candidate-bound evidence identity.
