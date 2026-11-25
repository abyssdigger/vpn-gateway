# Methodology hardening — project response and rationale — 2026-11-25

**Source proposal:** `design/reviews/METHODOLOGY-2026-11-25-cross-contract-hardening-source.md`.

**Trigger:** independent review of the GPT-6 warm-presence evaluation exposed one inherited
cross-contract conflict, one partial-transition race, stale materialization wording and an
evidence-context gap. The evaluator's subsequent self-analysis proposed general methodology
changes intended to prevent the same classes of errors outside VPN-GATE-specific code.

**Scope of this response:** decide which proposals become portable project methodology and
record why. The resulting normative changes are made in the same commit.

## Decision principles

The methodology should remain useful to comparatively weak developers and human reviewers,
but must not become an all-to-all ritual that is too expensive to execute honestly.

Therefore:

- checks are **impact-driven**, not complete-project re-review;
- no mandatory requirement matrix, transition matrix or new review artifact is introduced;
- no mandatory rollback is inferred from partial-transition analysis;
- portable engineering rules live in the portable requirement/component models;
- CDC contains only enforcement hooks and review cadence;
- `AGENTS.md` is not expanded with a duplicate copy of the engineering methodology.

## Findings / proposal dispositions

### M1 — Joint action of obligations, including inherited decisions

**Decision:** accepted.  
**Resolution:** fixed.

The requirements model now defines an **impact frontier** for material changes and requires a
counterexample attempt across obligations whose preconditions, scope, states or transitions
can be changed by the solution.

The check explicitly includes previously accepted architecture when its consequences first
materialize or become observable in the current development unit.

This addresses the class represented by F1 without requiring a complete re-review of the
project on every change.

### M2 — Semantic composition of component contracts

**Decision:** accepted.  
**Resolution:** fixed.

The component model now reviews not only individual component contracts but their semantic
composition.

The accepted form is strengthened beyond “is the result meaningful enough”: for each
downstream decision, review must identify the property actually required, the upstream fact
used as its basis and the contract that proves that the upstream fact entails that property.

The same section explicitly checks **authority leakage through composition**: a component must
not acquire effective policy/ownership authority indirectly through filtering, object removal
or another side effect when that authority is absent from its own responsibility.

### M3 — Partial state-changing transitions

**Decision:** accepted.  
**Resolution:** fixed.

The component model now requires analysis after each material side effect when later execution
can fail, prior evidence can become stale or external state can validly change.

The project does **not** mandate rollback. Review must instead establish whether the resulting
state is complete, safe-but-incomplete, or unknown/unsafe, and define an acceptable continuation,
compensation, fail-closed state or fresh reconciliation.

This directly addresses the class represented by the D.003 cleanup race.

### M4 — Evidence criteria come from obligations, not implementation behavior

**Decision:** accepted.  
**Resolution:** fixed.

The normative evidence rule is placed in `design/requirements-model.md`:

- expected results derive from accepted obligations;
- a test built from the same unproven assumption as the implementation does not prove the
  assumption;
- evidence proves only what it actually observed;
- failure evidence must establish the required post-failure state, not merely cancellation of
  the last operation or survival of one object.

Operational scenario-selection guidance is enforced by CDC expert review rather than duplicated
as a second evidence model.

### M5 — Materially different execution contexts

**Decision:** accepted.  
**Resolution:** fixed.

The requirements model states that one context does not automatically prove another when
preconditions, dependencies, ordering or result handling materially differ.

CDC's counterexample pass explicitly considers execution context and failure point. This is
the general form of the cold-start-versus-steady-state evidence lesson; no VPN-specific case is
embedded into the portable methodology.

### M6 — Escalate only real residual ambiguity

**Decision:** accepted.  
**Resolution:** fixed.

A new requirements-model rule requires filtering candidate alternatives through already
accepted obligations before asking for a human decision. A technical optimization or a newly
invented restriction is not promoted into a competing product goal merely because it makes a
second implementation path imaginable.

The rule does not weaken the existing requirement to escalate genuinely missing or unclear
`Basis/Purpose/Reason`.

CDC §7 now points to this rule before human escalation.

### M7 — Dependent current-state documentation must remain true

**Decision:** accepted.  
**Resolution:** fixed.

`PROJECT-CONVENTIONS.md` §7 now requires checking the truth of current documentary assertions
whose validity depends on a materialization/implementation/architecture change, including
statements in components not directly edited.

Correct IDs and coverage edges are not sufficient if prose such as “not yet materialized” has
become false.

Historical assertions explicitly tied to prior state remain historical and are not rewritten.

### M8 — Two-direction expert review

**Decision:** accepted.  
**Resolution:** fixed.

CDC expert review now includes two directions inside the same review unit:

1. contract-conformance;
2. adversarial/counterexample analysis.

For stateful multi-step mechanisms, the second direction includes partial execution after
material side effects.

No second reviewer, model, artifact or review unit is required by this rule.

### M9 — Add another rule for the missed initial UTC reading

**Decision:** rejected.

The existing CDC rule is already explicit: fresh UTC is obtained before any other CD
preparation. The observed failure was execution discipline, not a methodology ambiguity.
Duplicating the rule would add text without adding a new invariant.

### M10 — Copy the same engineering rules into AGENTS.md

**Decision:** rejected.

The portable models are intended to govern agents and humans alike. `AGENTS.md` already owns
entry/read/write/publication discipline and delegates requirement/component semantics to the
portable models.

Duplicating these engineering rules there would create two future sources of truth.

### M11 — Mandatory matrices or new review artifacts

**Decision:** rejected.

The accepted rules are impact-driven. A reviewer may create a matrix when it genuinely helps a
complex unit, but the methodology does not require all-to-all requirement matrices,
transition matrices or a new artifact class.

## CDC integration

CDC remains an execution model rather than a second source of requirement/component semantics.

Its implementation gate now requires the applicable portable-model checks before materializing
a non-trivial design. Its expert review enforces a normal conformance pass plus an adversarial
counterexample pass. Its human-decision rule filters false alternatives through already
accepted obligations before escalation.

## Expected effect

The changes are intended to catch these general classes of error:

- an individually accepted solution violating a neighboring obligation when materialized;
- a locally correct component acquiring unintended authority through composition;
- a transition whose final operation is cancelled after earlier destructive effects already
  occurred;
- a test proving object survival rather than the protected capability;
- a steady-state PASS being generalized to a materially different startup/recovery context;
- current documentation becoming false while all IDs and trace edges remain syntactically
  correct;
- a developer asking projectholder to choose between an accepted obligation and an invented
  optimization.

Retrospective coverage of one CDC is not proof that the methodology is sufficient forever.
Future real development remains the validation mechanism for these portable rules.
