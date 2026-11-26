# COLLABORATIVE EXECUTION (COLLAB) OVERLAY

**Scope:** coordination semantics for multi-expert work inside an active continuous execution loop.

COLLAB composes with development, research and interactive execution. It does not grant repository,
GitHub, tool or external-service authority; redefine generic `WORK/WAIT/STOP`; or replace
requirement, architecture, review or evidence semantics owned elsewhere.

## 1. Roles and incarnations

A **role** is a stable collaboration responsibility. An **incarnation** is the current concrete
chat/session/model instance serving that role.

The projectholder defines role responsibility. A role change or replacement of an incarnation
does not silently change authority.

A typical development collaboration may use:

- `SPEC` — turns accepted product/project intent into an executable project-task specification:
  normative basis, scope/non-scope, acceptance criteria and required evidence;
- `GUARD` — requirements/process/authority/safety plus adversarial independent verification,
  terminal task acceptance and the COLLAB project-task gate protecting `main`;
- `BUILDER` — technical analysis, implementation, tests/evidence and finding correction;
- `ARCHITECTURE` — joint reconciliation responsibility rather than a third autonomous manager;
- `PROJECTHOLDER` — product/project decisions and execution-authority expansion.

These names are project configuration, not universal product semantics.

`SPEC` does not invent missing product semantics. If a complete executable specification requires
a genuine projectholder decision, SPEC routes that decision request under the normal holder contract
instead of silently choosing an option.

One incarnation may carry both `SPEC` and `GUARD` responsibilities. Their lifecycle meanings
remain distinct: authoring/maintaining a task specification is not acceptance of BUILDER's result.
In the current v1 pilot, SPEC is carried by the GUARD incarnation as a process responsibility and
does **not** add a new journal transport actor or mutate the immutable current-epoch role config.
A future journal-epoch migration may materialize it as a distinct transport role if useful.

`PROJECTHOLDER` is not a schedulable worker role in v0. Projectholder input arrives through the
configured human lane and is routed to worker roles for triage/reconciliation.

## 2. Activation and authority

Explicit projectholder COLLAB/collaborative-cycle wording activates this overlay on the generic
execution loop. It does not imply development or research unless that work mode is also active.

Collaboration never widens authority:

- a peer task, READY state, review, consensus, lease, ACK or technical need is not authorization;
- a projectholder product decision is not automatically an execution-authority grant;
- every repository/GitHub mutation still passes `AGENTS.md PRE_MUTATION_GATE`;
- a helper/scheduler must not infer authorization from free text;
- denied mutation does not close the collaborative work; authorized/read-only work may continue.

## 3. Collaboration surfaces

Keep canonical semantics, delivery hints and substantive payloads separate.

### Project-task Issue — work plane

For new implementation work tied to project Requirements/Constraints/architecture, the normal
human-facing unit of work is one dedicated GitHub **project-task Issue** created/curated by SPEC.

Its initial specification must be sufficient for BUILDER and GUARD to work without reconstructing
the assignment from chat history. It contains, as applicable:

- concise task objective and why it exists now;
- exact normative basis: relevant Requirement/Constraint IDs and accepted product/project decisions;
- relevant architecture/component/review/evidence refs;
- explicit in-scope and non-scope boundaries;
- observable acceptance criteria;
- required tests/evidence, including negative/fail-closed cases when safety semantics require them;
- documentation/traceability obligations;
- known dependencies/blockers and any decision that still belongs to PROJECTHOLDER.

After SPEC declares the Issue ready, the shared COLLAB coordination room receives only a short
routing notice containing the Issue number/ref and readiness/assignee information. From that point,
**task-specific substantive communication lives in the project-task Issue**: clarification,
implementation plan, technical findings, rework, evidence, review findings and acceptance.

Changes to the accepted task meaning must remain visible in that Issue. SPEC may clarify an
unambiguous specification; a material product/scope choice still requires its owning decision source.
Do not silently replace the original contract through off-thread chat or control-plane prose.

The project-task Issue is a work record, not repository/tool authority.

### Coordination/journal room — control plane

Configured shared pseudo-Issue(s) carry collaboration **control-plane** traffic:

- project-task readiness/routing by Issue ref;
- role/lease ownership and handoff;
- liveness/PING/PONG and bounded-wait coordination;
- scheduler/helper state;
- cross-task synchronization and process/recovery events;
- machine journal facts required by the active COLLAB protocol.

They do not become the ordinary discussion thread for a project task once a dedicated project-task
Issue exists. Do not duplicate long task specifications, implementation reports or GUARD reviews
there merely for transport.

Under control protocol v1 the current durable typed collaboration journal still has same-room
`payload_ref`/`closure_ref` constraints. Therefore this new work-plane split is a **prospective
protocol target** for new project tasks: current already-open v1 obligations may finish under their
existing task/journal-room contract. Before admitting the first new project-task obligation under
the split model, the helper/protocol must be adapted and reviewed so control-plane facts can bind the
project Issue without copying its substantive content back into the pseudo-Issue. Do not fake
compatibility by duplicating payloads.

