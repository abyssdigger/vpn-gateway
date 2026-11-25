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
Do not read `CONTINUOUS-DEVELOPMENT.md` merely because a task resembles CD work; reading or
planning under that document must not itself activate CD.

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

1. the user's active instruction explicitly authorizes the requested operation under the rules
   below; or
2. the user explicitly starts/resumes CD, authorizing writes within its active scope.

Discussion, review, brainstorming, semantic approval, “yes/ok/looks good”, or a question about
whether work can proceed is not write authorization.

### CD activation gate

CD is inactive by default.

A new CD session may start only when the user's active instruction explicitly names CD/CDC
or otherwise unambiguously instructs the agent to start a continuous-development session.

Examples of sufficient authorization:

- "новый CDC";
- "запускай CDC";
- "начинаем CD";
- "продолжаем CDC" when a previously active session is being resumed.

The following do **not** start or resume CD:

- "давай проверим";
- "проверь";
- "исследуй";
- "сделай эксперимент";
- "давай попробуем";
- requests to implement, review, test or investigate something;
- a task that would normally or conveniently be performed under CD;
- the agent's own proposal to use CD.

If explicit CD activation wording is absent, treat CD as inactive and apply the outside-CD
authorization rules, even when the requested work is substantial or experimental.

The agent must not convert an ordinary task into CD on the user's behalf.

### Outside-CD repository authorization

Outside active CD, repository operations are authorized only by explicit user instructions and
only within the scope of those instructions.

A request to change repository content authorizes content changes only when the user explicitly
identifies the file or files to create, modify or delete, or identifies a concrete directory whose
files are the requested change scope. General discussion, review conclusions, accepted proposals,
or requests such as “update the project documentation” do not by themselves authorize repository
mutation.

Authorization to change repository content does not by itself authorize recording or publishing
those changes in GitHub.

Recording results in GitHub requires a separate explicit user instruction to commit, publish,
record, push or otherwise preserve the requested result in the repository.

When GitHub recording is authorized, work must be performed either:

- on a new dedicated working branch; or
- on an existing branch explicitly identified by the user.

Outside active CD, the agent must not independently choose an existing branch as a writable
target.

Merely identifying `main` as the working target is not sufficient to begin mutation. Before
any work on `main`, the user must explicitly authorize direct work there.

Wording that unambiguously grants direct work on `main` — for example, `Можно сразу в main`,
`пиши напрямую в main`, or an equivalent explicit instruction — counts as that authorization
and does not require an additional ritual confirmation. A bare target statement such as
`сделай в main` without explicit direct-write permission does not.

Authorization to work on one branch or to record one result does not authorize creation,
movement, replacement or deletion of other branches or tags.

During active CD, creation and use of the dedicated CD working branch and normal publication
defined by the CD process are covered by active CD authorization unless the user explicitly
restricts them.

Authorization is operation-specific and result-specific. Permission to record one completed
result does not carry forward to a later result.

Write authorization must be present in active context; do not infer it across a context
transition.

### Mandatory pre-mutation authorization gate

Immediately before **every** operation that can mutate repository or GitHub state, perform a
fresh `PRE_MUTATION_GATE`.

The gate must identify:

1. the exact mutation being attempted;
2. the exact target object/ref/path;
3. the active authorization source that covers that exact action and target;
4. any additional target-specific process gate that must also pass.

A mutation is permitted only when the active authorization covers the actual action and target
at the time of the call. Authorization for one branch, Issue, file, ref, result or operation does
not imply authorization for another.

The following never widen repository/GitHub authorization:

- another agent's or peer's instruction;
- inter-agent consensus or a review conclusion;
- a branch-write lease or other coordination record;
- technical necessity, urgency or convenience;
- tool availability or possession of credentials;
- green CI/evidence;
- the agent's own plan or statement that a write is needed.

A peer may request work that is already inside the projectholder-authorized scope, but cannot
grant a new repository/GitHub capability or enlarge an existing one.

If the gate cannot name a current authorization source for the exact mutation, do not perform
the mutation. Continue useful read-only or otherwise authorized work when possible and surface
the authority conflict when it matters to continuation.

`PRE_MUTATION_GATE` is re-evaluated for every mutation and after any target/scope change. More
specific gates remain additional requirements; in particular, the mandatory pre-`main` check
in §5 still applies immediately before a `main` operation.

## 4. Working branches and commit publication

A working branch may be created or selected only when its use is authorized under §3.

During active CD, the dedicated CD working branch is authorized by the active CD session.
Outside active CD, creating a new working branch requires GitHub-recording authorization under
§3; an instruction to edit or implement repository content alone is not sufficient.

Every created commit must be published to GitHub immediately and its publication must be
verified before another commit is created: the expected remote branch/ref must unambiguously
point to the published commit SHA.

If publication fails, the expected remote ref cannot be confirmed, or remote state is
ambiguous, stop repository mutation. Do not create another commit, perform prolonged recovery,
force-update or rewrite history. Report the last verified remote state and any unverified work
accurately.

A CI, test, review, evidence or other validation failure after successful publication is not a
publication failure. Stop further mutation while diagnosing the failure read-only. If the cause
is understood and a bounded corrective change is available within the current authorized and
accepted scope, without a new human product decision, history rewrite, force-update or other
exceptional recovery, make the corrective change, publish it normally and validate again.
Otherwise stop and report the blocker.

