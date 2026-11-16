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
   - verify that its derived `Purpose` is honestly supported by accepted ancestry;
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
13. return to component design only when the relevant requirement paths are sufficiently
    concrete and contain no active unreal Requirement needed by the unit.

A thought that occurs during implementation is **not** automatically a requirement.

If it is not needed to satisfy an accepted primary/derived product obligation, it remains outside the current scope unless explicitly accepted as a new requirement with the required Basis/Purpose.

A requirement must never be invented merely to preserve an existing component or mechanism.

## Requirement artifact maintenance

The current requirement tree is the normative source of requirement state.

When requirement/constraint text or decomposition links change:

- keep the existing stable ID unless the entity itself was incorrectly identified;
- update the node in place rather than creating a shadow copy;
- preserve causal decomposition links as `[decomp: blocker -> pending|deblocker]`;
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
- every requirement has meaningful `Purpose + Statement`;
- every accepted constraint has meaningful `Reason + Statement`;
- no unresolved product-semantic ambiguity is being hidden in implementation;
- no active decomposition block exists on a requirement/constraint whose missing detail is
  necessary for the implementation scope;
- no Requirement required by the implementation scope has an active
  `[unreal: ...]` link;
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
4. resolve every accepted finding before starting the next review unit.

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

- an L1 requirement or material product constraint changes;
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
- architectural consequence.

Failed or unavailable experiments remain visible evidence and are not hidden by simply
rerunning until green.

## Blocking and deferral

A temporary ambiguity in the current development cycle is recorded in the relevant review,
test or experiment artifact. It does not automatically create a project-wide deferral.

Use `design/deferrals/` only for open items expected to survive the current implementation
scope, for example:

- postponed product extensions;
- future experiments not required for the first working production baseline;
- deliberately deferred DeviceManager/availability behavior.

A deferred item must identify its re-entry condition: what future decision, evidence or
milestone makes it active work again.

## Review documentation

External reviews are preserved verbatim under `design/reviews/` and receive a separate
response/disposition document.

Autonomous internal development reviews normally use **one document** containing:

- scope;
- findings;
- disposition of every finding;
- final verdict;
- explicit accumulated requirement-state inventory listing every current `decomp` link
  (mark each as `pending` or `resolved`), every active `unreal` link and every
  `[rejected_closure]` node; write `none` for an empty category rather than omitting it.

Create a separate response document only when the review originated externally, must remain
immutable/verbatim, or the disposition is produced materially later/by a different reviewer.

Every finding is explicitly classified as one of:

- accepted and fixed;
- accepted and deferred behind a named gate/experiment;
- rejected with technical justification.

No finding is silently ignored.

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
checkpoint.

## Session-safety cadence

Long development sessions may be interrupted by the execution environment after roughly
45 minutes. The CD cycle is therefore a **session-safety window**, not a logical unit of
design/development work and not a release/snapshot boundary.

Each autonomous design/development cycle has a **cycle interval**:

- if the user explicitly specifies an interval when starting that cycle, use that value;
- otherwise the default cycle interval is **35 minutes**.

Call the selected value `CYCLE_INTERVAL`. After it is chosen for the cycle, all cadence
logic below refers only to `CYCLE_INTERVAL`.

### Logical work versus CD window

Logical work units, reviews, experiments, implementation slices and snapshots have their own
natural boundaries independent of the CD window.

- A logically complete block may be committed, reviewed and published as a snapshot at any
  point inside a CD cycle.
- Reaching the end of a CD cycle does **not** imply that a snapshot should be created.
- Snapshot publication must not be delayed merely to coincide with the CD boundary.
- Conversely, unfinished logical work may remain on the active cycle branch across a CD
  boundary; the handoff exists precisely so the next cycle can resume it without re-reviewing
  the whole repository.
- If the current logical block completes materially before the nominal CD boundary and there
  is no useful reason to start another block, the cycle may end early.
- Large overruns beyond `CYCLE_INTERVAL` are undesirable because they increase the risk that
  the interface/session fails before a usable handoff is delivered.

### Mainline snapshot requirements

The snapshot policy is normative process behavior. It is expressed explicitly because a
working branch and `main` serve different purposes.

#### CD-SNAPSHOT-R1 — snapshot boundary is a logical block boundary

**Basis:** `main` is the compact chronological record used to resume and inspect completed
logical development blocks without replaying their entire working history.

**Statement:** a snapshot may be published only for a deliberately selected **logical
development block state**. A CD/session-safety boundary is neither necessary nor sufficient
for a snapshot. Completion of a logical block may produce a snapshot at any point inside a
CD window; an unfinished logical block remains only on its working branch across any number
of CD windows.

#### CD-SNAPSHOT-R2 — one logical snapshot is exactly one new mainline commit

**Purpose:** preserve a compact mainline while retaining the full development trail on the
working branch.

**Statement:** publication of one logical snapshot to `main` creates exactly **one** new
commit whose:

- parent is the current accepted `main` snapshot HEAD;
- tree is exactly the committed tree selected from the logical block's working branch;
- commit message identifies the next sequential snapshot number, the logical block, source
  branch and exact source commit;
- ancestry does **not** include the intermediate commits of the working branch.

The working branch retains all intermediate commits. It is not merged, rebased onto
`main` for publication, or otherwise used to import its commit chain into `main`.

A snapshot is therefore equivalent to a squash of the selected committed tree onto the
previous snapshot, not a squash-merge operation whose ancestry may depend on branch history.

#### CD-SNAPSHOT-R3 — source state is explicit and may precede branch HEAD

**Purpose:** a working branch may already contain unfinished work for the next logical block
when the previous block is ready to snapshot.

