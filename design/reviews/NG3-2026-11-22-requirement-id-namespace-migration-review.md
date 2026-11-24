# NG3 2026-11-22 — requirement ID namespace migration review

**Scope:** owner-requested global, mechanical requirement identifier namespace migration across
the complete current repository tree, including historical review/research/experiment records.

## Verdict

**PASS — ACCEPT GLOBAL IDENTIFIER NAMESPACE MIGRATION.**

## Canonical mapping

The migration is bijective and changes identifier spelling only:

- `VPNG0*` -> `VPNG-U*`;
- `VPNG90*` -> `VPNG-D0*`;
- `VPNG91*` -> `VPNG-M0*`.

Examples:

- `VPNG0001` -> `VPNG-U001`;
- `VPNG0004-R4.R6` -> `VPNG-U004-R4.R6`;
- `VPNG9001-R1.R1` -> `VPNG-D001-R1.R1`;
- `VPNG9101-R2.R2.R4` -> `VPNG-M001-R2.R2.R4`.

Requirement/Constraint suffixes and ancestry are unchanged.

## Scope and historical records

The project holder explicitly required the new namespace to be canonical **everywhere in the
current repository tree**, including historical records. Therefore historical dossiers,
reviews, research notes, migration notes, code comments/tests, evidence records and current
normative/architecture documents were mechanically rewritten.

This is treated as an owner-approved global namespace re-encoding, not as semantic
renumbering. `PROJECT-CONVENTIONS.md` and `design/requirements-model.md` now distinguish
this case from ordinary per-node migration, for which historical baseline IDs remain
preserved.

Published Git object history and old commit messages were not rewritten; doing so would be a
separate destructive history operation and is not required to make the current repository
tree use one canonical namespace.

## Integrity checks

Current requirement tree after migration:

- normative R/C nodes: **187**;
- primary roots: `VPNG-U001`, `VPNG-U002`, `VPNG-U003`, `VPNG-U004`,
  `VPNG-D001`, `VPNG-M001`;
- duplicate normative IDs: **0**;
- malformed/missing decomposition labels: **0**;
- closed: **152**;
- pending closure: **31**;
- closed requirements missing from structured architecture: **0**.

The requirement document now records the three namespace classes explicitly and corrects the
stale pre-restructure “seven primary requirements” wording to the current six roots.

## Mechanical coverage

The migration started from all current-main code-search hits for the three old prefixes.
Broad search returned 211 candidate paths. Exact-content review identified 185 files carrying
actual old-format requirement IDs plus false-positive search matches. All exact old-format
references were transformed; one initially omitted historical review was found by set-diff and
migrated before closure.

The traceability parser itself is format-agnostic
(`VPNG[^\\]]+`) and therefore required no special parser migration.

## Evidence

NG3 Python workflow run `44959465853` on migration commit
`afd1f143aa39fff5867a7f6e53605488614bd3dd`:

- workflow: **PASS**, 21/21 jobs successful;
- unit job `137014910842`: **PASS**;
- **793 tests**, OK.

That run already contained the migrated requirements, structured architecture, active Python
trace comments and affected executable experiment sources. Subsequent migration commits only
rewrote additional review/evidence text or the final historical reference, plus the
requirements namespace legend; they did not change executable behavior or trace parser logic.

## Findings and dispositions

### F1 — historical-preservation convention conflicted with an everywhere namespace migration

**Decision:** accepted.  
**Resolution:** fixed.

A narrow project-holder-authorized global namespace-migration exception was added. Ordinary
semantic ID moves still preserve historical IDs and use migration notes.

### F2 — broad GitHub code search produced false-positive candidate paths

**Decision:** accepted.  
**Resolution:** fixed.

Candidate paths were validated against exact old-format ID syntax. False positives were not
forced into artificial diffs.

### F3 — one exact historical reference was missed by the first manual batching pass

**Decision:** accepted.  
**Resolution:** fixed.

Set-diff plus exact-content verification found
`NG3-2026-11-16-endpoint-provenance-postponement-review.md`; its remaining three old IDs
were migrated before this review.

## Semantic impact

None. This unit changes only the canonical textual namespace of requirement identities.
Requirement meaning, ancestry, decomposition state, closure state, architecture ownership,
implementation behavior and evidence conclusions are unchanged.
