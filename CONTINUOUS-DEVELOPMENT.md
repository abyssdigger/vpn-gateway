# CONTINUOUS DESIGN AND DEVELOPMENT RULES

**Scope:** autonomous continuous-development (CD) execution after the user explicitly starts
or resumes a CD cycle.

This document owns the CD execution model, review/development-block cadence, session clock and
handoff. It does not own repository write authorization, `main` publication, requirement
semantics, component semantics, documentation conventions or Git-history policy.

Those subjects are owned by `AGENTS.md`, `design/requirements-model.md`,
`design/component-model.md`, current-stage normative artifacts and
`PROJECT-CONVENTIONS.md`.

## 1. Entering CD

A CD cycle starts or resumes only after an explicit user instruction to start/resume/continue
CD execution.

Before any other CD preparation:

1. choose `CYCLE_INTERVAL`: the user-specified interval, otherwise **30 minutes**;
2. obtain fresh real current time and record it as `CYCLE_START_TIME`;
3. read this document if it has not already been read unchanged in the current response;
4. apply the `AGENTS.md` reading gate to the actual CD task and read only the relevant
   normative/project documents;
5. create/select the dedicated CD working branch.

If fresh real time cannot be obtained, do not begin autonomous CD mutation.

The clock starts before mandatory reading or preparation. Commit timestamps are not a
substitute for `CYCLE_START_TIME`.

## 2. Review units and development blocks

Work proceeds in coherent **review units**.

A review unit is the smallest change that can be independently:

- traced to the accepted need that justifies it;
- designed when design is required;
- implemented when implementation is required;
- evidenced;
- reviewed;
- accepted or rejected as one piece.

A review unit may contain only requirements/design work and no code.

A **development block** is one or more review units that together produce one completed
logical result. A CD time window is not automatically a review-unit or development-block
boundary.

`main` snapshot rules for completed development blocks are owned exclusively by
`AGENTS.md`.

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

Only the phases relevant to the current unit are performed. A documentation-only or
requirement-only unit need not manufacture implementation/evidence phases that do not apply.

If a later phase exposes an earlier insufficiency, return to the earliest insufficient owner
instead of inventing semantics locally.

### Requirement work

For requirement semantics, refinement, constraints, requirement status and requirement-tree
maintenance, follow `design/requirements-model.md` and the relevant current-stage
Requirement/Constraint ancestry.

CD adds no parallel requirement model.

### Component/architecture work

For component roles, interaction semantics and decomposition, follow
`design/component-model.md` and the relevant current-stage architecture.

CD adds no parallel component model.

### Implementation gate

Implementation may proceed only when the relevant requirement and architecture decisions are
sufficient for that implementation scope.

If the implementation would have to choose new product semantics, ownership, observable
behavior or an unresolved architecture contract, return to the governing normative artifact.

## 4. Classification of discoveries

Classify discoveries by their real owner:

| Discovery | Action |
| --- | --- |
| product meaning/scope is insufficient | return to requirements |
| component responsibility/interaction is insufficient | return to architecture/component design |
| external/kernel/protocol fact is unknown | run the cheapest sufficient technical experiment/evidence |
| implementation violates an accepted contract | fix implementation and evidence |
| attractive new product idea without accepted need | keep it out of the current unit until separately accepted |

A technical experiment may establish facts. It must not decide what the product is supposed
to mean.

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

Experiment artifact placement, historical-result preservation and result/disposition records
follow `PROJECT-CONVENTIONS.md` and the experiment instructions referenced there.

## 6. Expert review

A non-trivial review unit must receive an expert review appropriate to its scope before it is
treated as accepted.

Review the actual unit against its governing requirements/contracts and evidence. Do not
reconstruct unrelated parts of the project merely to perform a local review.

Every material finding receives an explicit disposition according to
`PROJECT-CONVENTIONS.md`.

If review changes the implementation/design materially, re-run the evidence invalidated by
that change and review the changed scope again.

