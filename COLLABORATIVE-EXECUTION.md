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

Minimum v0 obligation fields:

```text
id
revision
kind
assignee_role
subject_refs[]
status = OPEN | CLOSED | SUPERSEDED | CANCELLED
blocked_on?       # structured predicate/ref
closure_ref?      # required for terminal disposition
```

A result/receipt does not automatically close an obligation. `NEEDS_INFO`, `PARTIAL`,
rejected work or a stale result may change readiness while the obligation remains open.

A superseded revision remains historical evidence and cannot mutate the replacement revision.

## 6. Readiness and passivation

A role is conceptually `READY` when at least one admitted unprocessed material input or open
unblocked obligation permits useful work within current authority/capability.

A role with no runnable work passivates instead of consuming model time merely to remain present.

On passivation publish or preserve enough durable state to explain what would make the role useful
again, for example an exact peer-result or holder-decision predicate.

Prefer **level-triggered readiness** and **edge-triggered wake delivery**:

- readiness remains true until relevant work is processed/dispositioned;
- one transition to useful READY state should normally cause one wake attempt;
- bursts coalesce into one activation so the role can drain all currently ready work;
- duplicate delivery does not create duplicate semantic work;
- ambiguous wake delivery is reconciled before blind retry.

The collaboration overlay does not define how a concrete ChatGPT/API/UI actuator wakes a role.

## 7. Control events

A v0 control event should be small and versioned. Minimum common fields:

```yaml
protocol: vpng-collab/0
event_id: <stable logical id>
kind: <known event kind>
room: <task-room identity>
to: [<role>]
cause_ref: <exact durable source ref>
```

Optional fields include `obligation`, `revision` and `payload_ref`.

Unknown protocol revisions, malformed required fields or conflicting reuse of an `event_id`
fail closed into `CONFLICT`; they do not create runnable authority.

Initial event kinds may include:

- `TASK_OPENED`;
- `WORK_READY`;
- `RESULT_READY`;
- `REVIEW_READY`;
- `REWORK_READY`;
- `HOLDER_DECISION_NEEDED`;
- `DORMANT`;
- `CONFLICT`.

The vocabulary may evolve only with protocol/version handling; free text never silently becomes a
new control kind.

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

- ingest configured durable control/task inputs;
- validate protocol envelopes;
- deduplicate logical/physical delivery;
- maintain a derivative local projection/cache;
- compute readiness/waiting/conflict with exact reasons;
- expose a compact status suitable for manual or future automated wake.

It must not:

- use an LLM to determine authority;
- invent product/review dispositions;
- treat local cache as canonical project truth;
- mutate project state merely because readiness is true;
- retry ambiguous external side effects blindly.

Loss of the local derivative state should be recoverable by replay/reconciliation from durable
project inputs, except for explicitly identified local delivery facts that cannot be reconstructed.

## 10. Failure and recovery

Distinguish at least:

- duplicate identical event -> idempotent;
- conflicting reuse of event identity -> `CONFLICT`;
- stale revision/result -> durable evidence, no mutation of current revision;
- missing/unknown dependency -> unresolved, not silently satisfied;
- helper/cache restart -> rebuild/reconcile before new wake;
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
