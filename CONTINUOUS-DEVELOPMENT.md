# CONTINUOUS DEVELOPMENT (CD) OVERLAY

**Scope:** development semantics for an active continuous execution loop.

This document is a work-mode overlay on `EXECUTION-LOOP.md`. It owns development/review units,
development progression, development-specific evidence/review, branch/publication behavior and
development additions to the common handoff.

It does not own generic loop transitions/finalization, repository authorization, requirement
semantics, component semantics or artifact conventions.

## 1. Starting and resuming development

Explicit projectholder `CD` / `CDC` start/resume/continue wording activates the generic loop
and this development overlay under `AGENTS.md`.

`CD` names continuous development; `CDC` denotes a CD cycle (one continuous-development
execution cycle with the CD overlay active). In activation wording, `CD` and `CDC` are
accepted aliases with **identical process semantics**. The extra letter does not introduce
another development mode, a separate lifecycle or additional authority.

A generic loop, ID/IDC or research-loop instruction does not activate development.

### New CDC initialization

A new CDC is entered only through the generic `START` procedure in `EXECUTION-LOOP.md`.
This overlay must never invoke `START` recursively.

When generic `START` initializes this overlay:

1. Use the generic clock, `CYCLE_INTERVAL`, optional `ITERATION_BUDGET`, and safety boundary already being established by `START`.
2. Read this document when it has not already been read unchanged in the current context.
3. Apply the `AGENTS.md` reading gate to the actual development scope.
4. Create or select the dedicated CD working branch when mutation is authorized by the active CD.
5. Identify or reconstruct the current review unit and development frontier.
6. Return control to the still-running generic `START`; do not invoke `START` or `EXEC_NEXT` from overlay initialization.

On RESUME/recovery of an existing CDC:

1. Preserve the original `CYCLE_START_TIME`, `CYCLE_INTERVAL`, optional `ITERATION_BUDGET`,
   `ITERATIONS_COMPLETED`, development frontier, and authority boundary.
2. Reconstruct only the development state required to continue.
3. Return control to the generic RESUME/RECOVERY procedure; it owns the transition to `EXEC_NEXT`.

Pass every repository/GitHub mutation through `PRE_MUTATION_GATE` from `AGENTS.md`.

Keep routine development-boundary chatter out of chat. The generic `FINAL` summary owns the
normal end-of-cycle report; an occasional materially useful intermediate note does not alter the
loop state.

## 2. Review units and development blocks

Work proceeds in coherent **review units**.

A review unit is the smallest development change that can independently be:

- traced to the accepted need that justifies it;
- designed when design is required;
- implemented when implementation is required;
- evidenced;
- reviewed;
- accepted or rejected as one piece.

A review unit may contain only requirements/design work and no code.

A **development block** is one or more review units that together produce one completed logical
development result. A loop time window is not automatically a review-unit or
development-block boundary.

`main` snapshot rules remain owned exclusively by `AGENTS.md`.

## 3. Normal development flow

The ordinary flow is:

```text
accepted need
    -> relevant requirement validation/refinement
    -> relevant architecture/component design
    -> implementation
    -> evidence
    -> expert review
    -> accepted fixes
```

Only phases relevant to the current unit are performed. A documentation-only or
requirement-only unit need not manufacture implementation/evidence phases that do not apply.

If a later phase exposes an earlier insufficiency, return to the earliest insufficient owner
instead of inventing semantics locally.

After every bounded development operation:

1. Preserve the actual development state and required evidence/review state.
2. Do not emit a completion, progress, status, branch-state, finding, or next-step report in chat.
3. Return to the generic `EXEC_NEXT` gate.

### Requirement work

Requirement semantics, refinement, constraints, statuses and requirement-tree maintenance follow
`design/requirements-model.md` and the relevant current-stage Requirement/Constraint ancestry.

CD adds no parallel requirement model.

### Component/architecture work

Component roles, interactions and decomposition follow `design/component-model.md` and the
relevant current architecture.

