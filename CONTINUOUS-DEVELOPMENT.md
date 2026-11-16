# CONTINUOUS-DEVELOPMENT RULES

## Core development cycle

Development proceeds in coherent **review units** rather than individual helper functions.

A review unit is the smallest coherent product change that can be independently specified,
tested, reviewed and either accepted or rejected as one piece.

For every review unit:

1. implement the smallest coherent change;
2. add or update the cheapest sufficient tests/evidence;
3. perform an autonomous expert review of the changed subsystem and its interaction with
   whole-project invariants;
4. resolve every accepted finding before starting the next review unit.

The expert-review role has:

- strong Linux/network-stack knowledge;
- practical Python-to-Rust migration experience, with the goal of keeping Python
  architecture and data flow Rust-aligned;
- aggressive attention to small defects and edge cases;
- enough whole-project scope to identify redundant, mutually inconsistent or suboptimal
  architecture/functionality;
- an obligation to produce precise, actionable recommendations.

A full whole-project review is required when:

- an architectural or ownership boundary changes;
- a substantial integration milestone is reached;
- release/deployment acceptance is approached;
- or development of the current scope is otherwise complete.

## Ambiguity and experiment procedure

When implementation encounters a material ambiguity whose answer affects correctness:

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
- final verdict.

Create a separate response document only when the review originated externally, must remain
immutable/verbatim, or the disposition is produced materially later/by a different reviewer.

Every finding is explicitly classified as one of:

- accepted and fixed;
- accepted and deferred behind a named gate/experiment;
- rejected with technical justification.

No finding is silently ignored.

## Human escalation

The AI resolves ordinary implementation/review findings autonomously.

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
45 minutes. Do not rely on subjective wall-clock tracking.

Each autonomous development cycle has a **cycle interval**:

- if the user explicitly specifies an interval when starting that cycle, use that value;
- otherwise the default cycle interval is **30 minutes**.

Call the selected value `CYCLE_INTERVAL`. After it is chosen for the cycle, all cadence
logic below refers only to `CYCLE_INTERVAL`; do not substitute the default value back into
later decisions.

Each autonomous development cycle uses **Git commit timestamps as the checkpoint clock**
and a dedicated GitHub-visible **code-cycle branch** as the external activity record.

At the start of a cycle:

1. determine and record `CYCLE_INTERVAL`;
2. create or select a dedicated branch for that autonomous cycle, named clearly enough to
   identify the current code cycle;
3. all implementation, test, review and fix commits for the cycle are written to that
   branch;
4. **every commit must be present on GitHub immediately after it is created**; do not keep
   a local-only sequence of commits for later batch push;
5. the first commit created in the cycle becomes `CYCLE_START_COMMIT`;
6. record its **committer timestamp** `T0`;
7. after every subsequent commit in that cycle, read that commit's **committer timestamp**
   `Tn` from GitHub;
8. compute `Tn - T0`;
9. if the elapsed time is greater than or equal to `CYCLE_INTERVAL`, set
   `CHECKPOINT_PENDING=true`.

The code-cycle branch is the authoritative externally observable activity trail. Chat/UI
availability is not used to infer whether autonomous work is still running.

When `CHECKPOINT_PENDING=true`:

- do not start another review unit;
- finish the **current review unit completely**:
  implementation, required tests/evidence, expert review and accepted fixes;
- create/push the final checkpoint commit for that unit;
- post a brief human-facing checkpoint/discussion;
- stop autonomous development until the next user turn.

The selected `CYCLE_INTERVAL` is a checkpoint trigger, not a hard execution limit. The
remaining execution margin is used to finish the current iteration cleanly.

The checkpoint message must include:

- `CYCLE_INTERVAL`;
- `CYCLE_START_COMMIT` and its timestamp;
- final checkpoint commit and timestamp;
- elapsed cycle time;
- what was completed;
- tests/experiments/reviews that passed or failed;
- the exact unfinished or blocked item, if any;
- decisions that genuinely require human agreement;
- the next intended review unit.

A new autonomous cycle starts only after the next user turn, with a new code-cycle branch
(or a clearly reset cycle branch when explicitly chosen), a newly selected
`CYCLE_INTERVAL`, and a new `CYCLE_START_COMMIT`.

This is a session-preservation mechanism, not a reason to create extra review documents or
to interrupt a review unit halfway through.

## Completion criteria

Development of the current product scope is complete when:

- no unblocked required product function remains;
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
