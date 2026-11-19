# AGENTS.md — VPN-GATE agent operating instructions

**Scope:** All repository work, including requirements, architecture, implementation, tests, experiments, reviews, release documentation, and Git operations.

This file is an entry point, not a substitute for the normative project documents. An agent must read the current files in its actual working branch. Do not rely on summaries, prior chats, remembered conventions, or the repository's default branch as a proxy for the current development stage.

## Mandatory reading order — before starting work

Read these documents **in this exact order**:

1. [CONTINUOUS-DEVELOPMENT.md](CONTINUOUS-DEVELOPMENT.md) — continuous-development rules, review units, gates, evidence, expert review, cycle timing, and checkpoints.
2. [PROJECT-CONVENTIONS.md](PROJECT-CONVENTIONS.md) — project-wide conventions for documentation, reviews, repository structure, and commit publication.
3. [design/requirements-model.md](design/requirements-model.md) — the independent normative requirements and constraints model.
4. [design/component-model.md](design/component-model.md) — the independent normative model of components, roles, and interactions.
5. **Requirements of the current normative development stage**, followed by **the architecture of that same stage**.

Determine the current normative stage from the active project conventions and normative project artifacts. Locate the actual requirements and architecture paths for that stage; `design/<STAGE>/requirements.md` and `design/<STAGE>/architecture.md` are examples, not mandated names. **Do not hardcode NG1, NG2, NG3, or another stage in this instruction file.** Earlier stages are historical evidence, not automatically inherited design authority.

## Repository write authorization gate

Repository writes are allowed only in either of these two cases:

1. the user has explicitly instructed the agent to make the specific change; or
2. the user has explicitly started a continuous-development cycle (CD), in which case writes
   that are within the declared scope of that cycle may proceed autonomously under the normal
   CD rules.

Discussion, design exploration, review, brainstorming, or agreement on semantics is **not**
by itself authorization to modify repository state. Outside an active CD, keep repository
work read-only until the user explicitly asks for the change to be applied.

When a discussion appears ready to turn into implementation but no CD is active and no
explicit write instruction has been given, report the proposed change and stop at the
read-only boundary rather than silently beginning implementation.

## Requirement and component gates

Before implementing a material change:

- Identify exact applicable requirement and constraint IDs in the current stage and read their complete ancestry. Verify `Basis + Statement` for primary requirements, `Purpose + Statement` for derived requirements, and `Reason + Statement` for constraints. Check actor completeness, scope, closure status, and bottom-up constraint lifting.
- Confirm that requirements are sufficient to distinguish acceptable from unacceptable behavior. Do not invent product promises, constraints, or user-visible semantics in implementation.
- Check the current architecture and component model. A non-trivial review unit must have direct `Implements:` and, where applicable, `Constrained by:` traceability, a real scenario, component responsibilities and interaction boundaries, necessary external facts, a simplification review, and an evidence plan.
- Implementation begins only after the relevant requirement/design gates pass. A missing product decision returns to requirements work; a missing component contract returns to design; an uncertain kernel/platform fact requires an appropriately scoped experiment.
- Do not silently promote implementation convenience to product scope or allow lower-domain concepts to leak across an Adapter boundary.

## Process-correction gate

If an error is discovered in methodology/process, Git/snapshot/branch policy, CD cadence, or
another rule governing how project work is performed, **do not immediately repair it in
GitHub**.

Before any write:

1. stop work affected by the faulty process;
2. perform only the read-only inspection needed to characterize the problem;
3. discuss with the user:
   - what is wrong;
   - why the current rule/process produces incorrect behavior;
   - the proposed correction;
   - which process/project artifacts would change;
   - whether already-created consequences require repair;
4. wait for explicit user agreement on the proposed correction.

Only after that agreement may the process artifacts or the consequences of the process defect
be changed. This gate applies to project/process rules and Git-history/snapshot policy; it does
not turn ordinary implementation defects, test-harness fixes, or unambiguous fail-closed
hardening into mandatory human checkpoints.

## Normal continuous-development workflow

The following operations are **routine autonomous development work** and do not need separate user approval:

