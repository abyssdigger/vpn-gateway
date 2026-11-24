# NG3 2026-11-23 — post-publication ref hygiene review

**Scope:** require explicit cleanup reminders after successful snapshot/merge/publication without
weakening the repository's branch/tag authorization gates.

**Process owner:** `AGENTS.md`  
**Reviewed head:** `78e5cb66bddd51b73c06dbad387db792ddc14b56`

## Verdict

**PASS — the rule prevents silent accumulation of completed temporary branches while preserving
explicit projectholder control over branch/tag mutations.**

## Findings and dispositions

### F1 — completed working branches previously had no mandatory cleanup step

**Decision:** accepted.  
**Resolution:** fixed.

Dedicated working branches are now explicitly temporary work surfaces rather than archival
records. After a completed result is durably represented in its intended target lineage, the
agent must remind the projectholder to clean up redundant refs.

### F2 — source identity must survive branch cleanup

**Decision:** accepted.  
**Resolution:** fixed.

The mandatory reminder includes a proposed annotated source tag on the actual published
working-branch source tip when an equivalent source tag does not already exist. The proposal
must state the exact commit SHA and follow the established NG3 source-tag naming convention.

This keeps source identity independent of the temporary branch.

### F3 — cleanup hygiene must not reintroduce implicit mutation authority

**Decision:** accepted.  
**Resolution:** fixed.

The new rule explicitly distinguishes the mandatory reminder from the mutation itself.
Creating/moving/replacing/deleting branches or tags still requires the explicit authorization
defined by the existing repository-write rules.

The agent therefore cannot delete a working branch or create a source tag merely because a
snapshot succeeded.

## Disposition

The new post-publication hygiene rule is accepted as the project-wide Git-ref cleanup policy.
