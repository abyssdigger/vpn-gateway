# CONTINUOUS DESIGN AND DEVELOPMENT RULES

## Normative design inputs

Continuous work uses two independent normative models together:

- `design/requirements-model.md` defines requirements, constraints, refinement and
  bottom-up constraint lifting;
- `design/component-model.md` defines the permitted component roles and interaction
  semantics.

The requirements model answers where primary product obligations come from, what the product must provide, why derived obligations are needed, and where its promise is constrained.

The component model answers which components may own the required responsibilities and how
they may interact.

Neither model is allowed to manufacture facts for the other:

- an architectural mechanism is not a product requirement merely because it exists or is
  convenient to implement;
- a requirement does not prescribe a component or interaction unless that choice is itself
  externally required;
- an implementation limitation does not silently become product scope.

## Unified review-unit cycle

Work proceeds in coherent **review units** rather than individual helper functions.

A review unit is the smallest coherent product change that can be independently:

- traced to accepted requirements;
- designed;
- implemented when implementation is required;
- evidenced;
- reviewed;
- accepted or rejected as one piece.

A review unit may start as requirement/design work and contain no code at all. Implementation
starts only after the requirement and design gates for the affected behavior are satisfied.

A `development block` is one or more review units that together produce one completed
logical result. Its snapshot publication is governed by `PROJECT-CONVENTIONS.md` §6.1.
Neither a review unit nor a CD window automatically defines a development-block boundary.

The normal cycle is:

```text
accepted product need
        |
        v
requirement validation / refinement
        |
        v
constraint review and lifting
        |
        v
component design
        |
        v
requirement + design gate
        |
        v
implementation
        |
        v
evidence
        |
        v
expert review
        |
        v
accepted fixes
```

Any later phase may discover that an earlier phase was insufficient. In that case the
affected work returns to the earliest insufficient phase instead of inventing semantics
locally.

## Requirement gate

Before designing or implementing behavior, identify the concrete requirement nodes that
justify it.

For every affected requirement:

1. read its full ancestry through the primary project requirement;
2. for every relevant primary project requirement read both mandatory parts:
   - `Basis / Основание`: **откуда** это требование взято;
   - `Statement`: что именно проект обязан обеспечить;
3. for every relevant derived requirement read both mandatory parts:
   - `Purpose`: **зачем** это требуется для вышестоящего обязательства;
   - `Statement`: что именно система обязана обеспечить;
4. read all applicable constraints and their mandatory parts:
   - `Reason`: **почему** ограничение существует;
   - `Statement`: что именно ограничено и как действует это ограничение;
5. verify that every normative action has an explicit or unambiguous actor;
6. verify that the intended change stays within the existing scope and meaning;
7. verify that the requirement is concrete enough to distinguish acceptable from
   unacceptable behavior at the level being designed;
8. identify the cheapest sufficient acceptance evidence, even if the exact test or
   experiment will be implemented later.

A requirement is insufficient for the current design when implementation would have to
invent material semantics not derivable from it.

A requirement/constraint chain is also insufficient when its mandatory semantic first part
cannot be stated clearly:

- primary requirement: `Basis / Основание` / **Откуда это взято?**
- derived requirement: `Purpose` / **Зачем это нужно?**
- constraint: `Reason` / **Почему это ограничение существует?**

A primary `Basis` must be externally verifiable; it is not derived from ancestry.
A derived `Purpose` and a Constraint `Reason` must be natural, unambiguous and causally
supported by accepted ancestry/scope rather than a preferred architecture. If the applicable
answer cannot be established, stop autonomous refinement and escalate the affected chain.

Typical signals are:

- two or more materially different user-visible behaviors would all satisfy the current
  wording;
- a test cannot be written without deciding a new behavior;
- a component needs persistent state whose meaning is not justified by a requirement;
- a new event, state, retry, queue, epoch, cache or lifecycle policy appears only because it
  is technically possible or convenient;
- a supposedly necessary edge case has no confirmed real product scenario;
- the implementation needs a new assumption about supported environment or usage;
- a newly discovered limitation changes the effective product envelope;
- a proposed new primary promise has no verifiable external `Basis`;
- a new derived idea is attractive but has no accepted `Purpose`;
- the proposed derived `Purpose` merely paraphrases its own `Statement` instead of explaining its parent need;
- the proposed `Reason` explains an implementation choice rather than why the constraint
  exists.

If any of these occurs, do **not** resolve it inside implementation merely to keep coding.

