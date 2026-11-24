# NG3 — forward semantic compiler readiness review

**Дата:** 2026-11-16  
**Branch:** `ng3-design-cycle-20261116-forward-policy-evidence-40m`

## Scope

Readiness review for the next pure semantic compiler after the accepted strict
observer and lower actual-vs-desired comparison. No implementation in this
review.

## Requirements

**Implements / constrains future design:** `VPNG-U002-R2.R1.R2`,
`VPNG-U002-R2.R3.R3`, `VPNG-U002-R2.R5.R1`,
`VPNG-U001-R1.R2.R4.R6.R2`, `VPNG-U004-R4.R1`,
`VPNG-U004-R4.R3.R2`.

## Findings

**F-01 — ACCEPTED DESIGN REQUIREMENT: outbound overlap must be partitioned.**
A union of broad/specific allow CIDRs can permit a packet on a path allowed
only by the broader Profile after routing drift. The filter must independently
preserve the most-specific Profile path decision. Candidate solution:
canonical disjoint CIDR fragments assigned to the selected outbound Profile.

**F-02 — ACCEPTED DESIGN REQUIREMENT: inbound partition is path-relative.**
The requirement explicitly restricts inbound candidate Profiles by actual
ingress Device/path *before* most-specific selection. Therefore inbound source
partition must be computed independently per logical ingress path; a
more-specific prefix belonging only to another Device must not shadow a valid
broader Profile on this ingress.

**F-03 — ACCEPTED DESIGN REQUIREMENT: return uses the same selected fragments.**
Stateful reverse permission must retain the exact remote fragment and reverse
interface pair proved by EXP-036. A generic established rule is insufficient.

**F-04 — BLOCKING GATE FOR COMPLETE COMPILER: Device envelope contract.**
The accepted product invariant says Device envelope is restrictive intersection,
and recovered prototype evidence includes source/destination prefixes, protocol
and ports. Exact NG3 normalized grammar/lower semantics for those dimensions are
not accepted. Current `PayloadForwardRuleSpec` cannot represent protocol/port
restrictions. Implementing a “complete” compiler now would silently ignore a
possible supported restriction and violate the requirement.

Disposition: do not invent envelope fields. A separately named **no-envelope
reference slice** may be implemented later if useful, but complete production
compiler remains gated until the envelope contract or release-scope decision is
accepted.

**F-05 — SIMPLIFICATION: keep positive-only/default-drop if possible.**
No accepted scenario currently requires deny-rule ordering/jumps solely for
Profile prefix overlap. Disjoint CIDR subtraction should be tested first
against point classification before adding a more complex nft policy graph.

## Verdict

**PASS as readiness/design finding; IMPLEMENTATION OF THE COMPLETE SEMANTIC
COMPILER REMAINS GATED.**

The completed lower observer/comparison units remain valid and independent of
this gate.