## 7. Blocking, deferral and human decisions

An unresolved problem blocks only the scope that depends on it.

A temporary ambiguity is not automatically a project-wide deferral. Persistent accepted
postponements belong in the project's deferral mechanism defined by the relevant project
conventions/artifacts.

When the governing requirements/model require a human product decision, stop the dependent
scope and ask. Continue independent unblocked work when useful and allowed by the active CD.

The global process-correction gate and all repository/Git authorization rules are owned by
`AGENTS.md`, not this document.

## 8. CD branch and publication discipline

All CD commits use the dedicated working branch for the cycle/current continuation.

Commit publication, verification, publication-failure behavior, `main` protection and
snapshot rules are defined only by `AGENTS.md`.

A publication failure is therefore an immediate CD stop condition.

## 9. Time checks

After **every commit**, and at development-block/handoff boundaries, obtain fresh real current
time and compare it with `CYCLE_START_TIME`.

Do not reset `CYCLE_START_TIME` because:

- a development block completed;
- the user sent a message;
- the cycle branch changed for a continuation;
- a snapshot was published.

The cycle interval is a session-safety boundary, not a logical-development boundary.

## 10. User intervention pauses CD

Any new user intervention pauses autonomous CD writes immediately.

Handle the new instruction/question first. Resume autonomous CD only after an explicit
resume/continue instruction.

If the intervention explicitly requests one repository change, that instruction authorizes
only that change under `AGENTS.md`; completing it does not resume the rest of CD.

The original CD clock remains unchanged while paused.

## 11. Continuation across development blocks

When a development block completes:

1. perform the required review/evidence for that block;
2. publish its completed state according to the `AGENTS.md` snapshot rules applicable to
   the active CD;
3. obtain fresh current time.

If fewer than **3 minutes** remain before `CYCLE_INTERVAL`, finish the cycle with a handoff.

Otherwise select the next highest-priority sufficiently defined and unblocked development
block from the current project frontier, preferring logically adjacent work when priority is
otherwise equal.

A CD does not end merely because the originally mentioned subsystem finished.

Early stop before the session boundary is appropriate only when:

- a required human decision blocks meaningful continuation;
- an external blocker prevents further meaningful work;
- there is no sufficiently defined unblocked development block;
- publication fails;
- the remaining session margin is insufficient for safe work plus handoff.

Do not manufacture work just to fill the clock.

## 12. Session-safety stop and handoff

As the cycle approaches `CYCLE_INTERVAL`, prefer a safe technical stopping point and a
usable handoff over squeezing in another change.

Do not intentionally run materially beyond the interval to finish a block.

At the stop:

- leave all verified published commits on the working branch;
- do not create an artificial completion commit;
- do not publish a snapshot merely because the time window ended;
- accurately distinguish published/verified work from any unverified work;
- provide the handoff in chat, not as a repository artifact unless it independently belongs
  in the project.

The handoff contains only what is needed to resume cheaply:

- `CYCLE_INTERVAL` and `CYCLE_START_TIME`;
- active branch and current verified head;
- base/`main` snapshot when relevant;
- completed review units/development blocks;
- exact unfinished work and current technical state;
- tests/experiments/reviews that are green, red or pending;
- short plan for the **current unfinished development block**;
- decisions genuinely requiring human agreement;
- current accumulated requirement-state inventory relevant to the work:
  active/resolved `decomp` links, active `unreal`, active `broken`, and
  `rejected_closure` nodes.

After a handoff, autonomous development remains stopped until the user explicitly starts or
resumes CD again.

## 13. Completion of a development scope

A scope is complete only when its required product behavior is represented by accepted
requirements, its material architecture/implementation is traceable to them, required
evidence has passed, and review has no unresolved finding that can materially affect
correctness, safety or required behavior.

If final review finds a material issue, fix it and re-review the affected changed baseline.
Repeated clean reviews without intervening changes are not required.
