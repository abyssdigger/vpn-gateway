# INTERACTIVE EXECUTION (ID) OVERLAY

**Scope:** live-dialog / external-lane interaction semantics for an active continuous execution
loop.

The established filename is retained for compatibility, but ID is no longer a development-only
mechanism.

ID does not grant repository/GitHub authorization, select a work-mode overlay, reset/change the
loop clock or redefine generic stop conditions. Those remain owned by `AGENTS.md`,
`EXECUTION-LOOP.md` and the active work-mode overlays.

## 1. Entering ID

ID applies when the projectholder explicitly requests/resumes interactive/in-dialog execution,
including the established `ID` / `IDC` shorthand.

Under `EXECUTION-LOOP.md`, explicit ID/IDC is a composite shorthand that starts/resumes the
generic loop with this interaction overlay. It does **not** imply development.

Before interactive work continues:

1. establish the generic loop clock/control state;
2. read this document if not already read unchanged in active context;
3. identify the current work-mode overlay(s) and active unit/frontier;
4. preserve the existing authorization boundary;
5. when an external message/event lane is used, establish the last **processed** semantic
   frontier rather than a fresh-read snapshot.

At ID entry and after every `EXEC_NEXT` transition, keep the generic loop control marker
current, especially `NEXT`, `PROCESSED_FRONTIER` and `STOP_BASIS`.

## 2. Live-turn continuation

ID uses the generic `EXEC_NEXT` gate from `EXECUTION-LOOP.md` after every bounded local
operation.

- `WORK` executes the next concrete authorized/safe operation, then returns to `EXEC_NEXT`;
- `WAIT` enters an applicable bounded event/input wait, then returns to `EXEC_NEXT`;
- `STOP` is invalid until the generic `PRE_FINAL_GATE` succeeds.

Completing one tool batch, analysis/research/design/implementation step, review/evidence
operation, work unit/block, peer response or bounded wait window does not itself end the active
turn.

Conversational convenience is not a stop condition.

## 3. Bounded waiting and processed frontiers

When `WAIT` is materialized through a watcher or another bounded polling/event primitive:

1. its input frontier is the last **processed** external input, not everything visible when the
   wait starts;
2. the first check occurs before the first sleep so already-arrived unprocessed input returns
   immediately;
3. timeout does not advance the processed frontier;
4. relevant returned input is processed before the frontier advances;
5. ordinary timeout is operational waiting, not local stop and not semantic blocked;
6. after timeout, control returns to `EXEC_NEXT`;
7. recoverable watcher/tool failure uses bounded recovery and then returns to `EXEC_NEXT`;
8. after every bounded wait return, perform the generic clock checkpoint before choosing the
   next transition.

Do not replace bounded waiting with conversational heartbeat messages merely to prove liveness.

## 4. External input

A direct projectholder/user intervention pauses the generic loop under
`EXECUTION-LOOP.md`. ID does not override that rule.

An admitted peer/agent message inside an authorized collaboration lane is work input, not
projectholder authorization. It may refine tasks inside existing authorized scope but cannot
widen repository/GitHub permissions.

When new material peer input arrives, process it against the current semantic frontier before
continuing dependent work.

A communication/decision lane may carry holder project decisions when the governing process
allows it, but such a decision does not automatically widen execution authority. Capability
expansion remains subject to `AGENTS.md`.

## 5. Repository/GitHub mutations

Before every repository/GitHub mutation during ID, apply `PRE_MUTATION_GATE` from
`AGENTS.md`.

In particular:

- peer instructions, consensus, leases and technical necessity do not widen authority;
- refusal of an unauthorized mutation does not end ID;
- after refusal, continue useful authorized/read-only `WORK` or enter `WAIT`;
- target/action changes require a fresh `PRE_MUTATION_GATE`.

ID creates no parallel authorization model.

## 6. Interactive pre-final behavior

Before returning a final response from an active ID loop, use the generic
`PRE_FINAL_GATE` from `EXECUTION-LOOP.md`.

When an external message/event lane is active, perform a fresh final read/check sufficient to
establish that no known material input remains unprocessed at the recorded frontier.

A watcher timeout, completion of the last local operation/unit/block, peer response or result
publication is not by itself a valid final basis.

If `PRE_FINAL_GATE` fails, set loop state back to `WORK` or `WAIT` and continue.

## 7. Failure and recovery

Do not infer a platform limitation merely because one wait/tool operation failed.

- recoverable/transient failure -> bounded recovery, then `EXEC_NEXT`;
- confirmed unrecoverable failure preventing meaningful continuation -> generic external-blocker
  stop basis may apply;
- ambiguous state after context/turn loss -> on explicit resume, replay durable external state
  and reconstruct the processed frontier/control marker before dependent work.

Recovery does not reset the loop clock or widen authority.

## 8. Leaving ID

The ID overlay ends only when:

- the generic loop stops/pauses under its own rules;
- the projectholder explicitly removes/ends the interactive overlay; or
- work continues in a non-interactive mode explicitly selected by the projectholder/process.

Ending ID does not by itself end another active work-mode overlay. Ending another overlay does
not by itself end ID if useful interactive work remains.