CD adds no parallel component model.

### Implementation gate

Implementation may proceed only when relevant requirement and architecture decisions are
sufficient for that implementation scope.

For a non-trivial materialization, also apply the affected-obligation frontier, semantic
composition and partial-transition checks required by `design/requirements-model.md` and
`design/component-model.md`.

If implementation would have to choose new product semantics, ownership, observable behavior or
an unresolved architecture contract, return to the governing normative artifact.

## 4. Development discoveries and research composition

Classify discoveries by their real owner:

| Discovery | Action |
| --- | --- |
| product meaning/scope is insufficient | return to requirements |
| component responsibility/interaction is insufficient | return to architecture/component design |
| external/kernel/protocol/platform fact is unknown | enter/apply the research overlay and obtain the cheapest sufficient evidence |
| implementation violates an accepted contract | fix implementation and evidence |
| attractive new product idea without accepted need | keep it outside the current unit until separately accepted |

Entering a research unit inside active CD does not start a new loop, reset the clock or widen
authority.

A technical experiment may establish facts. It must not decide what the product is supposed to
mean.

## 5. Evidence and experiments

Choose the cheapest environment capable of proving the required property:

1. pure/unit/property test for deterministic logic;
2. disposable privileged environment for kernel/system integration;
3. target/live environment only when the property genuinely depends on it.

Use a persistent experiment dossier when the fact is material, target-specific,
undocumented/ambiguous, negative evidence matters, or the result can change architecture or
safety decisions.

Routine permanent automated tests do not need a separate dossier merely because they are
evidence.

Research/evidence classification follows `RESEARCH.md` when that overlay is active.
Experiment artifact placement and historical-result preservation follow
`PROJECT-CONVENTIONS.md` and the experiment instructions referenced there.

## 6. Expert review

A non-trivial review unit must receive an expert review appropriate to its scope before being
treated as accepted.

Review the actual unit against governing requirements/contracts and evidence. Do not reconstruct
unrelated project areas merely to perform a local review.

Within the same review unit, perform two analytical directions:

1. **contract-conformance pass** — does the actual design/implementation satisfy accepted
   contracts and claimed postconditions;
2. **counterexample pass** — in what permitted state, event ordering, execution context or
   failure point can the implementation violate an accepted obligation even when main local
   operations behave as designed.

For stateful multi-step mechanisms the counterexample pass includes partial execution after
material side effects under `design/component-model.md`.

Evidence claims remain limited to properties actually tested under
`design/requirements-model.md`; steady-state success does not silently prove startup/recovery/
failure behavior.

Every material finding receives an explicit disposition under `PROJECT-CONVENTIONS.md`.

If review materially changes design/implementation, re-run invalidated evidence and review the
changed scope again.

### Documentation impact

For every review unit, determine whether the proposed change materially affects the user/operator documentation required by `VPNG-M001-R6*`, including externally observable behavior, configuration/defaults, interfaces, supported environments, safety/trust boundaries or operator procedures. At the affected review boundary require either the applicable documentation delta (both EN and RU, including affected diagrams and examples), or an explicit reviewable reason why no documentation change is necessary.

A missing pre-existing documentation page is not by itself a no-impact reason. Identify and track pre-existing gaps separately where they are neither introduced nor materially worsened by the proposed change. They do not automatically prevent acceptance of unrelated work. This gate does not establish a historical-backfill release gate, waive existing documentation obligations, or close a permanent Requirement. Documentation layout and artifact conventions remain owned by `PROJECT-CONVENTIONS.md`. When the COLLAB overlay is active, bounded processing of these already-established documentation obligations during productive WAIT or true no-WAIT idle follows the documentation-reconciliation lanes in `COLLABORATIVE-EXECUTION.md` §§6.1–6.2.

## 7. Blocking, deferral and human decisions

An unresolved development problem blocks only the scope depending on it.