**Statement:** every snapshot names an exact `SOURCE_SNAPSHOT_COMMIT`. The snapshot tree
must equal that commit's tree. The source commit need not be the current branch HEAD.
Unfinished descendant commits must never leak into the earlier logical snapshot.

#### CD-SNAPSHOT-R4 — numbering is a mainline invariant

**Purpose:** snapshot numbers are chronological mainline checkpoint identifiers.

**Statement:** the new snapshot number is exactly the previous accepted mainline snapshot
number plus one. If published history is explicitly reconstructed, every reconstructed
snapshot after the reconstruction point is renumbered to preserve one gap-free chronological
sequence. A commit message with an obsolete snapshot number is incorrect even when its tree
is correct.

#### CD-SNAPSHOT-R5 — snapshot verification is mechanical

**Purpose:** prevent accidental publication of branch history or the wrong logical tree.

**Statement:** before updating `main`, verify all of:

1. current `main` HEAD is the expected previous snapshot;
2. source branch and exact `SOURCE_SNAPSHOT_COMMIT` are recorded;
3. the candidate snapshot tree hash equals the source commit tree hash;
4. the candidate snapshot parent is exactly the expected previous `main` HEAD;
5. comparison from previous snapshot to candidate snapshot reports exactly one commit
   (`ahead_by = 1`);
6. no unfinished descendant tree is being substituted for the selected source state.

After updating `main`, repeat the parent/tree/one-commit checks against the published ref.

If any check fails, do not continue development on the assumption that the snapshot was
published correctly.

#### CD-SNAPSHOT-R6 — development history stays on the working branch

**Purpose:** preserve evidence and debugging history without turning `main` into a raw
implementation journal.

**Statement:** intermediate requirement, design, experiment, code, test, review and fix
commits remain reachable from their working branch. They are not copied one-by-one to
`main`. Removing or rewriting the working branch is a separate repository-history action
and is not implied by snapshot publication.

#### CD-SNAPSHOT-R7 — CHANGELOG synchronization is stage-gated

**Purpose:** future snapshots should provide a concise user-readable index in addition to Git
history, without forcing churn during the current NG3 convergence phase.

**Statement:** through the active NG3 development stage, snapshot publication does **not**
require an immediate `CHANGELOG.md` edit. At NG3 closure, the missing NG3 snapshot summary
must be reconciled/backfilled. For development stages after NG3, each new mainline snapshot
must include the corresponding concise `CHANGELOG.md` entry in the snapshotted tree unless
an explicit later project decision changes this policy.

The changelog entry summarizes the completed logical result; it never replaces normative
requirements, architecture, evidence or review artifacts.

### Cycle branch and clock

Each CD cycle uses Git commit timestamps as an objective elapsed-time clock and a dedicated
GitHub-visible working branch as the externally durable work trail.

At the start of a cycle:

1. determine and record `CYCLE_INTERVAL`;
2. create or select the dedicated branch for that CD window;
3. all requirement, design, implementation, test, evidence, review and fix commits produced
   during the window are written to that branch;
4. every commit must be present on GitHub immediately after creation;
5. the first commit created in the window becomes `CYCLE_START_COMMIT`;
6. record its committer timestamp `T0`;
7. after later commits read their GitHub committer timestamps `Tn` and track `Tn - T0`.

The branch is the durable record of work. The CD handoff is intentionally **not** a Git
project artifact.

### Handoff trigger and behavior

As elapsed time approaches `CYCLE_INTERVAL`, prioritize leaving enough execution margin to
produce a reliable handoff. Do not intentionally run far past the interval merely to finish a
large logical unit.

When the session-safety boundary is reached or work is otherwise stopped for the current
chat turn:

- stop at the nearest safe technical point; do not manufacture a logical completion;
- leave all already-created commits published on the active branch;
- do not create a special Git checkpoint commit unless the work itself naturally requires a
  commit;
- do not create a snapshot solely because the CD window ended;
- produce a compact **handoff file in the chat interface**, not in Git;
- stop autonomous development until the next user turn.

The handoff file should contain only enough context to resume cheaply:

- `CYCLE_INTERVAL`;
- active branch and current branch head;
- base/main snapshot from which the branch started when relevant;
- what logical work was completed during the window;
- exact unfinished work and current technical state;
- tests/experiments/reviews that are currently green/red or still pending;
- the short plan for the **current logical development unit**, not a new plan invented merely
  for the next CD window;
- decisions genuinely requiring human agreement, if any;
- current accumulated requirement-state inventory: every `decomp` link with
  `pending|resolved`, active `unreal`, and `[rejected_closure]`.

The handoff is operational continuity metadata. It should not be committed to the repository
unless its content independently becomes a real project artifact.

A new CD cycle starts after the next user turn. It may continue the same logical development
unit on a new cycle branch or a clearly reset continuation branch, using the previous handoff
to avoid a full repository review.

This mechanism exists only to survive chat/session limits. It must not distort logical work
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
- all accepted review findings are fixed or explicitly postponed outside the current scope;
- and a final full-project review has no unresolved finding of minor severity or higher.

If that final review produces a finding, fix it and repeat the final review on the changed
baseline. Multiple consecutive clean reviews without intervening code changes are not
required.

## Evidence hierarchy

Safety-relevant kernel/userspace behavior must not be inferred from documentation or unit
tests when a practical stronger experiment is feasible.

Use, in order of increasing environment specificity:

1. rootless deterministic/unit/property tests;
2. disposable privileged namespace / GitHub CI;
3. real target topology.

The environment is chosen by what the hypothesis requires, not by a fixed preference for
the most expensive stand.

## Backend direction

For NG1 production packet filtering and NAT policy, nftables is the production backend.

Legacy iptables-based code may remain temporarily as regression/historical evidence but
must not define new production semantics and must not remain in the production Planner/
runtime ownership path.
