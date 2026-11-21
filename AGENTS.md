# AGENTS.md — VPN-GATE agent operating instructions

**Scope:** all repository work, including requirements, architecture, implementation, tests,
experiments, reviews, release documentation, process documents and Git operations.

This file is the repository entry point. It owns repository-reading discipline and all
repository write/publication rules. Other project documents own their subject matter and
must not duplicate these rules.

## 1. Reading gate

At the start of repository work after a new chat/context, context compaction/reset,
agent/model handoff, or any situation where the active repository instructions may have
been lost:

1. read the current `AGENTS.md` from the actual branch/ref being worked on;
2. identify which normative/project documents are relevant to the requested task;
3. read those relevant documents before relying on them.

Do **not** read every referenced document merely because it exists.

The normal subject owners are:

- `PROJECT-CONVENTIONS.md` — documentation language, review artifacts, repository layout,
  lineage and CHANGELOG conventions;
- `design/requirements-model.md` — Requirement/Constraint semantics and requirement-tree
  maintenance;
- `design/component-model.md` — component roles and interaction semantics;
- current-stage requirements — product semantics, scope and constraints;
- current-stage architecture — accepted architectural realization and traceability;
- experiment/review artifacts — only when the task depends on their evidence/history.

`CONTINUOUS-DEVELOPMENT.md` is **not** a general prerequisite. Read it when the user
explicitly starts/resumes a CD cycle, or when the task itself edits/reviews CD process.

For a material product/implementation change, read the relevant current-stage requirement
ancestry and the architecture/component-model sections needed to establish the affected
contract. For a documentation/process/layout task, do not force unrelated requirements or
architecture into the reading set.

### No duplicate reads inside one response

If a document has already been read during the current assistant response from the same
branch/ref and its blob SHA has not changed since that read, do not read it again.

If the document changes after it was read, re-read the changed document before performing
work that depends on it.

This optimization applies only while the current response still has the actual read content
and SHA in active context. A new chat/context transition must not assume that a previous
response's document content survived; perform the reading gate again for the new task.

## 2. Git-state recovery and history diagnosis

When the task is to recover, reconstruct or diagnose repository/GitHub state, begin from the
affected refs and the newest relevant commits by commit time. Inspect their ancestry, trees
and diffs first.

Do not start by semantically re-reviewing an already clean `main` from scratch when recent
commit/ref history is sufficient to establish what happened.

Broaden the historical search only when the recent commits do not explain the state or when
an ancestry/tree inconsistency requires it.

## 3. Repository write authorization

Repository state is read-only unless one of these is true:

1. the user's active instruction explicitly orders the specific repository/artifact change;
2. the user explicitly starts/resumes a CD cycle, in which case writes within that cycle's
   declared/current scope are authorized until paused or stopped by the CD rules.

Discussion, review, brainstorming, semantic agreement, “yes/ok/looks good”, or a question
about whether work can proceed is **not** write authorization.

Outside an active CD, an explicit instruction to edit a file or implement a change authorizes
that change on a working branch. It does **not** implicitly authorize publication to
`main`.

Write authorization does not survive a context transition by inference. After a new
chat/context, use only authorization present in the active user instruction/context.

### User intervention during CD

Any new user intervention pauses autonomous CD writes. Handle the intervention first.
Autonomous CD execution resumes only after an explicit resume/continue instruction.

If the intervention itself explicitly authorizes one specific repository change, only that
change is authorized; it does not implicitly resume the rest of the CD.

## 4. Working branches and publication

Authorized development/process/documentation work is performed on a dedicated working branch
unless the user explicitly requests a different safe target.

Every created commit must be published to GitHub immediately. Do not accumulate local-only
commits for later batch publication.

After each commit, verify that the exact commit is present on the expected remote branch
before creating the next commit.

If publication or verification fails:

- stop repository mutation immediately;
- do not create another commit;
- do not attempt prolonged recovery, force updates or history rewriting;
- report the last verified remote state and any unverified/unpublished work accurately.

## 5. `main` protection and snapshots

`main` is not a development branch.

Outside an active CD, authorization to modify a working branch does **not** authorize any
write to `main`. A `main` update requires an explicit user instruction to publish/snapshot
the accepted result to `main`.

During an explicitly active CD, the normal completed-development-block snapshot described
below is part of the CD authorization unless the user has explicitly disabled or changed
snapshot publication for that cycle/block.

A normal snapshot:

- is one linear commit on `main`;
- records the exact final tree of the completed published working-branch tip;
- does not merge/replay the working branch's intermediate commits into `main`;
- is created only for a completed development block, not merely because a CD window ended;
- is not duplicated when the same branch-tip/tree is already represented;
- must not present unfinished work as a completed block.

Before a normal snapshot, verify current source/target heads, expected ancestry/tree and that
`main` has not changed incompatibly.

The user may explicitly define a different snapshot boundary for a particular body of work.

### Exceptional history operations

The following always require read-only diagnosis followed by explicit user approval of the
specific operation:

- reset/rewrite/force-update of published `main`;
- retrospective reconstruction/reordering of historical snapshots;
- deletion or destructive movement of existing branches;
- publication of an ambiguous diverged/dead-end lineage as a snapshot;
- any operation that can discard or reinterpret already published history.

Present the relevant before/after refs/SHAs, ancestry and loss/duplication risks before such
approval. If the remote head changes after approval but before execution, stop and re-review.

## 6. Process-correction gate

A defect in the project's governing process, Git policy, snapshot policy, CD cadence or other
project-operating rule must not be silently corrected while doing unrelated work.

Before changing a governing process rule:

1. diagnose the current rule and consequence read-only;
2. explain the proposed replacement and affected process artifacts;
3. obtain explicit user agreement;
4. change only the agreed scope under the normal repository write gate.

Ordinary implementation/test defects do not use this gate unless they actually change the
governing process.

## 7. Subject-matter gates

Do not duplicate the detailed rules of the subject owners here.

When a task changes product behavior or requirements, follow
`design/requirements-model.md` and the relevant current-stage requirement tree.

When a task changes component responsibilities/interactions, follow
`design/component-model.md` and the relevant current-stage architecture.

Implementation must not invent missing product semantics, silently promote implementation
limitations to product scope, or bypass an unresolved requirement/architecture decision.

Evidence/review/experiment artifacts follow their governing model/conventions and are read
only when relevant to the current task.

## 8. Authority

If project documents appear inconsistent, use the document that owns the affected subject:

- this file: reading discipline; repository write authorization; branch publication;
  `main` protection/snapshots; exceptional Git-history operations; global process-correction
  gate;
- `CONTINUOUS-DEVELOPMENT.md`: CD execution model, review/development-block cadence,
  session clock and handoff;
- `PROJECT-CONVENTIONS.md`: documentation/review conventions, repository structure,
  lineage facts and CHANGELOG;
- requirements/component models and current-stage artifacts: their respective semantic
  domains.

Surface a material conflict instead of choosing whichever wording is more convenient.
