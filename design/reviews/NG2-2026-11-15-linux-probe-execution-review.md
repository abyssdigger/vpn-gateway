# NG2 autonomous review — Linux probe execution Agent

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-linux-probe-transport-40m`  
**Base:** `e24a3640fe6b406a16dbc475dda9a7c50711d909`  
**Scope:** concrete production execution of `ProbeExecutionPlan` through the proven Linux ICMP mechanism

## Scope

Reviewed the complete execution slice:

```text
AvailabilityProbeManager
    |
    +-- ProbeExecutionPlan | None
            |
            v
    LinuxProbeExecutionAgent
            |
            +-- ProbeSendDriver
            |       |
            |       +-- LinuxDiagnosticPingSendAdapter
            |               |
            |               +-- LinuxIcmpProbeDriver
            |
            +-- ProbeGoodNewsInfo
            +-- ProbeWindowBoundaryInfo
            +-- ProbeExecutionDiagnosticInfo
```

The review specifically checked:

- accidental restoration of semantic attempts or production `NO_REPLY`;
- Manager/Agent/Driver/Adapter responsibility boundaries;
- physical generation and logical evidence-generation races;
- scheduler phase correctness;
- suspend/resume behavior;
- resource bounds;
- stale worker completion;
- diagnostic lifecycle;
- hidden timing policy;
- contradictions with the persistent-route availability model;
- unnecessary new kernel mechanism or target evidence claims;
- Rust-aligned ownership/data flow.

## Findings

### F1 — production Agent initially depended on historical attempt result semantics

**Status:** accepted and fixed.

The first draft let the Agent consume the existing diagnostic:

```text
ProbeAttemptResult(REPLY | NO_REPLY | ERROR)
```

directly. Even if `NO_REPLY` were ignored later, this would make the rejected attempt
contract a production dependency.

Added the narrow production boundary:

```text
ProbeSendDriver.execute_send(...)
    -> ProbeSendResult(
           good_news: bool,
           local_error: str | None
       )
```

`LinuxDiagnosticPingSendAdapter` now hides the historical single-shot Driver:

```text
REPLY    -> good_news
NO_REPLY -> absence of good news
ERROR    -> local execution diagnostic
```

No production `NO_REPLY` type crosses the Adapter.

### F2 — execution demand had no event lifecycle

**Status:** accepted and fixed.

Polling `AvailabilityProbeManager.execution_plan` would not match the project event model
and would make quiesce timing ambiguous.

The Manager now publishes latest-value:

```text
ProbeExecutionPlan | None
```

as RequestEvent intent.

Physical READY-generation invalidation publishes `None` before the subsequent lower-domain
transition. A later fresh READY generation publishes a replacement plan.

Equivalent plans are suppressed.

### F3 — delayed scheduler could create catch-up storms

**Status:** accepted and fixed.

A naive scheduler could replay every elapsed logical boundary and every missed physical send
after suspend/resume.

Current behavior:

- elapsed logical windows are represented by one
  `ProbeWindowBoundaryInfo(elapsed_intervals=N)`;
- the evidence integral is applied in O(1);
- exactly one current physical send is launched;
- historical missed sends are not replayed;
- both send and boundary deadlines advance in O(1).

This preserves elapsed-time semantics without an event/process burst.

### F4 — physical sends could overlap without a bound

**Status:** accepted and fixed.

If technical send duration exceeds the configured cadence, spawning a new thread/process at
each deadline would permit unbounded growth.

The Agent now allows at most one in-flight send per physical plane and
`ProbeObservationGeneration`.

At an overrun deadline:

- no second worker is started;
- local execution state becomes ERROR;
- observation-window cadence continues;
- no immediate negative routing event is produced.

### F5 — good-news and boundary facts lacked one source order

**Status:** accepted and fixed.

Good-news originates on worker threads while boundaries originate on the scheduler thread.
Without source serialization, their publication order could be indeterminate at a shared
time boundary.

The Agent now serializes good-news and window-boundary publications through one event
publication lock.

This establishes source order. It does **not** replace the separate EventEnvelope
epoch/revision delivery gate.

### F6 — local execution diagnostics were not generation-complete

**Status:** accepted and fixed.

READY/ERROR alone could leave an old ERROR looking current after the corresponding
generation or plane disappeared.

Diagnostics are now current projections:

```text
READY
ERROR
INACTIVE
```

and are keyed by full `ProbeObservationGeneration + PhysicalProbePlane`.

When a diagnostic subject leaves the current plan, INACTIVE is published.

### F7 — stale worker diagnostic could race plan invalidation

**Status:** accepted and fixed.

A worker could pass a current-plan check and then publish READY/ERROR after a concurrent
plan change had already emitted INACTIVE.

Diagnostic validation/cache commit and plan invalidation are now ordered so that:

- a worker cannot commit a stale current diagnostic after invalidation;
- if the diagnostic was committed first, subsequent invalidation emits INACTIVE after it.

Regression coverage includes old-generation worker completion after plan replacement.

### F8 — logical policy reset was not reflected in execution window phase

**Status:** accepted and fixed.

A `failure_intervals`-only change resets the Manager's evidence state but does not change
physical rules or the observation interval. The initial execution plan was therefore equal
to the old plan and the Agent could retain a partially elapsed old logical window.

Added Manager-owned opaque:

```text
LogicalProbeWindow.evidence_epoch
```

The epoch changes whenever that logical probe definition changes. It is not routing or
execution policy and does not expose `failure_intervals` below the Manager.

The scheduler preserves a logical window phase only when both interval and
`evidence_epoch` are unchanged.

### F9 — an already-emitted old logical boundary could cross a same-generation policy reset

**Status:** accepted and fixed.

Even with F8 fixed, a boundary could have already left the scheduler before a logical
policy change and arrive after the new evidence state was installed. Physical
`ProbeObservationGeneration` would still match.

`ProbeWindowBoundaryInfo` now carries the opaque logical `evidence_epoch`.
`AvailabilityProbeManager` rejects a boundary unless both:

- physical READY generation matches;
- logical evidence epoch matches.

Good-news intentionally does **not** carry logical evidence epoch: valid replies are
arrival-based positive evidence for the current physical plane, independent of which send
caused them.

### F10 — technical timeout had an implicit default

**Status:** accepted and fixed.

A constructor default of one second risked looking like hidden availability verdict policy.

`LinuxProbeExecutionAgent` now requires an explicit positive technical
`timeout_seconds` value from runtime assembly. The timeout bounds technical process
execution only; it does not generate a routing verdict.

### F11 — minor public-contract validation was weaker than the type model

**Status:** accepted and fixed.

Tightened:

- `ProbeSendResult.local_error` must be a non-empty string when present;
- schedule time must be finite numeric and not bool;
- schedule plan must be `ProbeExecutionPlan | None`;
- Agent clock must be callable;
- diagnostic validation wording covers both READY and INACTIVE.

### F12 — new raw/ping-socket implementation would add evidence risk without a requirement

**Status:** rejected as unnecessary complexity.

The existing capability-free `LinuxIcmpProbeDriver` is already validated on Debian 13 and
fits the selective LOCAL_PROCESS network plane.

The production implementation therefore keeps the long-lived lifecycle in the Agent and
uses bounded single-shot ping workers underneath the compatibility Adapter.

This introduces no new claimed Linux socket/kernel behavior and does not require a new
target experiment for this review unit.

A new transport mechanism remains possible later if a concrete requirement justifies it.

## Component-model review

The resulting split is consistent with `design/component-model.md`:

```text
AvailabilityProbeManager        # Manager
    owns desired probe plane + evidence/hysteresis