Return to requirement work for the affected scope.

## Requirement refinement procedure

When a requirement or constraint is insufficient:

1. state exactly what decision cannot be derived from the current tree;
2. walk the affected ancestry to its primary root, verify that every primary `Basis` remains verifiable and every relevant derived `Purpose/Reason` remains clear;
3. if a primary `Basis` cannot be verified, or any derived `Purpose/Reason` is not naturally and unambiguously supported, stop autonomous refinement and escalate that chain for human discussion;
4. identify the highest existing requirement/constraint whose meaning is affected;
5. determine whether the missing information is:
   - a refinement of an existing requirement;
   - a constraint on an existing requirement;
   - or a genuinely new product promise;
6. add or change only the minimum requirement/constraint nodes necessary;
7. for every new or changed Requirement:
   - if it is a primary root, require a concrete externally verifiable `Basis`;
   - otherwise verify that it refines rather than expands or rewrites the parent;
   - verify that its derived `Purpose` is causally supported by the immediate parent
     `Statement`, not merely by a distant ancestor or a generally desirable outcome;
   - verify explicitly that every domain entity, scenario and promise named in `Purpose`
     is already present in the accepted ancestor Statements of this branch; a `Purpose`
     that first introduces implementation vocabulary, an internal entity, a future
     decomposition concept or a broader scenario is a requirement finding and must be
     lifted or reworded before closure;
   - if the same `Purpose` would still independently justify the child after mentally removing
     the immediate parent, re-check whether the child belongs elsewhere in the tree;
   - verify actor completeness for normative actions;
8. for every new or changed `C` node:
   - record a clear `Reason`;
   - state what is constrained and how;
   - identify who must compensate for the limitation;
   - if work/knowledge is shifted to a user, administrator or external system, add the
     necessary child requirement under that constraint;
   - that child requirement must state what the product must provide so the external
     participant can perform the adaptation correctly and reproducibly;
   - lift the observable effect upward;
   - verify the resulting effective product envelope;
9. define acceptance evidence at the cheapest sufficient level;
10. if further decomposition depends on insufficient semantics in another `R/C` branch:
    - add `[decomp: <blocker-ID> -> pending]` to the blocked node;
    - stop only that decomposition path;
    - continue independent requirement/design work;
11. when the blocker or one of its descendants later provides enough specificity:
    - replace `pending` in the same link with the concrete deblocker ID:
      `[decomp: <blocker-ID> -> <deblocker-ID>]`;
    - keep the blocker part unchanged for causal traceability;
    - resume review of the blocked decomposition;
12. if sufficiently concrete accepted R/C nodes make another Requirement impossible to satisfy:
    - add `[unreal: <R/C-ID>, <R/C-ID>, ...]` beside the unreachable Requirement;
    - use the minimal sufficient set of normative causes;
    - stop architecture/implementation for that Requirement;
    - escalate for human requirement decision; do not search for an architecture workaround
      that violates one of the causal R/C nodes;
    - after an accepted semantic change, remove the active link only when the Requirement is
      demonstrably reachable again;
13. if accepted R/C nodes make another Requirement or Constraint itself no longer a correct
    normative decision, even if it remains technically implementable:
    - add `[broken: <R/C-ID>, <R/C-ID>, ...]` beside the broken R/C;
    - use the minimal sufficient normative causal set;
    - do not implement or preserve the broken rule merely because it was previously accepted;
    - re-open the affected requirement semantics and its descendants/architecture/evidence;
    - remove the active link only after an accepted semantic change repairs, replaces or
      removes the broken node;
14. return to component design only when the relevant requirement paths are sufficiently
    concrete and contain no active `unreal` or `broken` node needed by the unit.

A thought that occurs during implementation is **not** automatically a requirement.

If it is not needed to satisfy an accepted primary/derived product obligation, it remains outside the current scope unless explicitly accepted as a new requirement with the required Basis/Purpose.

A requirement must never be invented merely to preserve an existing component or mechanism.

Conversely, substantial development must also be requirement-driven. Before starting a
non-trivial implementation, experiment or evidence unit, identify the exact accepted R/C whose
implementation, verification or closure requires that work. An experiment may establish a
fact needed by the tree, but must not become an independent source of product semantics.

If no honest R/C trace exists, stop that development unit or perform requirement refinement
first.

## Requirement artifact maintenance

The current requirement tree is the normative source of requirement state.