Journal facts use the exact reserved first-line framing defined in §7. The journal remains canonical
for collaboration control semantics; the project-task Issue is canonical for the human-readable task
specification, implementation/review record and acceptance history.

### Signal room

A configured signal room is an **ephemeral delivery/wake optimization only**. It carries strict
recipient-specific SIGNAL comments that point to already-published durable journal facts.

A SIGNAL:
- never creates or erases semantic work;
- is optional for correctness;
- may disappear after durable recipient consumption without changing semantic replay;
- is not a source of authority;
- is never used as the canonical source for obligation, INPUT, disposition or health semantics.

Legacy v0 event-room epochs, including predecessor pilot streams, remain historical replay-log
evidence under the process version that created them. They are not reinterpreted as v1 signal rooms
and are not silently transplanted into the v1 journal.

### Projectholder room

A configured projectholder room is the human-facing collaboration lane.

Ordinary projectholder comments are accepted as **PRODUCT-MANAGER input**:
- they are strong evidence of desired product behavior, priorities and expectations;
- they are not assumed technically correct;
- they are not execution authority;
- GUARD/BUILDER must test them against requirements, architecture, evidence and counterexamples,
  and surface material inconsistencies rather than conform automatically.

The helper may turn each exact projectholder comment into a synthetic material input for routing,
without interpreting its prose.

Ordinary PRODUCT-MANAGER input is routed to configured triage roles; the v1 default is
`GUARD`.

An exact registered PROJECTHOLDER command is routed as one synthetic material input to **all
configured worker roles**. Each worker independently acknowledges that command input through the
normal handled/frontier mechanism. Routing does not execute the command and does not decide
whether its arguments satisfy an authority gate.

A comment beginning like a command but failing exact grammar/registry validation remains ordinary
PRODUCT-MANAGER input; a helper may expose a diagnostic but must not partially execute/infer it.

Ordinary PRODUCT-MANAGER input from this durable room does **not** pause an active collaboration
cycle merely by arriving. It is routed as material work input. A registered `STOP` command is
the explicit collaboration-lane pause/stop primitive.

#### Projectholder-lane polling and read receipt

While COLLAB is active, the worker role responsible for the configured projectholder routing must
successfully re-read the projectholder room:

- immediately on COLLAB activation or RESUME/recovery re-entry; and
- thereafter at intervals of **no more than 5 minutes of live-session time** until the loop is
  paused or stopped.

The 5-minute value is a maximum poll interval, not a reconstructed wall-clock claim. At each
`EXEC_NEXT`, a due projectholder poll takes precedence over starting another ordinary work unit.
Do not intentionally start a bounded wait/work operation that would defer a due poll beyond the
interval when a shorter scheduling choice is available. If an uninterruptible tool/external
operation crosses the interval, poll immediately when execution control returns and do not claim
that the blind interval was observed.

A restart never infers successful polling from GitHub comment timestamps. On re-entry, poll
immediately and start a fresh local cadence only after that successful read.

For each newly observed projectholder-authored work input:

1. classify it under the existing ordinary-input/registered-command rules;
2. place the actionable item into the appropriate current work/triage queue without widening
   authority; and
3. post one **very short worker-authored receipt** in the projectholder room stating that the exact
   holder comment(s) were read and what short work item/scope was queued.

Multiple newly observed holder inputs from one poll may be acknowledged in one compact receipt.
An empty poll produces no receipt. A control command or non-actionable input is acknowledged with
its truthful classification rather than falsely claiming it was queued.

The receipt is ordinary non-holder prose only. It is not a journal fact, HANDLED receipt,
authorization grant, semantic disposition or substitute for canonical task/journal routing.

A small versioned command registry is the only exception. A command is recognized only when the
**entire comment body** matches one registered form. Everything else remains ordinary
PRODUCT-MANAGER input.

Initial command forms are:

```text
!COLLAB STOP cycle=<cycle-key>
!COLLAB DENY capability=<capability-key> scope=<scope-key>
!COLLAB ALLOW capability=<capability-key> scope=<scope-key> [condition=<condition-key>] [until=<utc-key>]
!COLLAB MODEL role=<role-key> model=<model-key> scope=<scope-key>
```

Arguments are opaque identifiers resolved through the active collaboration configuration. They
are not arbitrary paths, shell fragments or free-text conditions.

Semantics:

- `STOP` — stop/pause the addressed collaboration cycle; no authority grant;
- `DENY` — restrict/revoke the named registered capability/scope;
- `ALLOW` — projectholder authorization input for the exact registered capability/scope under
  stated registered condition/expiry; actual use remains subject to `AGENTS.md`;