A temporary ambiguity is not automatically a project-wide deferral. Persistent accepted
postponements belong in the project's deferral mechanism.

When governing requirements/model require a human product decision, stop the dependent scope
and apply the real-ambiguity check from `design/requirements-model.md`. Continue independent
unblocked work when useful and permitted.

If a projectholder decision remains genuinely required after that filtering, construct the
request under the self-contained decision-request contract in `EXECUTION-LOOP.md` §8.1. A
pointer to a review, Issue, task room or prior discussion is supporting evidence, not the
decision request itself.

If no meaningful unblocked work remains, the generic loop may use a human-decision/external-
blocker stop basis or `WAIT` when an active interaction overlay provides an applicable lane.

## 8. CD branch and publication discipline

All CD commits use the dedicated working branch for the active development cycle/continuation.

Commit publication, remote verification, `main` protection and snapshots are owned by
`AGENTS.md`.

Failure to publish a commit, failure to confirm the expected remote ref, or ambiguous remote
publication state is an immediate development stop condition.

A failed CI/test/review/evidence result after successful publication is not itself a stop
condition. Diagnose read-only first and, when `AGENTS.md` permits a bounded corrective change
inside current accepted scope, fix and revalidate it.

## 9. Development clock checkpoints

The generic clock and safety reserve are owned by `EXECUTION-LOOP.md`.

In addition to its generic checkpoints, obtain fresh real UTC time:

- after **every commit**;
- at every development-block boundary;
- immediately before a development handoff/snapshot decision.

Do not reset `CYCLE_START_TIME` because a development block completes, the branch changes or a
snapshot is published.

## 10. Continuation across development blocks

When a development block completes:

1. Perform the required review and evidence work.
2. Publish the completed state according to the applicable `AGENTS.md` snapshot rules.
3. Perform the development clock checkpoint.
4. Do not emit a development-boundary report in chat.
5. Return to generic `EXEC_NEXT`.

When the session-safety reserve has been reached, use the generic `STOP -> PRE_FINAL_GATE -> FINAL`
path.

When the session-safety reserve has not been reached:

1. Select the next highest-priority sufficiently defined and unblocked development block from the current project frontier.
2. Prefer logically adjacent work when priority is otherwise equal.
3. Enter another applicable work-mode overlay, such as research, when the selected work requires it.
4. Do not manufacture work merely to fill the clock.
5. Return to generic `EXEC_NEXT`.

Do not end a development cycle merely because the originally mentioned subsystem finished.

## 11. Development handoff additions

The common handoff is defined by `EXECUTION-LOOP.md`.

Before a development cycle/session ends or hands off, apply the WIP durability rule from
`AGENTS.md`. If materially useful unfinished work exists only in transient state, publish a WIP
checkpoint to the authorized working branch before final handoff when publication remains safe and
authorized. This checkpoint is not a candidate submission and does not imply completion.

When development is active, additionally include:

- active branch and current verified head;
- whether that head is WIP, Candidate, or Accepted when the distinction matters to continuation;
- base/`main` snapshot when relevant;
- completed review units/development blocks;
- current unfinished development block and technical state;
- development tests/experiments/reviews that are green, red or pending;
- current accumulated requirement-state inventory relevant to the work:
  active/resolved `decomp`, active `unreal`, active `broken`, and `rejected_closure`.

Do not create an artificial completion commit or snapshot merely because the session boundary
was reached. A required WIP durability checkpoint preserves unfinished state; it does not convert
that state into a completed development block or review candidate.

## 12. Completion of development scope

A development scope is complete only when required product behavior is represented by accepted
requirements, material architecture/implementation is traceable to them, required evidence has
passed, and review has no unresolved finding materially affecting correctness, safety or
required behavior.

Completion of a development scope/block is not a release decision and does not by itself create
a release candidate. Release preparation and publication follow `PROJECT-CONVENTIONS.md`.

If final review finds a material issue, fix it and re-review the affected changed baseline.
Repeated clean reviews without intervening changes are not required.