When requirement/constraint text or decomposition links change:

- keep the existing stable ID unless the entity itself was incorrectly identified;
- update the node in place rather than creating a shadow copy;
- preserve causal decomposition links as `[decomp: blocker -> pending|deblocker]`;
- preserve active normative-causality links as `[unreal: ...]` or `[broken: ...]` until the
  underlying requirement-tree conflict has actually been resolved;
- use one architecture-closure label per requirement/constraint:
  `[pending_closure]`, `[closed]` or `[rejected_closure]`;
- `[pending_closure]` means an architecture candidate exists but acceptance is pending;
- `[closed]` means the closure candidate passed sufficient acceptance;
- `[rejected_closure]` means the closure candidate failed acceptance and the affected
  implementation remains blocked;
- do not copy architecture-decision IDs or architecture link lists into requirements;
- to determine how a closed requirement is realized, search architecture artifacts for the
  exact requirement/constraint ID;
- revalidate affected descendants, constraints, architecture references and evidence;
- remove/revalidate `[closed]` after a semantic change before implementation continues;
- use Git history as the current editorial change record.

The normal closure lifecycle is:

```text
open -> pending_closure -> closed | rejected_closure
rejected_closure -> pending_closure
```

A node with `[decomp: ... -> pending]` cannot be `[pending_closure]` or `[closed]`.

A Requirement with active `[unreal: ...]` cannot be
`[pending_closure]` or `[closed]`. This link records a requirement-tree inconsistency,
not an architecture closure status.

Any R/C with active `[broken: ...]` likewise cannot be `[pending_closure]` or `[closed]`.
The node itself requires semantic repair/replacement/removal before dependent implementation
continues.

After architecture produces a closure candidate, mark `[pending_closure]` only after
verifying an exact architecture reference. Replace it with `[closed]` only after sufficient
acceptance/review evidence. Replace it with `[rejected_closure]` when acceptance shows the
candidate is insufficient or unacceptable.

The closure check is deliberately asymmetric:

```text
pending_closure R/C without architecture reference -> ERROR
closed R/C without architecture reference          -> ERROR
architecture reference to unlabeled R/C             -> ALLOWED
```

An architecture reference alone never changes closure state.

Do not introduce a separate semantic requirement-change journal until a concrete project
need requires querying semantic transitions independently from Git history. Such a journal
is a future requirements-management feature, not a prerequisite for current design work.

## Human acceptance of requirement decisions

Unambiguous refinements that are strictly implied by an accepted parent requirement may be
resolved autonomously.

Human agreement is required before proceeding when requirement work would:

- create a primary Requirement without a concrete externally verifiable `Basis`;
- create or modify a derived `R/C` whose `Purpose/Reason` is not naturally and unambiguously supported by the accepted ancestry/scope;
- expose disagreement about why a requirement exists or why a constraint is legitimate;
- add or materially change a primary project promise;
- introduce a new user-visible capability;
- choose between multiple materially different user-visible semantics;
- materially narrow the useful product envelope by accepting a constraint;
- change user-visible configuration/schema or promised behavior;
- remove previously agreed product functionality;
- make a scope or priority trade-off rather than a technical derivation.

The implementation of the affected behavior remains gated until that decision is accepted.

## Component-design gate

Once the requirements are sufficient, design the smallest component structure that realizes
them using `design/component-model.md`.

The architecture produced by this phase is a **traceable implementation report for accepted
requirements**, not an independent source of product semantics.

The gate question is:

> **Докажи, что ты вообще знаешь, что и зачем собираешься реализовывать.**

For VPN-GATE architecture artifacts, requirement linkage is mandatory and explicit.

The design report for a non-trivial review unit must identify:

- **Requirements** — exact requirement/constraint IDs implemented by the unit, using
  explicit `Implements:` and `Constrained by:` references;
- **Scenario** — the real product situation in which those requirements matter;
- **Components** — which permitted component primitives are used;
- **Responsibilities** — what each component owns;
- **Interactions** — how components communicate with each other;
- **External environment** — which kernel, network, process, timer, configuration or operator
  facts cross the system boundary;
- **Traceability** — which requirement makes each material responsibility and interaction
  necessary;
- **Necessity** — why the responsibility needs to exist at all and why it belongs in a
  separate component or interaction rather than a simpler local mechanism;
- **Constraints** — limitations introduced or discovered by the proposed design;
- **Constraint lifting** — their effect on parent requirements and the product envelope;
- **Simplification review** — states, components, interactions or generality deliberately
  omitted because no accepted real scenario requires them;