- Create/select dedicated cycle branches, determine `CYCLE_INTERVAL`, and designate the first cycle commit as `CYCLE_START_COMMIT` with its GitHub committer timestamp `T0`.
- Develop coherent review units, write and run the cheapest sufficient tests/evidence, perform required expert review, record findings/dispositions/verdicts, and apply accepted fixes.
- **Publish every commit to GitHub immediately**, including code, design, tests, reviews, fixes, and checkpoints. No unpublished local commit series.
- After each commit, use its actual GitHub committer timestamp to check `Tn - T0` against `CYCLE_INTERVAL`; at the threshold, complete the current review unit, publish its checkpoint, report the precise restart state, and stop pending the next user turn.
- After **each completed substantial logical work block**, publish that block's final committed tree to `main` as **one linear snapshot commit before starting the next logical block**. A CD cycle may therefore produce multiple mainline snapshots. A CD boundary by itself neither creates nor suppresses a snapshot. The working branch retains all intermediate commits and is not merged with its history into `main`.
- An explicitly started CD authorizes and requires autonomous progress across successive logical blocks until the `CYCLE_INTERVAL`/safety boundary or a genuine blocking boundary is reached. Completing the subsystem or topic that triggered the cycle does **not** end the CD by itself. Unless the user explicitly says the cycle is limited to one topic, treat that topic as the starting point and continue with the next highest-priority sufficiently defined, unblocked project block. Do not stop early merely because one review unit, subsystem, or design seam is finished. Early exit is appropriate only for a required human decision, an external blocker, absence of further sufficiently defined unblocked work, or the existing time/safety-margin rules in `CONTINUOUS-DEVELOPMENT.md`.

**Mainline snapshots are records of development checkpoints, not product-acceptance certificates.** A branch tip on the active development lineage is a legitimate snapshot point even if its name contains `pre-review` or `draft`. Do not impose a retroactive expert-review acceptance test on selection of historical checkpoint snapshots. Duplicate branch-tip SHAs produce one snapshot. Diverged/superseded branch tips whose work is already reflected in the continuing main development lineage are not separately snapshotted.

Before a routine snapshot, confirm the source/target HEADs, lineage, existing mainline snapshots, and absence of conflicting updates. Never copy unfinished work as the accepted outcome of an earlier checkpoint. If a routine snapshot cannot be published unambiguously because of divergence, conflicting `main`, uncertain lineage, or required retrospective reordering, do not begin the next logical development block: stop at read-only analysis and use the applicable process/history gate first. Mark absorbed cycle branches with the agreed `-absorbed` suffix where the repository tooling supports an actual rename without losing the branch or its history; do not create misleading duplicate aliases in lieu of a rename.

## Exceptional Git history or branch restructuring

Routine branch creation and checkpoint snapshots do **not** require a new approval. The following **exceptional** actions do require a prior read-only review and explicit user approval:

- Resetting or rewriting already published `main` history, including force-updating its ref.
- Retrospective reconstruction or reordering of historical snapshot commits.
- Removing or destructively relocating existing branches, or changing the agreed snapshot publication policy.
- Incorporating a diverged, dead-end, or ambiguous branch as a separate mainline snapshot contrary to the active lineage.

For such a change, first inspect branch tips, Git ancestry, existing checkpoints, and current refs. Present the exact before/after history, source SHA list and order, scope of preserved/excluded branches, and risks of duplication or lost changes. Request explicit user acceptance of that proposal before any exceptional ref changes.

An approved restructuring must be performed with a staged reconstruction when practical, verified against exact target tree hashes, and a final ref update guarded by the expected old HEAD. If the remote HEAD changes, stop and re-review instead of overwriting it.

Branch names are pointers to commit history; renaming them must not replace, discard, or rewrite their commits. Do not claim a branch has been renamed if only an additional alias was created.

## Evidence, review, and reporting

- Distinguish written tests from executed tests and passed CI from pending or failed CI.
- Use rootless tests for pure contracts and privileged disposable namespaces or target-specific experiments when necessary for Linux/kernel behavior.
- Store reviews and their dispositions in `design/reviews/` according to project conventions; preserve external reviews unchanged.
- End each work unit with its branch, exact SHA, verified evidence, review verdict, remaining gates, and next intended unit.
- A newly uncovered requirement/architecture ambiguity is not authorization to invent a solution in code.

If this entry point and a normative project document appear inconsistent, follow the applicable normative document and explicitly surface the discrepancy before the affected work.