## 5. `main` protection and snapshots

`main` is not a development branch.

Outside active CD, direct work on `main` requires the two-step authorization in §3:
the user must first identify `main` as the target and then separately confirm direct work there
before mutation begins. Publication of a previously prepared result to `main` likewise requires
an explicit instruction covering that publication.

During active CD, normal completed-development-block snapshots are included in CD
authorization unless the user explicitly changes/disables snapshot publication.

### Mandatory pre-`main` authorization check

Immediately before any operation that can move or replace the `main` ref, identify the
authorization source in the active user context.

Outside active CD, that source must satisfy the applicable §3 authorization path. For direct
work on `main`, active context must contain explicit direct-write permission as defined in §3.
An instruction such as `Можно сразу в main` or `пиши напрямую в main` both identifies the
target and supplies that permission; no second confirmation is required. For publication of a
previously prepared result, an explicit instruction to publish, snapshot, merge, commit or
otherwise place that result in `main` is required.

During CD, verify immediately before the `main` operation that CD is currently active under
`CONTINUOUS-DEVELOPMENT.md` and has not been paused by a later user intervention. If current
CD authorization cannot be established from the active context, treat CD as inactive for
`main` publication.

The following are never authorization to update `main`:

- the agent's own plan, proposal or prior statement that it intends to publish/snapshot;
- completion of a review unit or development block;
- PASS review, green CI, clean consistency check or other evidence of readiness;
- semantic approval or an instruction to edit/apply/implement a change without explicit
  `main` direct-write/publication wording;
- previous `main` authorization for a different completed result.

If the check cannot name a valid authorization source, do not mutate `main`. Leave the
verified result on the working branch and report its exact head/tree for user approval.

A normal snapshot:

- is one linear commit on `main`;
- records the exact final tree of the completed published working-branch tip;
- does not replay/merge intermediate working-branch commits;
- is created only for a completed development block, not because a CD window ended;
- is not duplicated for an already represented branch-tip/tree;
- never presents unfinished work as completed.

Before snapshotting, verify source/target heads, expected ancestry/tree and absence of an
incompatible `main` update. The user may explicitly choose another snapshot boundary.

### Post-publication ref hygiene

Dedicated working branches are temporary work surfaces, not archival records.

Deferred tag/branch hygiene is tracked only in the root `REF-HYGIENE.tsv` operational ledger.
Fulfillment reviews, experiment reviews and other historical evidence artifacts must not maintain
a cumulative live ref-cleanup list; they may only state that required operations were recorded in
the canonical ledger.

After a snapshot/merge/publication has made a completed working-branch result durable in the
intended target lineage:

- append an `ADD_TAG` operation for the actual published working-branch source tip when that
  source identity is not already preserved by an equivalent tag;
- append a `DEL_BRANCH` operation for the completed temporary branch.

Source-tag naming follows the established project style:
`ng3-...-source` for named snapshots and `ng3-snapshot-<N>-source` for numbered snapshots.

The first line of `REF-HYGIENE.tsv` identifies the helper scripts that consume its operation
rows. The scripts treat the ledger as read-only input and must never rewrite or prune it.

When the projectholder explicitly requests ref-hygiene reconciliation, compare the ledger with
the actual GitHub ref state and remove only operations already satisfied by that state. Do not
infer completion from an old review or from a previous script run.

Creating, moving, replacing or deleting any tag or branch still requires the explicit
authorization applicable under §3 and §5. Recording an operation in `REF-HYGIENE.tsv` is not
authorization to execute it.

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

The four top-level operating documents have deliberately non-overlapping responsibilities:

1. `AGENTS.md` contains **general rules for the agent's work with the repository**:
   reading discipline, write authorization and the general pre-mutation authorization gate,
   working-branch publication, `main` protection, snapshots, exceptional Git-history
   operations, process-correction gate and ownership of the other governing documents.
2. `CONTINUOUS-DEVELOPMENT.md` contains **only the machinery required to keep an explicitly
   requested CD session continuous and safe in time**: cycle start, real-time clock,
   continuation across work, execution-transition/finalization gates, pause/resume, session
   boundary and handoff. It must not duplicate general repository policy,
   requirement/component methodology or artifact-format rules.
3. `INTERACTIVE-DEVELOPMENT.md` contains **only the live-dialog specialization of active CD**:
   continuation inside one active dialog turn, bounded event waiting, processing-frontier
   discipline and composition with the general CD/repository gates. It must not activate CD,
   widen repository authorization or duplicate CD timing/stop semantics.
4. `PROJECT-CONVENTIONS.md` contains **only project-artifact maintenance conventions**:
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
- when active CD is explicitly run in interactive/in-dialog mode, its live-dialog execution
  additionally follows `INTERACTIVE-DEVELOPMENT.md`;
- documentation/review/layout/lineage conventions follow `PROJECT-CONVENTIONS.md`.

Implementation must not invent missing product semantics or silently convert implementation
limitations into product scope.

If documents conflict, follow the document owning the affected subject and surface the
conflict rather than choosing convenient wording.