- **Evidence plan** — how each relevant requirement will be proven.

The report may be concise for a small unit. The content is mandatory; document size is not.

Every normative architecture document must support direct navigation from its material
decisions to the exact requirement/constraint nodes that justify them.

At minimum:

```text
Implements:
- VPNG-R...

Constrained by:
- VPNG-R....C...
```

must appear at document or section scope wherever the mapping is unambiguous.

For component-level architecture, each material component must identify the most specific
requirements it implements. Material responsibilities, interactions, lifecycle rules and
safety invariants must be traceable within the document either by their own references or
by an enclosing block whose scope is exact.

A distant ancestor requirement is not a sufficient reference when a more specific accepted
descendant defines the behavior.

A component, responsibility or interaction that cannot be honestly traced to a concrete
requirement is a design finding, not a reason to create a requirement afterward.

Conversely, when a requirement changes, every architecture artifact that references that
node or one of its descendants must be revalidated before implementation proceeds.

## Mandatory simplification review

Before implementation, review the proposed design specifically for unnecessary generality.

For each material component, state, interaction and failure-recovery mechanism ask:

1. Which exact accepted requirement needs it?
2. Which real supported scenario exercises it?
3. What observable product behavior breaks if it is removed?
4. Can the same requirement be satisfied with less persistent state?
5. Can an asynchronous interaction be synchronous or direct?
6. Can historical data be replaced by current or bounded aggregate state?
7. Is guaranteed delivery/replay actually required?
8. Is a separate lifecycle owner actually required?
9. Are we solving an arbitrary framework problem rather than the actual product problem?
10. Do all accumulated constraints still leave the parent requirement practically useful?

If removing a mechanism changes only theoretical generality and no accepted requirement,
removal is preferred.

## Requirement/design gate verdict

Implementation may begin only when all of the following hold for the affected scope:

- relevant requirements and constraints are identified by ID;
- every primary requirement has meaningful `Basis + Statement`, and every derived
  requirement has meaningful `Purpose + Statement`;
- every accepted constraint has meaningful `Reason + Statement`;
- no unresolved product-semantic ambiguity is being hidden in implementation;
- no active decomposition block exists on a requirement/constraint whose missing detail is
  necessary for the implementation scope;
- no Requirement required by the implementation scope has an active
  `[unreal: ...]` link;
- no R/C required by the implementation scope has an active `[broken: ...]` link;
- all material component responsibilities and interactions are traceable to requirements;
- every requirement/constraint whose architecture is required by the implementation unit is
  marked `[closed]`; `[pending_closure]` and `[rejected_closure]` block implementation
  of the dependent behavior;
- every `[pending_closure]` and `[closed]` node has an exact reference in the architecture;
- every `[rejected_closure]` node has explicit rejection evidence/review;
- the mechanical closure check reports every `[pending_closure]` or `[closed]` node
  without an architecture reference as an error, while allowing architecture references to
  unlabeled nodes;
- discovered constraints have been lifted far enough to expose their product effect;
- any user/administrator/external-system adaptation caused by an accepted constraint is
  explicit as a requirement/contract rather than an undocumented workaround;
- the effective product envelope remains useful for the intended real scenarios;
- the simplification review found no unnecessary mechanism that should be removed first;
- required human decisions, if any, are accepted;
- an evidence plan exists.

Failure of this gate returns the unit to requirements or component design. It does not
authorize speculative implementation.

## Implementation cycle

After the requirement/design gate passes:

1. implement the smallest coherent change;
2. add or update the cheapest sufficient tests/evidence;
3. perform an autonomous expert review of the changed subsystem and its interaction with:
   - the accepted requirement tree;
   - applicable constraints and product envelope;
   - the component model;
   - whole-project invariants;
4. give every accepted finding a canonical `Resolution` (`fixed` or `deferred`) before
   starting the next review unit, and do not proceed when a deferred finding's named gate
   blocks that next unit.

During implementation, compare the emerging code against the approved design continuously.

If implementation reveals that the requirements or design are insufficient, stop only the
affected behavior and return to the corresponding earlier phase. Do not keep extending code
while the governing requirement is unresolved.

## Classification of discoveries during implementation

When new information appears, classify it before acting:

### Requirement insufficiency

The product meaning is missing or ambiguous.

Action:

