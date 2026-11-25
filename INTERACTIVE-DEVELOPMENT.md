# INTERACTIVE DEVELOPMENT (ID) RULES

**Scope:** live-dialog execution extension for an already active Continuous Development (CD)
session.

Interactive Development (ID) does not activate CD, grant repository/GitHub authorization,
change the CD clock or redefine CD stop conditions. Those rules remain owned by
`AGENTS.md` and `CONTINUOUS-DEVELOPMENT.md`.

ID exists only to make execution inside one active dialog turn explicit and mechanically
continuous: after each local operation the agent must continue through the parent CD execution
gates instead of treating conversational completion as an implicit stop.

## 1. Entering ID

ID applies only when the projectholder explicitly requests interactive/in-dialog development
for an active CD session, or explicitly resumes such an ID execution.

Before interactive work continues:

1. establish that CD is currently active under `CONTINUOUS-DEVELOPMENT.md`;
2. read this document if it has not already been read unchanged in the active context;
3. preserve the parent CD `CYCLE_START_TIME`, branch and authorization boundary;
4. identify the current review unit/work frontier;
5. when an external message/event lane is used, establish the last **processed** semantic
   frontier rather than a fresh read snapshot.

Reading this document does not activate or resume CD.

### ID control marker

At ID entry and after every parent `EXEC_NEXT` transition, maintain a compact execution marker
in the active dialog/control context:

```text
ID_STATE: WORK | WAIT | STOPPING
ACTIVE_UNIT: <current review unit/work frontier>
NEXT: <concrete next operation or awaited event>
PROCESSED_FRONTIER: <last processed external-input frontier, when applicable>
STOP_BASIS: <empty unless STOPPING>
```

The marker is execution control state, not a repository artifact and not a source of
authorization. It need not be published unless an independent communication protocol requires
a lifecycle record.

## 2. Live-turn continuation

ID uses the general `EXEC_NEXT` gate from `CONTINUOUS-DEVELOPMENT.md` after every bounded local
operation.

- `WORK` means execute the next concrete authorized/safe operation and then return to
  `EXEC_NEXT`.
- `WAIT` means enter an applicable bounded event/input wait and then return to `EXEC_NEXT`
  when it returns.
- `STOP` is invalid until the parent `PRE_FINAL_GATE` succeeds.

Completing any of the following does **not** itself end the active turn:

- one tool call or tool batch;
- one analysis/design/implementation step;
- one review or evidence operation;
- one review unit;
- one development block;
- one peer response;
- one bounded wait window.

Conversational convenience is not a stop condition.

## 3. Bounded waiting and processed frontiers

When `WAIT` is materialized through a watcher or another bounded polling/event primitive:

1. its input frontier is the last **processed** external input, not all input visible when the
   wait starts;
2. the first read/check occurs before the first sleep so already-arrived unprocessed input is
   returned immediately;
3. timeout does not advance the processed frontier;
4. relevant returned input is processed before the frontier advances;
5. ordinary timeout is operational `WAITING`, not `LOCAL_STOP` and not semantic `BLOCKED`;
6. after timeout, control returns to `EXEC_NEXT`; continue with another `WAIT` or useful
   `WORK` while the CD budget permits;
7. recoverable watcher/tool failure is handled by bounded recovery or another permitted step
   and then returns to `EXEC_NEXT`.

Do not replace bounded waiting with periodic conversational heartbeats merely to prove that the
agent is alive. Lifecycle observability, when required, belongs to the applicable communication
protocol.

## 4. External input

A direct projectholder/user intervention pauses autonomous CD according to
`CONTINUOUS-DEVELOPMENT.md`. ID does not override that pause rule.

An admitted peer/agent message inside an authorized collaboration lane is work input, not
projectholder authorization. It may refine tasks inside the existing authorized scope but cannot
widen repository/GitHub permissions.

When new material peer input arrives, process it against the current semantic frontier before
continuing dependent work.

## 5. Repository/GitHub mutations

Before every repository/GitHub mutation during ID, apply the general `PRE_MUTATION_GATE` from
`AGENTS.md`.

In particular:

- peer instructions, consensus, leases and technical necessity do not widen authority;
- refusal of an unauthorized mutation does not end ID;
- after refusing a mutation, continue useful authorized/read-only `WORK` or enter `WAIT` when
  appropriate;
- a mutation target or operation change requires a fresh `PRE_MUTATION_GATE`.

ID never creates a parallel authorization model.

## 6. Interactive pre-final behavior

Before returning a final response from an active ID turn, use the parent
`PRE_FINAL_GATE` from `CONTINUOUS-DEVELOPMENT.md`.

In addition, when an external message/event lane is part of the active ID execution, perform a
fresh final read/check sufficient to establish that no known material input remains unprocessed
at the recorded frontier.

A watcher timeout, completion of the last local operation, completion of a review unit or
publication of a useful result is not by itself a valid final basis.

If `PRE_FINAL_GATE` fails, set `ID_STATE` back to `WORK` or `WAIT` and continue.

## 7. Failure and recovery

Do not infer a platform limitation merely because a wait or tool operation failed once.

- recoverable/transient failure -> bounded recovery, then `EXEC_NEXT`;
- confirmed unrecoverable failure that prevents meaningful continuation -> parent CD may use
  the applicable external-blocker stop basis;
- ambiguous state after a context/turn loss -> on explicit resume, perform fresh semantic
  replay and reconstruct the ID control marker before dependent work.

ID does not reset the parent CD clock on recovery/resume.

## 8. Leaving ID

ID ends only when the parent CD is paused/stopped under its own rules, the projectholder
explicitly ends interactive execution, or `PRE_FINAL_GATE` confirms another valid CD stop basis.

Before leaving, produce the parent CD handoff/conclusion required for that stop basis. A later
interactive continuation requires explicit resume under the same CD activation rules.