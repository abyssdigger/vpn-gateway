# NG3 2026-11-22 — current experiment trace migration cleanup review

**Scope:** remove migrated `VPNG-U005/0006/0007` IDs from current experiment requirement-trace
sections while preserving them in historical baseline text and migration notes.

## Verdict

**PASS — TRACEABILITY CLEANUP COMPLETE.**

## Finding

The requirement-ID restructure correctly preserved historical experiment bodies and added
migration notes, but four dossiers still used old IDs in their current
`Requirement trace` / `Requirement traceability` / `Requirements` sections. That made
historical provenance correct while leaving the active applicability trace stale.

## Resolution

Current trace sections were migrated in:

- EXP-050 bounded VPN lifecycle applicability;
- EXP-052 host publication DNAT;
- EXP-061 stack established-flow return affinity;
- EXP-063 Profile association gateway NAT.

Historical body text and `Requirement ID migration` notes were not rewritten.

A mechanical pass over the affected experiment set found **5 current requirement-trace
sections and 0 remaining references to `VPNG-U005`, `VPNG-U006` or `VPNG-U007` in those
sections**.

No requirement, architecture, implementation or evidence semantics changed. No tests are
required for this documentation-only traceability correction.