```text
implementation
    -> requirement refinement / acceptance
    -> component redesign if needed
    -> implementation
```

Do not settle product semantics through coding convenience.

### Design insufficiency

Requirements are clear, but the current component decomposition cannot realize them cleanly.

Action:

```text
implementation
    -> component design review
    -> requirement/constraint recheck
    -> implementation
```

Do not change product requirements merely to preserve a poor decomposition.

### Technical uncertainty

Requirements and component responsibilities are clear, but an external or implementation
fact is uncertain.

Action: use the experiment procedure below.

### Implementation defect

Requirements and design are sufficient; code simply violates them.

Action: fix and evidence normally.

### New product idea

The idea is useful but not required by the accepted tree.

Action: keep it out of the current implementation. Promote it only through explicit
requirement acceptance.

This classification is mandatory because otherwise implementation tends to convert every
local difficulty or interesting idea into accidental product semantics.

## Expert-review role

The expert-review role has:

- strong subject-domain expertise appropriate to the system under review;
- strong Linux/network-stack knowledge for VPN-GATE reviews;
- practical Python-to-Rust migration experience where relevant, with the goal of keeping
  Python architecture and data flow Rust-aligned;
- aggressive attention to small defects and edge cases;
- enough whole-project scope to identify redundant, mutually inconsistent or suboptimal
  architecture/functionality;
- an obligation to verify that every material architecture decision and implemented
  behavior remains explicitly traceable to the most specific applicable accepted requirement
  rather than merely existing in docs or code;
- an obligation to challenge components, states and interactions whose necessity cannot be
  demonstrated from real supported scenarios;
- an obligation to evaluate whether the implementation follows the project's component
  model cleanly rather than merely reproducing its behavior;
- an obligation to verify subject-domain isolation: concepts, policy and implementation
  details of a lower domain must not leak across an Adapter boundary unless they are part
  of the explicit contract;
- an obligation to perform bottom-up constraint review when implementation reveals a new
  limitation;
- an obligation to produce precise, actionable recommendations.

A full whole-project review is required when:

- a primary requirement or material product constraint changes;
- an architectural or ownership boundary changes;
- a substantial integration milestone is reached;
- release/deployment acceptance is approached;
- or development of the current scope is otherwise complete.

## Ambiguity and experiment procedure

Experiments resolve **technical facts**, not missing product semantics.

Before starting an experiment, first verify that:

- the governing requirement is sufficiently defined;
- the component responsibility that depends on the fact is understood;
- the ambiguity is about the real environment, protocol, kernel, implementation mechanism
  or other externally discoverable fact.

If the answer would choose what the product is supposed to mean, return to requirement
refinement instead of using an experiment to manufacture semantics.

When implementation or design encounters a material technical ambiguity whose answer affects
correctness:

1. State the hypothesis and the behavior that depends on it.
2. Select the **cheapest environment that is sufficient to prove that property**:
   - rootless deterministic/unit/property test for pure logic;
   - disposable privileged namespace / GitHub CI for kernel integration;
   - target/live stand when the property genuinely depends on the real VPN, kernel,
     service or deployment topology;
   - external stand only when the preceding environments cannot provide the required
     capability.
3. Run the verification when possible.
4. If it cannot yet be run:
   - prepare only the artifacts necessary for the future experiment;
   - place an explicit gate/stub around behavior that depends on the unresolved result;
   - continue all implementation, testing and review that is not blocked.

An unresolved ambiguity blocks only the behavior that depends on it.

## What deserves an experiment dossier

Create a persistent directory under `design/experiments/` when the verification concerns:

- undocumented or ambiguous kernel/userspace behavior;
- target-specific behavior;
- negative evidence that may affect future design;
- behavior whose result changes architecture or safety policy;
- or a one-off/live procedure that cannot be represented adequately by a permanent
  automated test.

Routine parser/unit/regression checks that become permanent automated tests do **not**
require a separate experiment dossier.

Every preserved experiment records at least:

- hypothesis;
- required environment;
- procedure/artifacts;
- result or blocked status;
- affected architecture/question or other technical implication established by the result.
  This field must not decide whether the project adopts the mechanism; adoption belongs to
  the separate `Disposition`.

Experiment **Result** and post-result **Disposition** are separate facts:

- `Result` records only the technical outcome established by the experiment itself
  (for example `PASS`, `FAIL`, `INCONCLUSIVE`, or a blocked/unrun state);
