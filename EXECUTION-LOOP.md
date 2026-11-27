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

## 3. Start and resume the loop

Follow this procedure exactly. Do not invent another exit path.

### START

1. Set `CYCLE_INTERVAL` to the user-specified interval; otherwise set it to **30 minutes**.
2. Obtain fresh real current time in UTC from the available current-time utility/source.
3. Set `CYCLE_START_TIME` to that observed time with an explicit UTC offset (`Z` or `+00:00`).
4. Read this document when it has not already been read unchanged in the current context.
5. Apply the `AGENTS.md` reading gate and read every active overlay document required by the task.
6. Establish the initial work frontier and every required external-input processed frontier.
7. Preserve the authority boundary exactly as established by `AGENTS.md`.
8. Do not reply anything in chat.
9. Enter `EXEC_NEXT`.

Do not convert the clock observation, setup work, branch state, role state, frontier state, or any
other startup fact into chat output.

If fresh real UTC time cannot be obtained, do not start autonomous continuous execution.

Start the cycle clock before mandatory reading or preparation. Do not use commit timestamps, local
timezone, inferred location, or another indirect time source as `CYCLE_START_TIME`.

### RESUME / RECOVERY

1. Preserve the existing `CYCLE_START_TIME`, `CYCLE_INTERVAL`, safety boundary, active overlays,
   work/frontier state, and authority boundary unless the projectholder explicitly changed one of
   them.
2. Reconstruct only the state required to continue.
3. Obtain fresh UTC only when an ordinary clock/safety checkpoint requires it.
4. Do not emit a startup, resume, status, progress, waiting, heartbeat, liveness, or recovery report
   in chat.
5. Do not reply anything in chat.
6. Return to `EXEC_NEXT`.

Maintain this compact control marker in active execution context:

```text
LOOP_STATE: WORK | WAIT | STOPPING
ACTIVE_OVERLAYS: <development/research/ID/...>
ACTIVE_UNIT: <current work frontier>
NEXT: <concrete next operation or awaited event>
PROCESSED_FRONTIER: <last processed external-input frontier, when applicable>
STOP_BASIS: <empty unless STOPPING>
```

Treat this marker as control state only. Do not treat it as a repository artifact or authorization
source.

## 4. Execute the loop

After every bounded local operation that returns execution control, run `EXEC_NEXT` before doing
anything else.

Treat each of the following as a bounded local operation:

- a tool/read/write batch;
- a mutation/publication and its verification;
- a validation/test/review result;
- one analysis/design/research/implementation step;
- completion of an overlay-specific unit/block;
- return from a bounded external-event wait.

### EXEC_NEXT

1. Do not reply anything in chat.
2. Check the session-safety boundary.
3. If the safety boundary requires stopping, set the exact safety stop basis and go to
   `PRE_FINAL_GATE`.
4. Check for a concrete, sufficiently defined, authorized, and safe `WORK` operation.
5. If such `WORK` exists, go to `WORK`.
6. Check for an applicable bounded `WAIT` mechanism that can observe the unresolved dependency
   inside the remaining execution window.
7. If such `WAIT` exists, go to `WAIT`.
8. Identify one exact currently true generic or overlay-specific `STOP` basis.
9. If no exact `STOP` basis exists, clear `STOP_BASIS`.
10. If no exact `STOP` basis exists, do not reply anything in chat.
11. If no exact `STOP` basis exists, return to `EXEC_NEXT`.
12. If an exact `STOP` basis exists, store it in `STOP_BASIS`.
13. If an exact `STOP` basis exists, go to `PRE_FINAL_GATE`.

Do not treat completion of a local operation, completion of one work unit, receipt of one peer
response, exhaustion of the originally mentioned subsystem, refusal of one unauthorized mutation,
or expiration of one bounded wait as a `STOP` basis.

### WORK

1. Do not reply anything in chat.
2. Execute exactly one bounded permitted work operation.
3. Record only the internal or durable process state required by the active governing documents.
4. Do not report completion, progress, status, findings, branch state, peer state, next steps, or
   waiting state in chat.
5. Do not reply anything in chat.
6. Return to `EXEC_NEXT`.

### WAIT

1. Do not reply anything in chat.
2. Use one applicable bounded wait mechanism.
3. When the wait returns, preserve the real semantic frontier.
4. Do not treat timeout, silence, a blocked marker, a passivation marker, `DORMANT`, or a missing
   peer response as completion or as a `STOP` basis.
5. Do not treat failure of one preferred wait implementation as proof that no other applicable
   bounded wait exists.
6. Evaluate every other applicable bounded wait mechanism before considering `STOP`.
7. Do not reply anything in chat.
8. Return to `EXEC_NEXT`.

Do not use an unbounded wait that can bypass the session-safety boundary.

Do not use scheduled tasks, reminders, automations, cron-like jobs, or detached/background runs as
wake-up, continuation, liveness, or recovery machinery for this loop. Treat a separately authorized
experiment with such a mechanism as outside normal loop semantics.

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

## 7. Handle user intervention and resume

When a new direct projectholder/user intervention arrives on the active conversational/source
execution surface:

1. Pause autonomous continuous execution immediately.
2. Classify the intervention.
3. If the intervention explicitly resumes, continues, or returns to the loop, preserve the existing
   `CYCLE_START_TIME`, active overlays, work/frontier state, and authority boundary unless the
   intervention explicitly changes one of them.
4. If the same intervention adds, changes, or requests work, place that work at the front of the
   resumed work frontier when applicable.
