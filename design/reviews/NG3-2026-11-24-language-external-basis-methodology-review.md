# NG3 2026-11-24 — language and external-basis methodology review

**Scope:** review the strengthened human-acceptable-document language rule and the new
requirement external-basis trace rule.

## Verdict

**PASS — methodology change is internally consistent and does not change product semantics.**

## Findings and dispositions

### F1 — language review is now two-stage

**Decision:** accepted.  
**Resolution:** fixed.

The project convention now requires both justification of every retained foreign term and a
second whole-sentence pass that reconstructs the text as natural Russian rather than preserving
translated English syntax.

Literal identifiers, API names, file names, commands and state values remain exempt only as
literal technical references; the exemption does not justify surrounding foreign vocabulary.

### F2 — externally justified requirement properties have a deterministic trace

**Decision:** accepted.  
**Resolution:** fixed.

The requirements model now requires one canonical current-stage registry when a normative
property cannot be verified from the current requirement artifact itself. The registry is
selective: it records only externally justified properties rather than duplicating the whole
requirement tree.

Repository-wide text search is explicitly not a traceability edge.

### F3 — postponed status keeps its existing semantic requirements

**Decision:** accepted.  
**Resolution:** fixed.

The new rule does not replace the existing postponed-status contract. It only requires a
deterministic path from the current requirement artifact to the record that proves the reason,
scope and known re-entry condition.

## Result

No unresolved finding remains in this review unit.
