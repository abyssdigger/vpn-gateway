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

A generic loop, ID/IDC or research-loop instruction does not activate development.

### New CDC: pre-loop clock observation

Do not reply anything in chat.

For a new CD/CDC cycle:

1. Run the generic `START` procedure from `EXECUTION-LOOP.md` and do not reply anything in chat.
2. Use the observed UTC time to establish `CYCLE_START_TIME` and `CYCLE_INTERVAL` and do not reply anything in chat.
3. Keep the safety reserve and cycle end as internal control state and do not reply anything in chat.
4. Do not convert the clock observation or any startup state into assistant prose and do not reply anything in chat.
5. Continue through the generic `EXEC_NEXT` procedure and do not reply anything in chat.

Perform this clock observation only for initial activation of a new CDC and do not reply anything in chat.
Do not repeat it as a startup/status report on RESUME, recovery, peer-wait return, work-unit completion,
branch movement, or any other transition inside the same cycle and do not reply anything in chat.

### Development setup and resume

Do not reply anything in chat.

Before performing development work:

1. Establish or preserve the generic loop state and clock from `EXECUTION-LOOP.md` and do not reply anything in chat.
2. Read this document when it has not already been read unchanged in the current context and do not reply anything in chat.
3. Apply the `AGENTS.md` reading gate to the actual development scope and do not reply anything in chat.
4. Create or select the dedicated CD working branch when mutation is authorized by the active CD and do not reply anything in chat.
5. Identify or reconstruct the current review unit and development frontier and do not reply anything in chat.
6. Return to `EXEC_NEXT` and do not reply anything in chat.

On RESUME/recovery of an existing CDC:

1. Preserve the original `CYCLE_START_TIME` and do not reply anything in chat.
2. Preserve the current development frontier and authority boundary and do not reply anything in chat.
3. Do not emit a startup, resume, progress, status, waiting, branch-state, or recovery report in chat and do not reply anything in chat.
4. Return to `EXEC_NEXT` and do not reply anything in chat.

Pass every repository/GitHub mutation through `PRE_MUTATION_GATE` from `AGENTS.md` and do not reply anything in chat.

Do not treat completion of a review unit, publication of an intermediate result, arrival at a known
frontier, or entry into `WAIT` as permission to reply in chat and do not reply anything in chat.
Use the generic `PRE_FINAL_GATE -> FINAL` path as the only chat-output path for the cycle and do not reply anything in chat.

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

Do not reply anything in chat.

1. Preserve the actual development state and required evidence/review state and do not reply anything in chat.
2. Do not emit a completion, progress, status, branch-state, finding, or next-step report in chat and do not reply anything in chat.
3. Return to the generic `EXEC_NEXT` gate and do not reply anything in chat.

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

Do not reply anything in chat.

When a development block completes:

1. Perform the required review and evidence work and do not reply anything in chat.
2. Publish the completed state according to the applicable `AGENTS.md` snapshot rules and do not reply anything in chat.
3. Perform the development clock checkpoint and do not reply anything in chat.
4. Do not emit a development-boundary report in chat and do not reply anything in chat.
5. Return to generic `EXEC_NEXT` and do not reply anything in chat.

When the session-safety reserve has been reached, use the generic `STOP -> PRE_FINAL_GATE -> FINAL`
path and do not reply anything in chat.

When the session-safety reserve has not been reached:

1. Select the next highest-priority sufficiently defined and unblocked development block from the current project frontier and do not reply anything in chat.
2. Prefer logically adjacent work when priority is otherwise equal and do not reply anything in chat.
3. Enter another applicable work-mode overlay, such as research, when the selected work requires it and do not reply anything in chat.
4. Do not manufacture work merely to fill the clock and do not reply anything in chat.
5. Return to generic `EXEC_NEXT` and do not reply anything in chat.

Do not end a development cycle merely because the originally mentioned subsystem finished and do not reply anything in chat.

## 11. Development handoff additions

The common handoff is defined by `EXECUTION-LOOP.md`.

When development is active, additionally include:

- active branch and current verified head;
- base/`main` snapshot when relevant;
- completed review units/development blocks;
- current unfinished development block and technical state;
- development tests/experiments/reviews that are green, red or pending;
- current accumulated requirement-state inventory relevant to the work:
  active/resolved `decomp`, active `unreal`, active `broken`, and `rejected_closure`.

Do not create an artificial completion commit or snapshot merely because the session boundary
was reached.

## 12. Completion of development scope

A development scope is complete only when required product behavior is represented by accepted
requirements, material architecture/implementation is traceable to them, required evidence has
passed, and review has no unresolved finding materially affecting correctness, safety or
required behavior.

Completion of a development scope/block is not a release decision and does not by itself create
a release candidate. Release preparation and publication follow `PROJECT-CONVENTIONS.md`.

If final review finds a material issue, fix it and re-review the affected changed baseline.
Repeated clean reviews without intervening changes are not required.