- `Disposition` records what the project decided to do with that completed evidence and
  belongs in the central experiment registry
  (`design/vpn-gateway-experiments.md` for the active project lineage), not in the
  experiment result;
- completing an experiment initially leaves its disposition `pending_decision` until the
  result has been discussed;
- a technically successful experiment may therefore be `PASS` while its disposition is
  `not_selected`; this means the mechanism is feasible but the applicable accepted project
  decision did not adopt it;
- changing a disposition must not rewrite or reinterpret the experiment Result.

Use a small canonical disposition vocabulary unless a review explicitly extends it:
`pending_decision`, `selected`, `not_selected`, `deferred`, `superseded`,
`historical_only`.

### Post-result supersession and coverage trace

When a completed experiment is accepted as replacing earlier evidence or the architecture
that consumed it, record that relationship **post-result**, after the new result has been
discussed and accepted. Do not predeclare supersession in a prepared experiment.

The accepted new experiment/result or its consuming review must record, where applicable:

- `Supersedes`: the earlier experiment(s) whose acceptance role is replaced, with the
  replaced claim/scope stated explicitly;
- `Partially supersedes`: the exact old claim that is replaced when other facts from the
  old experiment remain reusable;
- `Retains`: old claims that remain valid/current when partial supersession could otherwise
  be misread as replacing the whole experiment;
- a concise **coverage transition**: which requirement/architecture need the earlier
  evidence covered, what the new evidence covers now, and why the coverage changed.

The central experiment registry must be updated in the opposite direction as well:
the older entry names the replacing experiment/result in its Note when that relationship is
known. Use disposition `superseded` only when the newer evidence replaces the old experiment
as a whole for the same project decision. For partial replacement, keep the disposition that
matches the remaining evidence value and describe the replaced/retained scopes in the Note.

Do **not** reconstruct speculative supersession chains retrospectively. Apply this rule to
historical experiments only when the repository's experiment/result/review/architecture
artifacts make the predecessor, successor and reason explicit. If that causal chain cannot be
stated confidently, preserve the historical entry without inventing one.

Failed or unavailable experiments remain visible evidence and are not hidden by simply
rerunning until green.

## Blocking and deferral

A temporary ambiguity in the current development cycle is recorded in the relevant review,
test or experiment artifact. It does not automatically create a project-wide deferral.

Use `design/deferrals/` only for **accepted, explicitly postponed** obligations or
investigations expected to survive the current implementation scope, for example:

- postponed product extensions;
- future experiments accepted for a later named milestone;
- accepted implementation/evidence work explicitly moved outside the current scope.

A deferred item must identify its original normative source or accepted decision, its
scope and its re-entry condition: what future decision, evidence or milestone makes it
active work again. An unresolved technical ambiguity without an accepted disposition
is a blocked/pending finding, not a deferral.

Stage declarations are different: they record tentative, non-normative intent and
cannot by themselves introduce approved scope, implementation work or acceptance gates.
Promote them through the relevant Requirements/Constraints, architecture and human
acceptance process before they become executable obligations.

## Review documentation

Review storage, immutable originals, response-file exceptions and canonical
`Decision`/`Resolution` classification are governed by
`PROJECT-CONVENTIONS.md` §2. An autonomous internal review normally uses one document
containing scope, findings, the disposition of every finding, final verdict and the
accumulated requirement-state inventory listing every current `decomp` link
(`pending` or `resolved`), active `unreal`, active `broken`, and
`[rejected_closure]`; write `none` when a category is empty.

## Human escalation

The AI resolves ordinary requirement refinements, design, implementation and review findings
autonomously when their meaning is unambiguously derived from already accepted product
requirements.

Human agreement is required when the decision materially changes one of:

- user-visible configuration/schema or promised product semantics;
- trust/security boundary;
- previously agreed functionality or product scope;
- architecture where multiple materially different alternatives remain valid;
- destructive or irreversible migration/deployment behavior;
- project priorities or postponement of an otherwise required product function.

Ordinary bug fixes, test-harness corrections, internal data-structure choices,
Rust-alignment refactors and unambiguous fail-closed hardening do not require a human
decision.

## Process-correction gate

A defect in the project's own operating process is not repaired by immediately editing the
process documents or Git history.

If the defect concerns methodology/process, Git/snapshot/branch policy, CD cadence, or another
rule governing project work:

