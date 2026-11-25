# CONTINUOUS EXECUTION LOOP RULES

**Scope:** generic continuous execution independently of the kind of work being performed.

This document owns only execution-loop mechanics. It does not grant repository/GitHub authority,
define development semantics, decide research conclusions or define project artifact conventions.
Those remain owned by `AGENTS.md` and the active overlays.

## 1. Composition model

One execution loop may have one or more overlays active at the same time.

Established overlays are:

- `CONTINUOUS-DEVELOPMENT.md` — development work;
- `INTERACTIVE-DEVELOPMENT.md` — interactive/live-dialog execution (ID);
- `RESEARCH.md` — research work.

The loop is the lifecycle; overlays add semantics to the current work. Switching or adding an
overlay does not start a second clock and does not create a second authorization model.

Examples:

```text
loop + development
loop + development + ID
loop + research
loop + research + ID
```

A future experiment/emulation overlay may be added when a concrete use case requires semantics
not already owned by research/project experiment rules. Do not invent such an overlay merely for
symmetry.

## 2. Activation and backward-compatible shorthands

A continuous execution loop starts or resumes only after an explicit projectholder instruction
to start/resume/continue continuous execution, or through an explicit composite shorthand whose
meaning includes the loop.

Established shorthands:

- `CD` / `CDC` -> loop + development overlay;
- `ID` / `IDC` -> loop + interactive overlay, with the work-mode overlay determined by the
  assigned task; it does **not** imply development by itself;
- an explicit `research loop` / continuous-research instruction -> loop + research overlay.

The projectholder may explicitly compose overlays, for example an interactive research cycle.

Ordinary requests such as “check”, “research”, “review”, “test” or “try” do not start a
continuous loop merely because the task could benefit from one.

Loop or overlay activation never grants repository/GitHub authority. The only established
authorization shortcut remains explicit CD/CDC activation as defined by `AGENTS.md`; all other
loop modes use the ordinary authorization rules.

## 3. Entering a loop

Before continuous execution begins:

1. choose `CYCLE_INTERVAL`: the user-specified interval, otherwise **30 minutes**;
2. obtain fresh real current time in UTC and record it as `CYCLE_START_TIME` with an explicit
   UTC offset (`Z` or `+00:00`);
3. read this document if it has not already been read unchanged in the active context;
4. apply the `AGENTS.md` reading gate and read the active overlay documents;
5. establish the current work frontier and any external-input processed frontier;
6. preserve the current authorization boundary exactly as established by `AGENTS.md`.

If fresh real UTC time cannot be obtained, do not begin autonomous continuous execution.

The clock starts before mandatory reading or preparation. Commit timestamps, local timezone and
inferred location are not substitutes for `CYCLE_START_TIME`.

Maintain a compact control marker in active execution context:

```text
LOOP_STATE: WORK | WAIT | STOPPING
ACTIVE_OVERLAYS: <development/research/ID/...>
ACTIVE_UNIT: <current work frontier>
NEXT: <concrete next operation or awaited event>
PROCESSED_FRONTIER: <last processed external-input frontier, when applicable>
STOP_BASIS: <empty unless STOPPING>
```

The marker is control state, not a repository artifact and not a source of authorization.

## 4. Mandatory execution transition gate

After every bounded local operation that returns execution control to the agent, perform
`EXEC_NEXT` before deciding whether to continue or finish the active turn.

A bounded local operation includes, for example:

- a tool/read/write batch;
- a mutation/publication and its verification;
- a validation/test/review result;
- one analysis/design/research/implementation step;
- completion of an overlay-specific unit/block;
- return from a bounded external-event wait.

`EXEC_NEXT` must choose exactly one transition:

- `WORK` — a concrete, sufficiently defined, authorized and safe next step exists; execute it;
- `WAIT` — progress depends on an external event/input and the active execution mode provides an
  applicable bounded wait mechanism; enter that wait, then return to `EXEC_NEXT`;
- `STOP` — continuation is not permitted/appropriate under a currently true generic or
  overlay-specific stop basis; enter `PRE_FINAL_GATE` before ending the turn.

Completion of a local operation, one work unit, one peer response, the originally mentioned
subsystem or a bounded wait timeout is not by itself a `STOP` basis.

