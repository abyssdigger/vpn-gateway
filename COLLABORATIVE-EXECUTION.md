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

- `GUARD` — requirements/process/authority/safety/acceptance and independent verification;
- `BUILDER` — technical analysis, implementation, tests/evidence and finding correction;
- `ARCHITECTURE` — joint reconciliation responsibility rather than a third autonomous manager;
- `PROJECTHOLDER` — product/project decisions and execution-authority expansion.

These names are project configuration, not universal product semantics.

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

Keep control signals separate from substantive payloads.

### Event room

A configured event room is a compact control-plane lane. It carries small structured events and
exact references only. Do not use it for design essays, large reviews, code or evidence payloads.

### Task room

A task room holds substantive discussion for one collaborative unit: clarification, independent
first-passes, architecture reconciliation, questions, findings and dispositions.

### Artifact plane

Large or version-sensitive results use repository artifacts and exact refs such as
`path@commit-SHA`. The task/event room references them rather than copying them.

The event room is an optimization for signal visibility. A future transport may derive equivalent
events from other durable sources, but must preserve the same separation between control signal
and material payload.

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

A joint architecture decision is working collaboration state, not a substitute for any required
normative project artifact or holder decision.

## 5. Mailbox, obligations and readiness

Keep three projections distinct:

- **mailbox** — admitted material inputs/events;
- **obligations** — work whose future result matters to readiness, closure or a gate;
- **readiness** — derived answer to whether a role can do useful work now.

`READY` is never stored as semantic truth. It is recomputed from durable inputs and current
obligations.

Do not create an obligation merely to index every message. Create one only when losing the
obligation could make the collaboration stop while work remains, lose a blocker, wake forever on
resolved work, or mistake a stale/partial result for closure.

Minimum v0 obligation state is projected from admitted control events. `OPEN` supplies:

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
- it carries an exact `closure_ref` to the already-published semantic disposition.

This rule protects scheduler integrity; it does not make the helper an authority on whether the
referenced project/review disposition was substantively correct.

A superseded/stale revision remains historical evidence and cannot mutate the replacement revision.

## 6. Readiness and passivation

A role is conceptually `READY` when at least one admitted unprocessed material input or open
unblocked obligation permits useful collaborative work.

This means **work exists only**. It is not:
- proof that a concrete chat/agent is terminal or awake;
- authentication of the role claim;
- repository/GitHub/tool authority;
- evidence that machine activation is eligible or safe;
- a replacement for generic `EXEC_NEXT`, ID `WAIT`, clock or stop/final gates.

A role with no runnable work may passivate instead of consuming model time merely to remain
present. A `DORMANT` event is only that role's diagnostic self-claim and may carry an exact
waiting reason. It never suppresses a later derived `READY`.

Use level-triggered readiness:
- readiness remains true until relevant material input is handled or the blocking obligation is
  dispositioned/blocked;
- bursts coalesce into one readiness state/reason set;
- duplicate delivery does not create duplicate semantic work;
- actual wake delivery is a separate transport concern;
- ambiguous external wake delivery must be reconciled before blind retry.

COLLAB does not define how ChatGPT/API/UI execution is activated and does not infer terminality
from silence, timeout or a `DORMANT` claim.

## 7. Control protocol v0

Executable v0 events use one strict JSON object in a fenced `json` block. Legacy YAML bootstrap
records emitted before this rule are historical only and are not executable protocol.

Common required fields:

```json
{
  "protocol": "vpng-collab/0",
  "event_id": "stable-logical-id",
  "kind": "OPEN",
  "room": 34,
  "from": "GUARD",
  "to": ["BUILDER"],
  "incarnation": "opaque-role-incarnation",
  "payload_ref": "issue:34#issuecomment-123"
}
```

The GitHub actor is transport identity. `from` and `incarnation` are cooperative routing
claims and are not authentication or authority.

Accepted v0 kinds are:
- `OPEN` — create the first or explicitly superseding revision of a material obligation;
- `INPUT` — addressed material request/result; optionally references an obligation/revision and
  never closes it by itself;
- `HANDLED` — the emitting role acknowledges exact prior material event IDs; it is not semantic
  acceptance or closure;
- `BLOCK` — the current assignee marks an obligation blocked on one exact preallocated logical
  event ID through `wait_for_event_id`;
- `DISPOSITION` — terminal `CLOSED|CANCELLED|SUPERSEDED` claim satisfying §5;
- `DORMANT` — diagnostic self-passivation claim; never suppresses derived readiness.