1. stop the work that depends on the faulty rule;
2. use read-only inspection to establish the actual current state and consequences;
3. discuss with the user:
   - the defective rule/process;
   - why it caused or can cause incorrect project behavior;
   - the proposed replacement/correction;
   - every process/project artifact that would be changed;
   - any already-created consequences that need repair;
4. obtain explicit agreement before any corrective write.

After agreement, the approved correction and approved consequence repair are ordinary
execution of that decision.

This gate does not apply to ordinary implementation bugs, test-harness corrections,
internal refactors, or unambiguous fail-closed hardening unless they themselves change a
project-process rule.

## Session-safety cadence

Long development sessions may be interrupted by the execution environment after roughly
45 minutes. The CD cycle is therefore a **session-safety window**, not a logical unit of
design/development work and not a release/snapshot boundary.

Each autonomous design/development cycle has a **cycle interval**:

- if the user explicitly specifies an interval when starting that cycle, use that value;
- otherwise the default cycle interval is **35 minutes**.

Call the selected value `CYCLE_INTERVAL`. After it is chosen for the cycle, all cadence
logic below refers only to `CYCLE_INTERVAL`.

### Development blocks versus CD window

Review units, development blocks, experiments and snapshots retain their natural
boundaries independently of the CD window. Snapshot publication and the definition
of a completed development block belong to `PROJECT-CONVENTIONS.md` §6.1.

### User intervention pauses autonomous CD execution

An active CD window is not blanket authorization to keep mutating the repository after the
user sends a new message. Any user intervention during the cycle suspends autonomous CD
writes before further mutation.

The agent must first handle the user's new instruction/question. Autonomous CD execution
resumes only after the user explicitly asks to continue/resume the CD (or equivalent).

If the intervention itself contains an explicit instruction for one specific repository
change, that instruction authorizes only that change. Completing it does not implicitly
resume the rest of the CD; the cycle remains paused until an explicit resume instruction.

This pause does not end or reset the CD clock, current development block, branch,
snapshot policy or `CYCLE_INTERVAL`. It is only a write-authorization boundary.

### Continuation across development blocks

A completed development block receives its required snapshot before another
development block begins, subject to `PROJECT-CONVENTIONS.md` §6.1 and any explicit
user-approved snapshot-publication exception. A CD window does not create or suppress
snapshots. Unfinished work may continue across CD windows via handoff.

- Completing the current development block, subsystem or topic that originally triggered the CD
  does **not** by itself complete the CD window. Unless the user explicitly constrained the
  cycle to that one topic, the cycle scope is the current project development frontier.
- If that completed block is snapshotted and less than three minutes remain before the nominal
  CD boundary, the CD cycle is complete.
- Otherwise:
  1. select the next highest-priority sufficiently defined and unblocked development
     block from the current project frontier; prefer a logically adjacent block when priority
     is otherwise equal;
  2. continue work until the earlier of:
     - the CD interval boundary;
     - completion of that next development block in a separate GitHub commit;
  3. if that development block completes, publish its required snapshot and apply this rule again
     from the beginning.
- A decision boundary ends the CD early only when continuing meaningful work actually requires
  human agreement. Finishing one subsystem, reaching a design boundary that can be resolved
  autonomously, or discovering that the original topic is complete is **not** an early-exit
  condition while another sufficiently defined, unblocked project block remains.
- Early exit before the time/safety boundary is therefore limited to:
  - a required human product/process/architecture decision;
  - an external blocker that prevents further meaningful autonomous work;
  - absence of any sufficiently defined unblocked development block;
  - publication failure, handled as a mandatory stop under `PROJECT-CONVENTIONS.md` §7;
  - the existing less-than-three-minutes safety-margin rule above.
- These rules do not relax the `CYCLE_INTERVAL` boundary. As elapsed time approaches the
  interval, session safety and a usable handoff take precedence over starting or finishing more
  work.
- Large overruns beyond `CYCLE_INTERVAL` are undesirable because they increase the risk that
  the interface/session fails before a usable handoff is delivered.

### Cycle branch and clock

Each CD cycle uses real wall-clock time as its elapsed-time source and a dedicated
GitHub-visible working branch as the externally durable work trail. Commit timestamps
record publication events; they do not define when the CD window starts.

At the start of a cycle:

1. determine and record `CYCLE_INTERVAL`;
2. immediately read real current time and preserve it as `CYCLE_START_TIME`, before
   mandatory reading, preparation or the first commit;
3. create or select the dedicated branch for that CD window;
4. all requirement, design, implementation, test, evidence, review, process/documentation
   and fix commits produced during the window are written to that branch;
