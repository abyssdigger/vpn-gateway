# Future possibilities initial registry review — 2026-11-25

**Review unit:** project-level non-normative future/negative-result registry and reclassification
of traffic-driven managed-Device presence.

## Scope

Review the initial `design/future-possibilities.md` population for three properties:

1. it must not become a second backlog/requirements/deferral system;
2. every “Смысл” must state the human need in Russian without explaining implementation;
3. historical material must remain source-of-truth for technical detail and must not be
   rewritten to make later decisions appear contemporaneous.

## Findings and dispositions

### F1 — registry role is separated from normative planning

**Decision:** accepted.  
**Resolution:** fixed.

The document explicitly denies backlog, roadmap, Requirement, Constraint, declaration and
deferral semantics. Re-entry conditions are search hints, not commitments or priorities.

### F2 — human-facing “Смысл” rule is suitable for project archaeology

**Decision:** accepted.  
**Resolution:** fixed.

Each initial entry gives a short Russian statement of what was wanted and why. Implementation
mechanisms remain outside “Смысл”; material conditions that created the need are allowed.
The rule also forbids invented retrospective motivation when the original need cannot be
recovered reliably.

### F3 — initial retrospective population is selective and traceable

**Decision:** accepted.  
**Resolution:** fixed.

The initial entries cover only reusable alternatives/negative results with a plausible future
re-entry question: traffic-driven presence, inbound multipath, netkit L3, cross-boundary Profile
metadata, superseded host-side return/behavior lanes and the universal SystemdDriver idea.
Each points to existing research, experiment or review material instead of duplicating its
technical detail.

### F4 — traffic-driven presence is preserved without blocking current Device Manager work

**Decision:** accepted.  
**Resolution:** fixed.

The original research/review are not rewritten. A later classification note records that the
research answered a valid optional-future question, while the clarified current need is
configuration-driven redundancy. D1–D4 therefore remain future re-entry questions rather than
current product blockers.

## Verdict

**PASS.** The registry is suitable as a non-normative project-memory index, the initial entries
are traceable, and the traffic-demand research is preserved without contaminating the active
Device Manager frontier.