- `MODEL` — permit the named role/model change in the registered scope; no repository/tool
  authority is implied.

The registry is extensible only through normal process revision/review. Do not add natural-language
aliases.

The execution-loop clock/window is independent of the durable journal epoch and does not change
journal semantics.

For the v1 pilot, the **semantic journal configuration is immutable within one journal epoch**:
repository, task/journal rooms, roles/incarnations, projectholder actor/room/routing and the complete
command registry (including its cycle key) are fixed. A semantic-config change requires an explicit
reviewed journal-epoch migration/rollover; it is never reinterpreted in place.

The signal-room identity is transport configuration and may rotate independently under §10 without
changing the semantic journal configuration.

### Artifact plane

Large or version-sensitive results use repository artifacts and exact refs such as
`path@commit-SHA`. Task-room prose or journal facts reference them rather than copying them.

The signal room is only an optimization for delivery visibility. A future transport may derive
equivalent delivery hints from other durable sources, but must preserve the separation between
canonical journal semantics, ephemeral delivery signals and material payloads.

## 4. Independent first-pass and architecture reconciliation

For non-trivial work, roles whose independent judgment matters should first analyze the original
task/evidence independently where practical.

The purpose is to reduce premature conformity, not to prohibit necessary shared facts.

After first-pass:

1. compare requirements, unknowns, risks and technical decomposition;
2. reconcile architecture jointly;
3. preserve material disagreement explicitly;
4. escalate a genuine unresolved product/project ambiguity to `PROJECTHOLDER`;
5. do not treat peer agreement alone as proof of correctness or authority.

Any surviving projectholder product/project decision request must satisfy the self-contained
decision-request contract in `EXECUTION-LOOP.md` §8.1. A task-room, review or artifact ref may
support the request but cannot substitute for its semantic payload.

A joint architecture decision is working collaboration state, not a substitute for any required
normative project artifact or holder decision.

## 5. Mailbox, obligations and readiness

Keep three semantic projections distinct:

- **mailbox** — admitted durable material INPUTs;
- **obligations** — work whose future result matters to readiness, closure or a gate;
- **readiness** — derived answer to whether a role can do useful work now.

`READY` is never stored as semantic truth. It is recomputed from durable journal/holder inputs and
current obligations. Current signal-room contents are not semantic input to this computation.

Do not create an obligation merely to index every message. Create one only when losing the
obligation could make the collaboration stop while work remains, lose a blocker, wake forever on
resolved work, or mistake a stale/partial result for closure.

Minimum v1 obligation state is projected from admitted journal facts. `OPEN` supplies:

```text
id
revision
kind
assignee
disposition_by
subject/payload refs
```

Revision starts at 1. A later revision is current only after the previous revision has an explicit
`SUPERSEDED` disposition.

A result/receipt does not automatically close an obligation. `INPUT` may make another role
runnable while the obligation remains open.

A terminal `DISPOSITION` is structurally accepted only when:
- it targets the exact current obligation revision;
- its emitting role equals that obligation's `disposition_by`;
- its state is `CLOSED`, `CANCELLED` or `SUPERSEDED`;
- it carries an exact `closure_ref` to the already-published semantic disposition authored by
  the DISPOSITION sender's admitted transport actor.

This rule protects scheduler integrity; it does not make the helper an authority on whether the
referenced project/review disposition was substantively correct.

A superseded/stale revision remains historical evidence and cannot mutate the replacement revision.

A v1 `HANDLED` journal fact is a durable, content-bound receipt. For INPUT/holder targets it also
clears that role's unhandled-mailbox readiness. For delivery-only targets such as OPEN or
DISPOSITION it records consumption only and never removes the target's independent semantic effect.
The exact receipt format and GC relationship are defined in §7.

## 6. Readiness and passivation

A role is conceptually `READY` when at least one admitted unprocessed material input or open
unblocked obligation permits useful collaborative work.

This means **work exists only**. It is not:
- proof that a concrete chat/agent is terminal or awake;
- authentication of the role claim;
- repository/GitHub/tool authority;
- evidence that machine activation is eligible or safe;
- a replacement for generic `EXEC_NEXT`, ID `WAIT`, clock or stop/final gates.

A role with no runnable work may enter collaboration passivation state. A `DORMANT` event is
only that role's durable diagnostic self-claim and may carry an exact waiting reason. It never
suppresses a later derived `READY`.

`DORMANT` is **not** a generic `STOP` basis and does not by itself permit the live execution
turn to end.

While the continuous loop remains active:

- if no verified post-turn wake/activation path exists and an applicable bounded wait mechanism is
  available, a DORMANT/blocked role must enter bounded `WAIT`, then return to `EXEC_NEXT`;
