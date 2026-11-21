# AGENTS.md — VPN-GATE agent operating instructions

**Scope:** all repository work.

This is the repository entry point. It owns reading discipline and all repository
write/publication rules. Other documents own their subject matter and must not duplicate these
rules.

## 1. Reading gate

After a new chat/context, compaction/reset, handoff, or any situation where active repository
instructions may have been lost:

1. read the current `AGENTS.md` from the actual branch/ref;
2. identify which project/normative documents are relevant to the task;
3. read only those relevant documents before relying on them.

Normal subject owners:

- `PROJECT-CONVENTIONS.md` — documentation/review conventions, repository layout, lineage,
  CHANGELOG;
- `design/requirements-model.md` — Requirement/Constraint model;
- `design/component-model.md` — component/interaction model;
- current-stage requirements — product semantics/scope/constraints;
- current-stage architecture — accepted architectural realization;
- experiment/review artifacts — only when their evidence/history is relevant.

`CONTINUOUS-DEVELOPMENT.md` is **not** a general prerequisite. Read it when the user
explicitly starts/resumes CD, or when the task itself edits/reviews CD process.

For product/implementation changes, read the relevant requirement ancestry and relevant
architecture/component-model sections. Do not force unrelated requirements/architecture into
documentation, process or repository-maintenance tasks.

### No duplicate read in one response

If a document was already read during the current assistant response from the same branch/ref
and its blob SHA has not changed, do not read it again. If it changes, re-read it before
dependent work.

This exception does not cross a new chat/context: previous read content may have been lost.

## 2. Git-state recovery

For repository/GitHub recovery or history diagnosis, start from the affected refs and newest
relevant commits by commit time; inspect their ancestry, trees and diffs first.

Do not semantically re-review an already clean `main` from scratch when recent ref/commit
history is sufficient. Broaden the search only when recent history does not explain the
state.

## 3. Repository write authorization

Repository state is read-only unless:

1. the user's active instruction explicitly orders the specific repository/artifact change;
   or
2. the user explicitly starts/resumes CD, authorizing writes within its active scope.

Discussion, review, brainstorming, semantic approval, “yes/ok/looks good”, or a question about
whether work can proceed is not write authorization.

Outside CD, an explicit edit/implementation instruction authorizes that change on a working
branch. It does **not** authorize `main`.

Write authorization must be present in active context; do not infer it across a context
transition.

## 4. Working branches and commit publication

Authorized work uses a dedicated working branch unless the user explicitly requests another
safe target.

Every created commit must be published to GitHub immediately and verified on the expected
remote branch before another commit is created.

On publication/verification failure, stop repository mutation; do not create another commit,
perform prolonged recovery, force-update or rewrite history. Report the last verified remote
state and any unverified work accurately.

## 5. `main` protection and snapshots

`main` is not a development branch.

Outside active CD, a `main` update requires an explicit user instruction to
publish/snapshot the accepted result to `main`.

During active CD, normal completed-development-block snapshots are included in CD
authorization unless the user explicitly changes/disables snapshot publication.

A normal snapshot:

- is one linear commit on `main`;
- records the exact final tree of the completed published working-branch tip;
- does not replay/merge intermediate working-branch commits;
- is created only for a completed development block, not because a CD window ended;
- is not duplicated for an already represented branch-tip/tree;
- never presents unfinished work as completed.

Before snapshotting, verify source/target heads, expected ancestry/tree and absence of an
incompatible `main` update. The user may explicitly choose another snapshot boundary.

### Exceptional history operations

Reset/rewrite/force-update of published `main`, retrospective snapshot reconstruction,
destructive branch movement/deletion, or publication of ambiguous diverged/dead-end history
always requires:

1. read-only diagnosis;
2. presentation of relevant before/after refs/SHAs, ancestry and loss/duplication risk;
3. explicit user approval of that specific operation.

If the remote head changes after approval, stop and re-review.

## 6. Process-correction gate

A governing process/Git/snapshot/CD rule is changed only after read-only diagnosis, an
explicit explanation of the proposed replacement and affected process artifacts, and explicit
user agreement. Then change only the agreed scope under the normal write gate.

Ordinary implementation/test defects do not use this gate unless they change governing
process.

## 7. Responsibility split between operating documents

The three top-level operating documents have deliberately non-overlapping responsibilities:

1. `AGENTS.md` contains **general rules for the agent's work with the repository**:
   reading discipline, write authorization, working-branch publication, `main` protection,
   snapshots, exceptional Git-history operations, process-correction gate and ownership of
   the other governing documents.
2. `CONTINUOUS-DEVELOPMENT.md` contains **only the machinery required to keep an explicitly
   requested CD session continuous and safe in time**: cycle start, real-time clock,
   continuation across work, pause/resume, session boundary and handoff. It must not duplicate
   general repository policy, requirement/component methodology or artifact-format rules.
3. `PROJECT-CONVENTIONS.md` contains **only project-artifact maintenance conventions**:
   language, formatting, review/experiment artifact handling, repository layout/lineage facts,
   naming and CHANGELOG conventions. It must not define agent authorization, `main` write
   policy, CD timing or requirement/component semantics.

When a rule appears to belong to more than one document, keep the normative rule only in the
owner above and use a short reference from the other document if needed.

## 8. Subject ownership

Do not restate detailed subject rules here.

- requirement changes follow `design/requirements-model.md` and current-stage requirements;
- component/interaction changes follow `design/component-model.md` and current architecture;
- CD execution follows `CONTINUOUS-DEVELOPMENT.md`;
- documentation/review/layout/lineage conventions follow `PROJECT-CONVENTIONS.md`.

Implementation must not invent missing product semantics or silently convert implementation
limitations into product scope.

If documents conflict, follow the document owning the affected subject and surface the
conflict rather than choosing convenient wording.