ProbeExecutionPlanCalculator    # Calculator
    derives execution demand

LinuxProbeExecutionAgent        # Agent
    observes remote reachability through active sends

ProbeSendDriver                 # Driver contract
    technical send operation

LinuxDiagnosticPingSendAdapter  # Adapter
    hides historical attempt-shaped Driver contract

LinuxIcmpProbeDriver            # existing Linux Driver
    proven process/kernel mechanics

LinuxCommandRunner              # Runner below Driver
```

No second availability Manager, attempt scheduler, retry policy, recovery threshold,
per-flow routing state or route-membership actuator was introduced.

## Safety / architecture consistency

Confirmed:

1. probing never adds or removes payload routes;
2. sole/last path has no special probing deletion rule;
3. no production `NO_REPLY` event exists;
4. local execution ERROR does not directly change routing;
5. good-news remains positive arrival evidence;
6. negative evidence remains only elapsed logical windows without good news;
7. physical generation and logical evidence epoch are independently validated;
8. one physical plane has bounded concurrent send work;
9. stale generation/plane worker results cannot become current evidence;
10. diagnostics cannot survive silently past subject invalidation.

## Test coverage

Deterministic regression coverage added for:

- immediate first send;
- boundary-before-next-send phase ordering;
- unchanged vs changed cadence phase behavior;
- physical generation restart;
- logical evidence-epoch restart;
- delayed boundary batching;
- no send catch-up burst;
- REPLY/NO_REPLY/ERROR compatibility mapping below production boundary;
- no production negative event from NO_REPLY;
- local-error diagnostics and recovery;
- one in-flight send per physical plane;
- unexpected Driver exceptions;
- diagnostic READY/ERROR/INACTIVE lifecycle;
- stale worker completion;
- execution-plan RequestEvent publication/quiesce/replacement;
- threshold-only logical policy reset;
- stale logical-boundary rejection;
- rootless Manager -> Agent -> Manager good-news/window round trip.

## CI / evidence

A temporary draft PR is used only to expose the repository's pull-request-triggered
`NG2 Python` workflow for this code-cycle branch. It will be closed without merge after
the final result is recorded.

At the time this review document is first written, the latest workflow result is still
pending. The final verdict below must not be changed to PASS until that run completes
successfully or an equivalent stronger test result is obtained.

No new target-specific kernel property is claimed by this unit.

## Remaining gates

Not part of this review unit:

1. Event Delivery Environment / EventEnvelope epoch+revision implementation;
2. daemon/runtime assembly that instantiates the Agent and connects real event transport;
3. Profile/status consumption of execution diagnostics;
4. serialization/schema lifecycle;
5. target validation only if a future send mechanism materially differs from the already
   validated capability-free ping path.

## Verdict

**PENDING CI.**

The architecture/code review has no unresolved finding. Final review-unit acceptance waits
only for the observable NG2 Python workflow result.