- a bounded WAIT timeout is not successful passivation and is not semantic completion;
- ending the turn still requires `PRE_FINAL_GATE` and a real generic/overlay stop basis;
- if no bounded wait exists, or the session-safety boundary is reached, surface that operational
  blocker explicitly in the collaboration handoff/projectholder lane rather than treating
  `DORMANT` itself as the stop reason;
- only after a concrete post-turn wake mechanism has been separately demonstrated may an overlay
  define true terminal passivation semantics for that mechanism.

Therefore a durable `DORMANT` record can be correct while a terminal exit immediately after it is
still a process failure.

Use level-triggered readiness:
- readiness remains true until relevant material input is handled or the blocking obligation is
  dispositioned/blocked;
- bursts coalesce into one readiness state/reason set;
- duplicate delivery does not create duplicate semantic work;
- actual wake delivery is a separate transport concern;
- ambiguous external wake delivery must be reconciled before blind retry.

COLLAB does not define how ChatGPT/API/UI execution is activated and does not infer terminality
from silence, timeout or a `DORMANT` claim.

## 7. Control protocol v1 — durable journal + ephemeral SIGNAL

Control protocol v1 separates canonical collaboration facts from delivery hints.

Legacy `vpng-collab/0` event-room streams are historical/transition evidence only. Their exact
process remains recoverable from the repository version that created them. A v1 helper must not
merge a legacy v0 event-room replay with a v1 journal epoch.

### 7.1. Durable journal framing

A journal comment from a configured worker uses this exact first line:

```text
<!-- vpng-collab-journal/1 -->
```

It is followed immediately by exactly one fenced `json` object and no trailing prose.

Common semantic fields are:

```json
{
  "protocol": "vpng-collab/1",
  "journal_epoch": "opaque-journal-epoch",
  "event_id": "stable-logical-id",
  "kind": "OPEN",
  "room": 34,
  "from": "GUARD",
  "to": ["BUILDER"],
  "incarnation": "opaque-role-incarnation",
  "payload_ref": "issue:34#issuecomment-123"
}
```

The GitHub actor is transport identity. `from` and `incarnation` remain cooperative routing claims
and are not authentication or authority.

`journal_epoch` is configured explicitly. For the v1 pilot it binds one immutable semantic
configuration: repository, task/journal rooms, roles/incarnations, projectholder actor/room/routing
and the complete command registry. These values are replay semantics and must not change in place.

The execution-loop window is not part of journal identity. The signal-room identity is separate
transport configuration and may rotate without rolling the journal after reconciliation.

A semantic-config change requires explicit reviewed journal-epoch migration/rollover. General
journal archival/compaction remains a later process problem.

For configured worker actors:
- any comment whose first line begins `<!-- vpng-collab-journal/` is intended machine input;
- wrong marker version/protocol/epoch, malformed JSON/schema or invalid admission fails canonical
  replay closed;
- there is no arbitrary ignore/legacy list for current v1 journal facts.

Machine-looking comments from unconfigured external actors are excluded from machine and ordinary
payload admission and do not poison canonical replay.

The physical journal comment must be in its semantic `room` task room. A journal-framed comment
cannot be used as `payload_ref` or `closure_ref`.

Accepted v1 semantic kinds are:
- `OPEN` — create the first or explicitly superseding revision of a material obligation;
- `INPUT` — addressed material request/result; optionally references an obligation/revision and
  never closes it by itself;
- `HANDLED` — durable exact-content consumption receipt, with INPUT/holder mailbox semantics below;
- `BLOCK` — current assignee blocks an obligation on one exact preallocated logical INPUT ID;
- `DISPOSITION` — terminal `CLOSED|CANCELLED|SUPERSEDED` claim satisfying §5;
- `DORMANT` — diagnostic self-passivation claim; never suppresses derived readiness;
- `PING` — diagnostic communication-liveness probe addressed to exactly one peer role;
- `PONG` — diagnostic response to one exact admitted PING.

`CONFLICT` is helper output/state, not an accepted journal kind.

### 7.2. Payload and closure references

An ordinary `payload_ref`:
- must identify an exact non-journal comment in the same task room;
- is bound in canonical integrity state by physical ref, actor and exact body;
- may be authored by an actor different from the journal fact sender;
- never transfers payload authorship or authority to/from the fact sender.

A `closure_ref` remains stricter in v1:
- it must identify exact non-journal task-room prose in the same task room;
- its transport actor must equal the DISPOSITION sender's admitted transport actor.

Cross-task-room payload/closure refs remain invalid.

### 7.3. Content-bound HANDLED receipts

A v1 HANDLED contains exact targets, not bare logical IDs:

```json
"handled": [
  {
    "event_id": "x",
    "ref": "issue:34#issuecomment-123",
    "body_sha256": "<raw-whole-target-comment-sha256>"
  }
]
```