5. every commit must be present on GitHub immediately after creation.

A failure to publish or verify publication of a commit is a mandatory early-stop
condition for the current CD. Follow the short preservation-and-handoff procedure
in `PROJECT-CONVENTIONS.md` §7; do not continue development or perform prolonged
recovery attempts in this CD.

If fresh real current time cannot be obtained at cycle start or at a required cadence
check, do not substitute commit timestamps as the elapsed-time source. Stop before
further repository mutation and report that the CD safety clock cannot currently be
enforced.

At each existing cadence check, obtain fresh real current time and compare it to
`CYCLE_START_TIME`. Check after every commit (including the first), at the existing
development-block and handoff boundaries, and whenever the existing cadence rules require it.
Keep the existing thresholds, safety margin and handoff behavior unchanged; the first
commit is a check event, not the origin of elapsed time. A user intervention does not
reset `CYCLE_START_TIME`.

The published branch is the durable record of successfully published work. The CD handoff
is intentionally **not** a Git project artifact.

### Handoff trigger and behavior

As elapsed time approaches `CYCLE_INTERVAL`, prioritize leaving enough execution margin to
produce a reliable handoff. Do not intentionally run far past the interval merely to finish a
development block.

When the session-safety boundary is reached or work is otherwise stopped for the current
chat turn:

- stop at the nearest safe technical point; do not manufacture a logical completion;
- leave all successfully published commits on the active branch; when a publication
  failed, explicitly identify unpublished work rather than assuming durability;
- do not create a special commit unless the work itself naturally requires one;
- do not create a snapshot solely because the CD window ended;
- produce a compact **handoff in the chat interface**, not in Git; use a file when practical,
  but use direct chat text instead if file creation fails or would materially increase cutoff risk;
- stop autonomous development until the user explicitly starts or resumes CD execution.

The handoff should contain only enough context to resume cheaply:

- `CYCLE_INTERVAL` and `CYCLE_START_TIME`;
- active branch and current branch head;
- base/main snapshot from which the branch started when relevant;
- which review units or development blocks completed during the window;
- exact unfinished work and current technical state;
- tests/experiments/reviews that are currently green/red or still pending;
- the short plan for the **current development block**, not a new plan invented merely
  for the next CD window;
- decisions genuinely requiring human agreement, if any;
- current accumulated requirement-state inventory: every `decomp` link with
  `pending|resolved`, active `unreal`, active `broken`, and `[rejected_closure]`.

The handoff is operational continuity metadata. It should not be committed to the repository
unless its content independently becomes a real project artifact.

A new CD cycle starts only after the user explicitly starts or resumes CD execution.
An arbitrary next user turn does not restore repository-write authorization. After explicit
start/resume, the new cycle may continue the same development block on a new cycle branch or
a clearly reset continuation branch, using the previous handoff to avoid a full repository
review.

This mechanism exists only to survive chat/session limits. It must not distort development-block
boundaries, snapshot timing, review structure or repository history.

## Completion criteria

Design and development of the current product scope are complete when:

- every required product function is represented by accepted requirements;
- every implemented material behavior is traceable to those requirements;
- no unblocked required product function remains;
- no unresolved candidate constraint materially changes the effective product envelope;
- all accepted constraints have passed bottom-up lifting and product-envelope review;
- all material component responsibilities and interactions are traceable to requirements;
- all required evidence gates for that scope have passed;
- every accepted review finding is either `fixed` or formally `deferred` with the
  required named gate/re-entry condition;
- no `unresolved` review finding remains if it can materially affect correctness, safety,
  required product behavior, acceptance evidence or completion of the current scope.

If that final review produces a finding, fix it and repeat the final review on the changed
baseline. Multiple consecutive clean reviews without intervening code changes are not
required.

## Evidence sufficiency

Choose the cheapest environment that can establish the required technical fact,
using the environment-selection procedure in
[Ambiguity and experiment procedure](#ambiguity-and-experiment-procedure).
Do not infer safety-relevant kernel/userspace behavior from documentation or
unit tests when a practical stronger experiment is needed to establish that
behavior. Experiment-stand execution rules are in
`design/experiments/README.md`.

## Backend ownership

Backend selection follows the current normative stage's requirements, architecture
and verified evidence; historical implementation or experiment evidence does not
establish current product semantics by itself. This process document must not
hardcode any particular stage, packet-filtering backend or technology choice.