5. Perform the requested bounded work through the normal `WORK` procedure.
6. Do not treat completion of that requested work as a `STOP` basis.
7. Do not emit an entry, resume, status, completion, progress, or next-step acknowledgement in chat.
8. Do not reply anything in chat.
9. Return to `EXEC_NEXT`.

When the intervention does not explicitly resume the loop:

1. Handle only the bounded operation explicitly requested by that intervention.
2. Keep autonomous continuous execution paused.
3. Do not silently resume the prior loop after completing the bounded operation.
4. Resume autonomous continuous execution only after a later explicit resume/continue instruction.

When an active overlay configures a durable external projectholder collaboration lane:

1. Apply that overlay's exact admission and routing rules.
2. Do not pause the loop merely because ordinary projectholder input arrives through that external
   lane.
3. Pause or stop only when an explicitly admitted stop/pause command or another exact overlay-defined
   control condition requires it.
4. Keep product/project input, control commands, and execution authority separate.
5. Do not reinterpret ordinary free text as authority.

Treat peer/agent input in an admitted collaboration lane as work input only. Do not treat it as
direct projectholder intervention or execution-authority expansion.

## 8. Stop and finalization

Use only the following generic `STOP` bases:

- a required human decision blocks all meaningful permitted continuation;
- an external blocker prevents all meaningful permitted continuation;
- no sufficiently defined unblocked work remains across the active overlays;
- an active overlay or owning process document defines an exact stop condition that is currently
  true;
- the session-safety boundary has been reached;
- a direct user intervention paused the loop and no bounded requested operation remains.

For the first three bases, require all of the following before accepting `STOP`:

1. Verify that no meaningful permitted `WORK` remains.
2. Verify that no applicable bounded `WAIT` remains inside the execution window.
3. Do not convert repeated wait timeout or exhaustion of independent work into a terminal blocker.

### PRE_FINAL_GATE

Run this procedure before every cycle-ending chat response:

1. Do not reply anything in chat.
2. Name one exact currently true generic or overlay-specific `STOP` basis.
3. Verify that basis against current observable facts.
4. Verify that no safer permitted `WORK` transition remains.
5. Verify that no required/applicable bounded `WAIT` transition remains.
6. Perform every active-overlay final check.
7. Perform every required external-lane final read.
8. Prepare the truthful handoff/conclusion required by the exact stop basis.
9. Ask: if no final response were emitted now, would any permitted `WORK` or applicable bounded
   `WAIT` path still exist inside the execution window and safety boundary?
10. If the answer is yes, fail `PRE_FINAL_GATE`.
11. If no exact `STOP` basis is currently true, fail `PRE_FINAL_GATE`.
12. If `PRE_FINAL_GATE` fails, clear `STOP_BASIS`.
13. If `PRE_FINAL_GATE` fails, do not reply anything in chat.
14. If `PRE_FINAL_GATE` fails, return to `EXEC_NEXT`.
15. If `PRE_FINAL_GATE` passes, go to `FINAL`.

### FINAL

1. Report the cycle results briefly and structurally in chat.
2. Do not use images.
3. Do not use tables.
4. End the cycle.

Do not create another chat-output path for the cycle.

### 8.1. Projectholder decision request contract

When a genuine projectholder product/project decision is required, the request is a semantic
decision payload, not a pointer to prior conversation. It must be self-contained for a
projectholder who knows the project but has not read the current agent/peer/task-room transcript.

The request must contain:

1. **Essence** — the concrete residual question, why it matters now and which dependent scope
   cannot proceed without the decision.
2. **Normative basis** — the exact Requirements, Constraints, accepted decisions and material
   facts from which the question arises, plus why the applicable real-ambiguity filtering still
   leaves more than one permissible outcome.
3. **Surviving options and consequences** — for every genuinely permissible option, the
   observable/product effect, material advantages, disadvantages, risks/costs/constraints and
   the accepted obligations it affects.
4. **Exact decision requested** — the minimum additional product/project choice or external
   basis needed to continue.

References to Issues, task rooms, reviews, artifacts or prior messages may provide evidence and
detail, but must not replace any required item above. A request such as "choose A/B; context is
in room/thread X" is insufficient.

Use the same self-contained payload whether the decision is delivered through the active
conversation, a projectholder room, an Issue, a handoff or another admitted transport.

If normative filtering leaves only one permissible outcome, do not manufacture a holder choice;
continue at the owning design/implementation layer within existing authority. Setup/entitlement
actions and execution-authority expansion are separate holder actions: request their exact
minimal action and do not disguise them as product alternatives.

## 9. Recovery

Recovery is **reactive** to an actual execution/context loss; it is not a normal continuation
mechanism and is never pre-scheduled merely to keep a loop alive.

Do not infer a platform limitation from one recoverable wait/tool failure.

- recoverable/transient failure inside the active turn -> bounded recovery, then `EXEC_NEXT`;
- confirmed unrecoverable failure preventing meaningful continuation -> external-blocker stop
  basis may apply;
- actual context/turn loss -> on a later explicit resume, replay durable state, reconstruct the
  control marker and processed frontier before dependent work.

A scheduled task/reminder/automation is not recovery of the same active turn and cannot establish
that the loop remained live.

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
- decisions genuinely requiring projectholder action, expressed under §8.1 when a product/project decision is required;
- any overlay-specific state required by its owner document.

Do not manufacture a repository artifact merely to store a handoff unless that artifact
independently belongs in the project.

After handoff, autonomous continuous execution remains stopped until explicitly resumed.