Rules:
- HANDLED is self-addressed and the emitting `from/incarnation` is the consuming role/session;
- every target must be an exact currently admitted physical journal fact addressed to that role,
  or an exact synthetic holder input addressed to that role;
- journal receipt identity is logical event ID + physical ref + raw whole-body digest;
- holder receipt identity is `holder:<comment-id>` + exact holder ref + raw whole-body digest;
- HANDLED may not target HANDLED;
- HANDLED itself receives no SIGNAL.

For INPUT/holder targets, validated HANDLED contributes the logical input identity to the semantic
handled set and clears only that recipient's unhandled-input readiness.

For OPEN/DISPOSITION/PING/PONG or other delivery-only eligible targets, HANDLED records durable
consumption without closing/removing their independent obligation/health semantics.

Identical logical journal events at distinct physical refs may deduplicate one semantic effect, but
receipts remain conservative per physical occurrence. This prevents a stale receipt from becoming a
destructive GC proof after local-ledger loss and physical target replacement/edit.

### 7.4. Ephemeral SIGNAL protocol

A configured signal-room worker comment uses exact first line:

```text
<!-- vpng-collab-signal/1 -->
```

followed by exactly one fenced JSON object and no trailing prose:

```json
{
  "protocol":"vpng-collab-signal/1",
  "journal_epoch":"opaque-journal-epoch",
  "signal_id":"stable-signal-id",
  "event_id":"canonical-journal-event-id",
  "journal_ref":"issue:34#issuecomment-123",
  "journal_sha256":"<raw-whole-journal-comment-sha256>",
  "from":"GUARD",
  "to":"BUILDER",
  "incarnation":"guard-gpt56-sol-current"
}
```

One SIGNAL addresses exactly one recipient role. A canonical fact addressed to N recipients may
have zero to N recipient-specific SIGNALs. Signal publication is optional for correctness.

A SIGNAL is admitted only when it resolves to an **already physically admitted current-epoch journal
fact** whose logical ID/ref/raw digest, sender role/incarnation and recipient all match.

No target-incarnation field exists in v1: canonical addressing remains role-scoped. The consuming
HANDLED records the actual consuming incarnation after normal config/incarnation reconciliation.

A missing SIGNAL never removes semantic work.

Malformed/mismatched SIGNALs, conflicting reuse of signal identity or a wrong journal target are
signal-plane diagnostics/quarantine only. They do not poison otherwise valid canonical journal
replay, but affected physical SIGNAL rows cannot become GC candidates. Unknown external actor
SIGNALs are ignored.

### 7.5. SIGNAL consumption and GC eligibility

For one SIGNAL pointing to exact journal occurrence F and recipient R, that SIGNAL becomes
GC-eligible only after a valid current-epoch HANDLED from R binds the exact F logical ID, physical
ref and raw digest.

All duplicate physical SIGNALs pointing to the same exact F occurrence and R may be candidates from
the same receipt. A receipt for another identical physical journal occurrence is insufficient.

No disappearance of a SIGNAL is a receipt.

GC candidate evidence contains at least:
- exact signal physical ref;
- signal transport actor ID;
- exact raw signal body digest;
- signal logical ID;
- target journal logical ID/ref/raw digest;
- recipient role;
- exact receipt journal ref(s).

A GC candidate is evidence only, never delete authority.

### 7.6. Communication health

PING/PONG remain durable journal facts and do not create, block, satisfy or close ordinary
obligations.

A valid PING:
- is addressed to exactly one configured worker role other than the sender;
- carries `ping_id` equal to its own `event_id`;
- carries no obligation/disposition semantics.

A valid PONG:
- carries the exact `ping_id` of one admitted PING;
- is in the same task room;
- reverses the exact sender/recipient roles of that PING.

A PONG is not an implicit GC receipt. If a PING SIGNAL should be deletable, the recipient emits an
exact HANDLED(PING) receipt.

Only a newly observed valid peer **journal fact** confirms peer communication liveness. SIGNAL
observation alone does not, because a future delivery actuator may publish/retry SIGNALs independently.

During an active collaboration cycle, the observer may use the local 10/5-minute policy:

1. after 10 minutes with no newly observed valid peer journal fact, publish at most one outstanding
   PING journal fact and optionally one SIGNAL to the peer;
2. wait up to 5 minutes for matching PONG or another new valid peer journal fact;
3. if neither arrives, report `COMMUNICATION_UNCONFIRMED(role, ping_id)` once to the projectholder
   lane;
4. suppress repetition until peer liveness is restored or PROJECTHOLDER changes the situation.

Elapsed live-session time is local observer state. Restart/replay never reconstructs elapsed time
from durable comment timestamps.

`COMMUNICATION_UNCONFIRMED` never declares a session ended, creates DORMANT, reassigns work,
changes incarnation/model or widens/revokes authority.

### 7.6.1. Non-blocking peer wait budget

Peer-response waiting and communication-health diagnosis are separate mechanisms.

