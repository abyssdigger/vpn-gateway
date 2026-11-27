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
- `RESEARCH.md` — research work;
- `COLLABORATIVE-EXECUTION.md` — multi-expert collaboration and coordination.

The loop is the lifecycle; overlays add semantics to the current work. Switching or adding an
overlay does not start a second clock and does not create a second authorization model.

Examples:

```text
loop + development
loop + development + ID
loop + research
loop + research + ID
loop + development + collaboration
loop + research + collaboration + ID
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
- an explicit `research loop` / continuous-research instruction -> loop + research overlay;
- explicit `COLLAB` / collaborative-cycle wording -> loop + collaboration overlay, with the
  work-mode overlay determined by the task.

The projectholder may explicitly compose overlays, for example an interactive research cycle.

Ordinary requests such as “check”, “research”, “review”, “test” or “try” do not start a
continuous loop merely because the task could benefit from one.

Loop or overlay activation never grants repository/GitHub authority. The only established
authorization shortcut remains explicit CD/CDC activation as defined by `AGENTS.md`; all other
loop modes use the ordinary authorization rules.

## 3. Activating and resuming a loop

Initial activation has a **pre-loop setup** phase. It is not yet active loop execution.

For a new continuous-execution cycle, before the loop becomes active:

1. choose `CYCLE_INTERVAL`: the user-specified interval, otherwise **30 minutes**;
2. obtain fresh real current time in UTC and record it as `CYCLE_START_TIME` with an explicit
   UTC offset (`Z` or `+00:00`);
3. read this document if it has not already been read unchanged in the active context;
4. apply the `AGENTS.md` reading gate and read the active overlay documents;
5. establish the initial work frontier and any external-input processed frontier;
6. preserve the authorization boundary exactly as established by `AGENTS.md`;
7. perform any overlay-defined **one-time pre-loop startup summary**; the generic loop itself
   defines no user-visible startup/progress report;
8. activate the loop and enter `EXEC_NEXT`.

If fresh real UTC time cannot be obtained, do not activate autonomous continuous execution.

The cycle clock starts before mandatory reading or preparation. Commit timestamps, local timezone
and inferred location are not substitutes for `CYCLE_START_TIME`.

A **RESUME/recovery** of an existing cycle is not a second activation and does not create a new
entry timestamp or startup report. Preserve the existing `CYCLE_START_TIME`,
`CYCLE_INTERVAL`, safety boundary, active overlays and authority boundary unless the
projectholder explicitly changed them. Reconstruct the current work/frontier state, obtain fresh
UTC only when needed as an ordinary clock/safety checkpoint, and return directly to
`EXEC_NEXT`.

The generic loop emits no user-visible entry, resume, heartbeat, waiting or liveness reports.
Such output is not part of loop state and is never required to prove that execution is alive.

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

While the loop is active, returning a terminal/final assistant response is itself an
**execution-ending lifecycle action**. It is permitted only through the `STOP -> PRE_FINAL_GATE`
path. A completed local unit, a clear frontier, an intermediate result, or the fact that the next
step is `WAIT` never makes a terminal response safe by itself.

## 5. WAIT semantics

`WAIT` is valid only when progress actually depends on external input/event and an active
interaction mechanism can materialize a bounded wait.

The interaction overlay may define watcher/frontier mechanics. At the generic level:

- ordinary timeout means the wait returned control; it is not semantic completion;
- recoverable wait/tool failure returns to `EXEC_NEXT` after bounded recovery;
- timeout or failure must not silently advance a processed semantic frontier;
- an overlay-local blocked/passivated/dormant marker describes work state only and is not by itself
  a `STOP` basis; when the loop is still active and an applicable bounded wait exists, return to
  `WAIT` and then `EXEC_NEXT` rather than ending the turn;
- do not use an unbounded wait that can bypass the session-safety boundary.

`WAIT` does not return control to the user and does not complete the active turn:

```text
WAIT != return-to-user
WAIT != turn completion
WAIT != STOP

WAIT = bounded in-turn suspension followed by EXEC_NEXT
```

The active loop itself does not emit progress/status/heartbeat reports. User-visible reporting is
not a `WAIT` primitive and must not be used as a liveness mechanism.

Scheduled tasks, reminders, automations, cron-like jobs and detached/background runs are outside
the loop lifecycle. Do not create or use them as wake-up, re-entry, continuation, liveness or
recovery machinery for an active loop. A separately authorized experiment may test such a
mechanism, but the experiment is outside normal loop semantics and must not be treated as proof of
same-turn continuation unless that property is actually demonstrated.

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

A new direct projectholder/user intervention on the **active conversational/source execution
surface** pauses autonomous continuous execution immediately.

An explicit instruction to resume, continue or return to the active loop (including an
established composite shorthand such as `continue CDC` or `return to COLLAB`) is a lifecycle
**RESUME** transition, not a bounded one-shot user operation.

If the same intervention also adds, changes or requests work, incorporate that work into the
active frontier. Perform the requested item as the first resumed `WORK` item when applicable,
then return to `EXEC_NEXT`. Completing that item does not create a `STOP` basis and does not
return control to the user.

After explicit RESUME, reconstruct the required state and return directly to `EXEC_NEXT`. Do not
emit an entry/resume/status acknowledgement as part of the loop lifecycle merely to announce that
execution resumed or that the first requested item completed. A final response remains permitted
only through `STOP -> PRE_FINAL_GATE`.

When the intervention does **not** explicitly resume the loop, handle it first and keep the prior
autonomous loop paused. A bounded operation explicitly requested by that intervention may be
performed while paused, but completing it does not silently resume the prior loop. Autonomous
continuous execution resumes only after a later explicit resume/continue instruction.

RESUME preserves the existing `CYCLE_START_TIME`, active overlays, work/frontier state and
authorization boundary unless the projectholder explicitly changes one of them. The original
`CYCLE_START_TIME` remains unchanged while paused as well.

A governing overlay may configure a **durable external projectholder collaboration lane** that is
not the active conversational/source execution surface. Input arriving there follows that
overlay's admission/routing semantics and does not pause the loop merely because the author is
the projectholder. Only an explicitly admitted stop/pause command (or other overlay-defined
equivalent) from that lane pauses/stops the loop automatically.

This exception must not be used to reinterpret ordinary free text as authority or to bypass
`AGENTS.md`; the overlay must keep product/project input, stop/control commands and execution
authority distinct.

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
6. perform the terminal-response liveness check: **if no final response were emitted now, does any
   permitted `WORK` or applicable bounded `WAIT` path still exist inside the current execution
   window and safety boundary?** If yes, `PRE_FINAL_GATE` fails and the agent must return to
   `EXEC_NEXT`.

If no permitted stop basis is true, `STOP` is invalid: return to `EXEC_NEXT` and choose
`WORK` or `WAIT`.

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