`CONFLICT` is helper output/state, not an accepted peer event kind.

For `OPEN`, the obligation object contains at least:

```json
{
  "id": "O1",
  "revision": 1,
  "kind": "implementation",
  "assignee": "BUILDER",
  "disposition_by": "GUARD"
}
```

For `BLOCK`, `wait_for_event_id` names the exact logical `INPUT` event whose admission
satisfies the blocker. v0 intentionally uses this rigid causal form rather than a general
predicate language.

`HANDLED` can clear unhandled-mailbox readiness only for events addressed to the emitting role.
It cannot close obligations or handle work addressed exclusively to another role.

Unknown protocol revisions/kinds, unknown fields where strict validation forbids them, malformed
required fields, stale incarnation, invalid room/actor/recipient, missing refs or conflicting reuse
of event identity fail closed and do not create new readiness.

Task-room prose, comments such as “approved/merge it”, peer consensus or a raw READY claim are not
control events and cannot alter helper state.

## 8. Development collaboration loop

When the development overlay is also active, the default non-trivial flow is:

```text
task
  -> independent first-pass
  -> joint architecture reconciliation
  -> BUILDER implementation/evidence
  -> GUARD independent verification
  -> findings -> BUILDER rework
  -> GUARD re-verification
  -> convergence or PROJECTHOLDER gate
```

The named roles are configurable; the invariant is separation of implementation and independent
verification where the task requires it.

A review result can make rework READY without itself deciding product semantics. A corrected result
invalidates only the evidence/review scope actually affected.

## 9. Helper/scheduler boundary

A COLLAB helper may:
- ingest configured durable event/task inputs;
- validate strict protocol envelopes and configured physical transport admission;
- deduplicate logical/physical delivery;
- persist first-seen hashes needed to detect later edit/conflict where observed;
- project current obligations/mailbox state;
- compute `READY`, `WAITING` or `CONFLICT` with exact reason IDs/refs;
- expose compact status suitable for manual or future activation adapters.

It must not:
- output or imply `ELIGIBLE_TO_ACTIVATE`;
- use an LLM to determine authority;
- invent product/review dispositions;
- treat role claims as authenticated identities;
- treat local cache as canonical project truth;
- mutate project state merely because readiness is true;
- execute payloads, shell commands or arbitrary URLs from events;
- retry ambiguous external side effects blindly.

For v0, local state is a derivative integrity/replay ledger, not a second semantic database.
A successful complete acquisition may atomically replace the current derived projection. Failed or
incomplete acquisition must not advance durable processed/integrity state.

With a retained ledger, a changed/missing previously admitted event or payload is a conflict/
unresolved condition rather than last-write-wins. If that ledger is lost, replay can reconstruct
only currently visible claims; the helper must not pretend it can detect historical edits/deletes
that are no longer observable.

Version-sensitive artifact references must contain an exact commit identity. The helper may
validate syntax and pass such refs through; it does not infer authority or execute artifact
contents.

## 10. Failure and recovery

Distinguish at least:
- duplicate identical event -> idempotent;
- conflicting reuse of event identity/body -> `CONFLICT`;
- overlapping pagination returning the same physical event -> one logical effect;
- stale revision/result -> durable evidence, no mutation of current revision;
- missing/unknown dependency -> unresolved, not silently satisfied;
- previously admitted event/payload edited or missing -> conflict/unresolved when detectable;
- incomplete acquisition/page traversal -> no advancement of durable processed/integrity frontier;
- helper/cache restart -> rebuild/reconcile before reporting new readiness;
- local integrity ledger loss -> fresh-current replay only, with no claim of unseen historical
  integrity;
- ambiguous external send -> do not repeat until reconciled;
- changed protocol/governing process -> re-read/reconcile before dependent work.

A local role stopping or timing out does not imply collaborative semantic closure. Open obligations
remain durable and may make the role READY later.

## 11. Handoff

A collaborative handoff adds to the generic/work-mode handoff:

- active roles and incarnations when known;
- event/task room identities;
- processed control frontier;
- open obligations and blockers;
- derived readiness/waiting reason per role;
- exact artifact/result/review refs;
- holder decisions or authority gates genuinely required;
- conflicts/ambiguous deliveries requiring reconciliation.

Do not duplicate large payloads in the handoff when exact durable refs suffice.