When one role has issued a request whose completion depends on another role, the default
`PEER_WAIT_BUDGET` is **2 minutes** of live-session time. Expiry of this budget means only that
the current bounded peer wait has returned control to the waiting role. It does **not** mean the
peer is dead, DORMANT, STOPPED or replaced, and it does not satisfy, cancel or close the awaited
journal relation.

On peer-wait expiry the waiting role must immediately return to `EXEC_NEXT`:

1. if any independent authorized `WORK` exists, continue it;
2. if the current unit alone depends on the peer, keep that unit explicitly
   `WAITING_ON_PEER(<role>, <exact awaited event/request>)` and select another READY unit;
3. if no independent work exists, another bounded peer wait may be entered, subject to the same
   session-safety boundary and without converting repeated timeout into semantic closure.

A peer-wait timeout never:
- reassigns the peer's obligation or role;
- changes role/incarnation/model;
- permits the surviving role to emit the peer's journal fact, result, review or disposition;
- widens repository/GitHub authority;
- permits bypassing required independent review or preflight;
- advances canonical processed/handled state;
- creates a STOP basis by itself.

The 10/5-minute communication-health policy above remains diagnostic and may run independently.
Its PING/PONG state must not block the work scheduler. Conversely, continued independent work after
2 minutes is not evidence that communication is healthy.

A newly observed valid peer journal fact restores the ordinary work relation naturally. The role
then re-enters the previously waiting unit according to normal READY/frontier semantics; no special
"resume from timeout" semantic event is required.

### 7.7. Relation semantics

For OPEN, the obligation object contains at least:

```json
{
  "id": "O1",
  "revision": 1,
  "kind": "implementation",
  "assignee": "BUILDER",
  "disposition_by": "GUARD"
}
```

For BLOCK, `wait_for_event_id` names the exact logical INPUT event whose admission satisfies the
blocker. Multiple BLOCK claims on one current revision remain monotone/conjunctive.

Unknown semantic protocol revisions/kinds, malformed required fields, stale sender incarnation,
invalid room/actor/recipient, missing refs or conflicting logical event identity fail canonical
replay closed.

Task-room prose, comments such as “approved/merge it”, peer consensus, raw READY claims and SIGNAL
presence cannot directly alter canonical semantic state.

## 8. Development collaboration loop

When the development overlay is also active, the default project-task lifecycle is:

```text
accepted product/project intent
  -> SPEC creates/curates project-task Issue
  -> SPEC declares specification READY
  -> short control-plane notice: Issue #N ready for BUILDER
  -> BUILDER analysis / implementation / exact-SHA evidence in Issue #N
  -> BUILDER: READY FOR REVIEW
  -> GUARD adversarial terminal review
  -> findings -> BUILDER rework -> GUARD re-review
  -> GUARD ACCEPT
  -> final Issue comment links exact accepted commit SHA
  -> Issue CLOSED
  -> eligible for the additional AGENTS.md pre-main acceptance gate
```

The named roles are configurable; the invariant is separation of implementation and independent
verification where the task requires it.

### 8.1. SPEC contract

SPEC owns specification quality, not product authority. Before declaring a project-task Issue READY,
SPEC checks that the Issue has enough normative basis, scope, acceptance criteria and evidence
requirements to make implementation and later acceptance falsifiable.

A projectholder decision is requested when the residual ambiguity is genuinely product/project
semantic. SPEC must not hide that ambiguity by picking the technically convenient interpretation.

### 8.2. Builder completion is not acceptance

The process deliberately distinguishes:

```text
implementation success != task acceptance != Issue closure
```

BUILDER may report `IMPLEMENTATION COMPLETE` or `READY FOR REVIEW`, but never turns that fact into
a GUARD acceptance.

Compilation, successful startup, unit tests, integration tests, green CI and local/manual checks are
evidence. They establish only the properties they actually test.

### 8.3. GUARD terminal review and acceptance

GUARD reviews the proposed final result adversarially: the goal is to find a way the result fails the
accepted task contract despite apparently successful implementation/evidence, not to rationalize a
green build.

Before `GUARD ACCEPT`, GUARD independently verifies at least the applicable parts of:

- the **current accepted Issue specification**, including every accepted clarification/amendment;
- relevant Requirements/Constraints, architecture/component contracts and prior accepted decisions;
- exact final diff and absence of undeclared scope creep;
- correctness of tests/evidence and whether they prove the required properties rather than merely
  execute code;
- negative, ambiguity, drift, failure and fail-closed cases where the contract requires them;
- exact published commit SHA and durable CI/evidence bound to that SHA;
- documentation, architecture status and traceability changes required by the task;
- unresolved findings, known defects, TODOs, temporary bypasses or unverified assumptions that are
  incompatible with acceptance;
- compatibility/regression evidence materially affected by the change.