A refused unauthorized mutation is likewise not a `STOP` basis. Return to `EXEC_NEXT` and
continue authorized/read-only work or `WAIT` when appropriate.

## 5. WAIT semantics

`WAIT` is valid only when progress actually depends on external input/event and an active
interaction mechanism can materialize a bounded wait.

The interaction overlay may define watcher/frontier mechanics. At the generic level:

- ordinary timeout means the wait returned control; it is not semantic completion;
- recoverable wait/tool failure returns to `EXEC_NEXT` after bounded recovery;
- timeout or failure must not silently advance a processed semantic frontier;
- do not use an unbounded wait that can bypass the session-safety boundary.

## 6. Clock and session-safety boundary

`CYCLE_START_TIME` does not reset because:

- an overlay changes;
- a work unit/block completes;
- the user sends a message;
- a branch changes for continuation;
- a snapshot/result is published.

Active overlays may define additional mandatory clock checkpoints and may be stricter than this
document.

At minimum, obtain fresh real UTC time:

- at every overlay-defined unit/block/handoff boundary;
- after returning from a bounded `WAIT`;
- immediately before `PRE_FINAL_GATE`;
- whenever elapsed time is uncertain enough that starting another operation could consume the
  safety reserve.

If fewer than **3 minutes** remain before `CYCLE_INTERVAL`, do not start new material work.
Move to the session-safety stop path and prepare a truthful handoff.

Do not intentionally run materially beyond the interval to finish a unit.

## 7. User intervention and pause/resume

Any new direct projectholder/user intervention pauses autonomous continuous execution
immediately.

Handle the intervention first. Resume autonomous continuous execution only after an explicit
resume/continue instruction, except for a bounded operation explicitly requested by that
intervention.

Completing such a bounded operation does not silently resume the prior autonomous loop.

The original `CYCLE_START_TIME` remains unchanged while paused.

Peer/agent input in an admitted collaboration lane is work input, not direct projectholder
intervention and not execution-authority expansion. Its authority consequences are governed by
`AGENTS.md`.

## 8. Generic stop bases and PRE_FINAL_GATE

A generic stop basis exists when one of the following is currently true:

- a required human decision blocks all meaningful permitted continuation;
- an external blocker prevents meaningful continuation;
- no sufficiently defined unblocked work remains across the active overlays;
- an active overlay or owning process document defines a stop condition that is currently true;
- the session-safety boundary has been reached;
- a direct user intervention has paused the loop and no bounded requested operation remains.

Before ending an active loop turn or returning a final/handoff response, perform
`PRE_FINAL_GATE`.

The gate must:

1. name the exact currently applicable generic or overlay-specific stop basis;
2. verify that basis against current observable facts rather than infer it from completion of the
   last local operation;
3. verify that the active frontier has no safer permitted `WORK` transition and, when an
   applicable bounded waiting mechanism exists, no required `WAIT` transition;
4. perform any active-overlay final checks, including an external-lane final read when required;
5. prepare the truthful handoff/conclusion required for the actual stop basis.

If no permitted stop basis is true, `STOP` is invalid: return to `EXEC_NEXT` and choose
`WORK` or `WAIT`.

## 9. Recovery

Do not infer a platform limitation from one recoverable wait/tool failure.

- recoverable/transient failure -> bounded recovery, then `EXEC_NEXT`;
- confirmed unrecoverable failure preventing meaningful continuation -> external-blocker stop
  basis may apply;
- context/turn loss -> on explicit resume, replay durable state, reconstruct the control marker
  and processed frontier before dependent work.

Recovery/resume does not reset the loop clock or widen authority.

## 10. Common handoff

When the loop stops, provide only the state needed to resume cheaply and truthfully:

- `CYCLE_INTERVAL` and UTC `CYCLE_START_TIME`;
- active overlays;
- current work frontier / active unit;
- last processed external-input frontier when applicable;
- completed units relevant to continuation;
- exact unfinished work;
- green/red/pending checks or evidence relevant to the current frontier;
- decisions genuinely requiring projectholder action;
- any overlay-specific state required by its owner document.

Do not manufacture a repository artifact merely to store a handoff unless that artifact
independently belongs in the project.

After handoff, autonomous continuous execution remains stopped until explicitly resumed.
