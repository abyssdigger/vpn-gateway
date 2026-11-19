# AGENTS.md — VPN-GATE agent operating instructions

**Scope:** All repository work, including requirements, architecture, implementation, tests, experiments, reviews, release documentation, and Git operations.

This file is an entry point, not a substitute for the normative project documents. An agent must read the current files in its actual working branch. Do not rely on summaries, prior chats, remembered conventions, or the repository's default branch as a proxy for the current development stage.

## Mandatory reading order — before starting work

Read these documents **in this exact order**:

1. [CONTINUOUS-DEVELOPMENT.md](CONTINUOUS-DEVELOPMENT.md) — continuous-development rules, review units, gates, evidence, expert review, cycle timing, and handoffs.
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

Semantic/design approval is **not** repository-write authorization. Agreement phrases such as
"yes", "ok", "looks good", "I agree", "that's fine", "let's do it", or equivalent approval of
the proposed content mean only that the proposal is accepted for discussion/design purposes.
They must not be interpreted as permission to mutate repository state.

Outside an active CD, repository mutation requires an explicit imperative directed at the
repository or a specific artifact, for example "apply this change", "edit AGENTS.md",
"update the requirements", "commit this", or "write this to the repository". If the user
approves a proposal but does not separately instruct the agent to apply it, remain read-only
and state that the proposal is agreed but has not been written to Git.


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

- Create/select dedicated cycle branches, determine `CYCLE_INTERVAL`, and record real `CYCLE_START_TIME` before mandatory reading or the first commit, as defined in `CONTINUOUS-DEVELOPMENT.md`.
- Develop coherent review units, write and run the cheapest sufficient tests/evidence, perform required expert review, record findings/dispositions/verdicts, and apply accepted fixes.
- Follow the immediate commit-publication rule in `PROJECT-CONVENTIONS.md` §7.
- After each commit, obtain fresh real current time and check elapsed time from `CYCLE_START_TIME` against `CYCLE_INTERVAL`. At the session-safety boundary, stop at the nearest safe technical point and produce the CD handoff; do not manufacture review-unit completion, a special checkpoint commit, or a mainline snapshot just because the window ended. Follow the exact handoff and safety-margin rules in `CONTINUOUS-DEVELOPMENT.md`.
- Publish completed development blocks using the snapshot policy in `PROJECT-CONVENTIONS.md` §6.1; the CD boundary itself does not define a block boundary.
- Follow `CONTINUOUS-DEVELOPMENT.md` for autonomous continuation across development blocks and the exact time/safety/decision conditions for stopping a CD.
- Any new user intervention pauses autonomous CD writes; follow the resume and one-change exceptions in `CONTINUOUS-DEVELOPMENT.md`.

Snapshot publication, absorbed branch naming and exceptional Git history operations
are governed exclusively by `PROJECT-CONVENTIONS.md` §§6.1–6.2.

## Evidence, review, and reporting

- Distinguish written tests from executed tests and passed CI from pending or failed CI.
- Use rootless tests for pure contracts and privileged disposable namespaces or target-specific experiments when necessary for Linux/kernel behavior.
- Store reviews and their dispositions in `design/reviews/` according to project conventions; preserve external reviews unchanged.
- End each review unit with its branch, exact SHA, verified evidence, review verdict, remaining gates, and next intended unit.
- A newly uncovered requirement/architecture ambiguity is not authorization to invent a solution in code.

If this entry point and a normative project document appear inconsistent, follow the applicable normative document and explicitly surface the discrepancy before the affected work.