A GUARD finding returns the Issue to BUILDER rework. A corrected result invalidates the affected
evidence/review scope and must be reverified.

`GUARD ACCEPT` names the exact accepted source commit SHA. Any later task-affecting commit creates
a new candidate and invalidates the old acceptance until GUARD reviews the delta/new result.

### 8.4. Honest Issue closure

A project-task Issue is closed only after explicit GUARD acceptance.

The final pre-close comment must contain:
- the explicit acceptance verdict/ref;
- a direct exact commit SHA/link for the accepted final result;
- concise final evidence identity when useful.

Only after that comment is published and verified is the Issue moved to `closed`. BUILDER completion,
green CI, consensus or inactivity never closes the Issue by itself.

A newly discovered separate defect/requirement after honest closure normally creates a new linked
Issue instead of silently extending the accepted old task. Reopen only when the original acceptance
record itself is invalid or the same task was closed incorrectly.

### 8.5. Miscellaneous and holder-request work

Projectholder wishes, exploratory requests and work not yet attributable to a concrete project
Requirement/implementation task remain in the projectholder lane or a dedicated triage/misc Issue.
Once such work becomes a concrete project task, SPEC promotes it into a dedicated project-task Issue
and the work-plane lifecycle above applies.

## 9. Helper/scheduler and GC boundaries

### 9.1. Read-only semantic projector

A COLLAB helper may:
- ingest complete configured task/journal, projectholder and current signal-room observations;
- admit strict v1 journal facts and synthetic holder inputs;
- validate exact physical refs/digests and deduplicate logical semantic delivery;
- persist first-seen canonical hashes needed to detect later edit/conflict where observed;
- project current obligations/mailbox state through one semantic reducer;
- compute `READY`, `WAITING` or canonical `CONFLICT` with exact reason IDs/refs;
- project PING/PONG health relations separately from ordinary semantic readiness;
- validate current SIGNALs as noncanonical delivery hints;
- expose signal diagnostics and exact GC-candidate evidence;
- expose compact status suitable for manual or future activation adapters.

It must not:
- output or imply `ELIGIBLE_TO_ACTIVATE`;
- use an LLM to determine authority;
- invent product/review dispositions;
- treat role claims as authenticated identities;
- treat local cache as canonical project truth;
- mutate project state merely because readiness or a GC candidate is true;
- execute payloads, shell commands or arbitrary URLs from facts/signals;
- retry ambiguous external side effects blindly.

Canonical semantic replay is a pure function of durable current-epoch journal facts, synthetic holder
inputs and exact referenced ordinary payload/closure rows. The current SIGNAL set must not change
semantic obligations/mailbox/readiness.

For v1, local state is a derivative integrity/replay ledger, not a second semantic database.
Canonical retained ledger covers admitted journal physical records, holder inputs and referenced
payload/closure rows. Canonical state binds a **semantic-config hash** that excludes signal-room
identity; signal/transport validation may bind the current signal room separately. A successful
complete acquisition may atomically replace the current derived projection. Failed/incomplete
acquisition must not advance canonical processed/integrity state.

SIGNAL history is not canonical ledger state. Previously seen SIGNAL disappearance after GC is not
canonical conflict. A helper may retain advisory signal hashes for current diagnostics/compare, but
losing that advisory state must not change semantic replay.

Semantic replay remains relation/revision driven, never GitHub comment-ID/fetch-order driven.
Physical identity is still the exact room/comment reference for integrity and content-bound receipts.

With a retained canonical ledger, a changed/missing previously admitted journal/payload/holder record
is conflict/unresolved rather than last-write-wins. If that ledger is lost, replay reconstructs only
currently visible canonical claims; exact content-bound HANDLED receipts prevent a vanished/replaced
target from inheriting an old destructive GC proof.

Version-sensitive artifact refs must contain an exact commit identity. The helper may validate/pass
them through; it does not infer authority or execute artifact contents.

### 9.2. Outgoing preflight

Journal publication uses deterministic `preflight_journal_fact` against exact candidate bytes,
current config and a stable complete observation. It prospectively runs the canonical reducer before
the external write.

SIGNAL publication uses `preflight_signal` against an **already physically admitted** journal fact.
It validates exact candidate bytes/target/current config but creates no prospective semantic state.

Publication order is:

```text
journal fact -> remote verify/admit -> optional SIGNAL -> remote verify
```

An ambiguous send is reconciled before any retry. A SIGNAL loss cannot lose semantic work because
the journal fact already exists.

### 9.3. Separate GC janitor

Destructive SIGNAL deletion is owned by a separate least-privilege janitor, not the read-only
projector.

The janitor never decides semantic eligibility. It may act only on an exact precomputed GC candidate
and, when a separately registered current capability authorizes deletion:

1. re-read the exact current signal comment;
2. compare room/comment/actor/raw-body digest with the candidate;
3. pass a fresh `AGENTS.md PRE_MUTATION_GATE`;
4. DELETE that exact signal comment;
5. reconcile the result before any retry.

Absent after delete is confirmed success. Changed/ambiguous/read failure stops destructive retry.

The janitor must never delete task-room journal/payload comments, projectholder comments or Issue
bodies, and must never derive authority from HANDLED/readiness/GC eligibility.

Implementing/testing janitor logic does not grant a standing delete capability. Actual GitHub
deletion requires separate explicit projectholder authority/configuration.

## 10. Failure, recovery and protocol cutover

Distinguish at least:
- duplicate identical logical journal event -> one semantic effect, while physical occurrence
  identity remains available for receipts/integrity;
- conflicting reuse of journal logical identity/body -> canonical `CONFLICT`;
- overlapping pagination returning the same physical row identically -> one physical observation;
- stale revision/result -> durable evidence, no mutation of current revision;
- missing/unknown dependency -> unresolved, not silently satisfied;
- previously admitted canonical journal/payload/holder record edited or missing -> conflict/
  unresolved when detectable;
- incomplete/unstable acquisition -> no advancement of canonical integrity frontier;
- helper/cache restart -> rebuild/reconcile before reporting new readiness;
- local canonical ledger loss -> fresh-current replay only, with no claim of unseen historical
  integrity;
- exact HANDLED target changed/replaced -> receipt no longer matches that target;
- malformed/mismatched SIGNAL -> signal diagnostic/quarantine only, semantic journal remains valid;
- previously seen SIGNAL missing after GC -> no canonical conflict;
- ambiguous external send/delete -> reconcile before retry;
- changed protocol/governing process -> re-read/reconcile before dependent work.

A local role stopping or timing out does not imply collaborative semantic closure. Open obligations
remain durable in the journal and may make the role READY later.

### Legacy v0 event-room rollover

Legacy v0 replay-log epochs remain governed by the process version that created them. The failed #33
epoch and closed #36 epoch are preserved as immutable predecessor evidence for the current pilot.

A v1 helper must not scan them as part of current v1 semantic journal or SIGNAL state.

### v0 -> v1 M cutover

Cutover from a legacy event-room replay epoch to M requires:

1. a durable task-room checkpoint identifying the predecessor event room, exact final semantic
   state, last disposition/frontier, active role/incarnation identities, current holder frontier,
   process/helper head and unchanged authority boundary;
2. independent cross-review of that checkpoint;
3. a published/reviewed v1 process/helper head;
4. a new empty **signal-room** Issue;
5. explicit v1 config with:
   - signal room;
   - durable task/journal room(s);
   - projectholder room/routing;
   - exact persistent `journal_epoch`;
   - roles/incarnations;
   - current command registry/cycle key;
6. fresh v1 derivative local state rather than migration of a v0 local ledger;
7. fresh HANDLED receipts for currently visible holder inputs as needed after classification under
   the current registry;
8. no transplant/republication of closed v0 physical events into the v1 journal;
9. first new live work created as a fresh v1 journal fact.

The command-registry cycle key is fixed inside the current journal epoch. A later execution window
may reuse that collaboration key; the wall-clock execution interval is not the command cycle.
Changing registry semantics, holder routing or roles/incarnations requires an explicit reviewed
journal-epoch migration/rollover rather than in-place replay under new classification.

Old command-like holder comments never gain current authority merely because they replay; actual
authority still requires the exact current registry and `AGENTS.md` gate.

Old event-room comments are not deleted by cutover.

### v1 signal-room rollover

A signal room may be replaced independently when transport/UI maintenance requires it, because it is
not semantic state. The cutover must preserve the exact semantic journal configuration/hash and
journal epoch, change only the transport signal-room identity, and reconcile any ambiguous in-flight
signal send/delete. Signal-room replacement must never imply journal closure, obligation disposition
or authority change.

Journal archival/compaction/epoch rollover is intentionally outside v1 M scope and requires a later
explicit process design.

## 11. Handoff

A collaborative handoff adds to the generic/work-mode handoff:

- active roles and incarnations when known;
- current durable journal epoch and task/journal room identities;
- current signal room identity;
- processed canonical journal/holder frontier;
- open obligations and blockers;
- derived readiness/waiting reason per role;
- exact artifact/result/review refs;
- current signal diagnostics and unresolved ambiguous delivery/GC operations, when any;
- exact GC candidates only when they matter to continuation, clearly marked as non-authority;
- holder decisions or authority gates genuinely required; product/project decisions use
  `EXECUTION-LOOP.md` §8.1;
- current command-registry cycle key when projectholder commands matter.

Do not duplicate large payloads in the handoff when exact durable refs suffice. Do not treat SIGNAL
history as the semantic handoff frontier; canonical journal/holder state owns that boundary.
