# VPN-GATE NG2 — HANDOFF

**Date:** 2026-11-15  
**Repository:** `abyssdigger/vpn-gateway`  
**Working branch:** `code-cycle-20261115-publisher-failure-recovery-40m`  
**HEAD:** `2695591b5207f831022d802d1f3eabdbbffa4321`

This is delta-context only. Read current code, active NG2 design docs, reviews and CI from
this HEAD before changing anything.

## 1. Current working state

Current branch:

```text
code-cycle-20261115-publisher-failure-recovery-40m
```

Current HEAD:

```text
2695591b5207f831022d802d1f3eabdbbffa4321
Record NG2 process-local failure hardening
```

Temporary draft PR **#21** is still open and exists only as a PR-triggered CI gate. Do not
merge it. Close it after the current cycle is formally checkpointed.

There is **no cycle checkpoint file yet** for this cycle. The code/reviews are materially
complete, but the 40-minute cycle was interrupted before the formal checkpoint/PR-close
sequence.

## 2. Current cycle and original task

Cycle:

```text
NG2 publisher failure recovery
CYCLE_INTERVAL=40m
base=9c3b9af38861804519a6313028a215e7f3fd49c4
```

Initial purpose:

1. recover the interrupted ProbeExecutionAgent publisher-failure work;
2. fix the one failing retry regression without weakening production semantics;
3. rerun full automated evidence;
4. review adjacent process-local publication/lifecycle boundaries;
5. continue autonomously only with tightly related, non-interactive review units.

The cycle evolved into focused **process-local failure/retry/lifecycle hardening** around
ProbeExecutionAgent, AvailabilityProbeManager, PayloadTrafficManager publication behavior,
and LinuxNetworkPolicyRuntime multi-owner failure reporting.

## 3. What is already done in this cycle

### ProbeExecutionAgent publisher failure isolation

Current semantics:

- `AvailabilityTick` subscriber exception is logged and does not abort remaining due
  physical sends;
- one failing `AvailabilityGoodNews` subscriber does not block fanout to other current
  logical consumers of the same physical plane;
- diagnostic publisher exception does not suppress good-news fanout;
- failed READY/ERROR diagnostic publication is removed from duplicate-suppression cache so
  the same semantic diagnostic can be published later;
- failed INACTIVE diagnostic publication is logged but is not persisted in a delivery
  queue;
- no reliable event bus/revision/replay machinery was added.

A broad scheduler-loop `except Exception` was explicitly removed. Known adjacent callback
failures are isolated at their exact boundary; unexpected Agent implementation failures
must remain visible.

### ProbeExecutionAgent scheduler-thread lifecycle

Fixed:

- synchronous `Thread.start()` failure no longer leaves stale `_running=True`;
- scheduler thread `finally` clears current running/thread identity if that thread exits
  unexpectedly;
- unexpected scheduler exception remains visible through normal Python thread exception
  handling;
- later explicit `start()` can retry;
- no automatic restart policy was introduced.

### AvailabilityProbeManager plan publication / quiesce retry

Current invariants:

- changed execution plan is recorded as published only after publisher returns;
- failed execution-plan publication is retryable by later equivalent Manager operation;
- shutdown always attempts probe-owned NetworkRules cleanup even if quiesce publication
  `None` raises;
- failed quiesce is not considered delivered;
- if the last successfully published plan is still non-None, later
  shutdown/invalidation retries `None` even after physical generation was already cleared;
- physical target replacement cannot open/publish the new physical generation until a
  previously failed quiesce of the old published plan succeeds.

This is implemented via the unresolved **last successfully published plan** invariant,
not a logical epoch/revision queue.

### PayloadTrafficManager state publication retry

Verified by regression, no production change needed:

- state publisher exception remains visible to caller;
- serialized reconcile executor is released correctly;
- failed state publication is not recorded as successful;
- later `audit()` can publish the same semantic state;
- already MATCHED NetworkRules are not rematerialized merely to retry state publication.

### LinuxNetworkPolicyRuntime independent-owner errors

Current behavior:

- probe and payload Managers are distinct owner scopes on the same owner-composing
  NetworkRulesAdapter;
- `audit()` attempts both owners independently;
- `stop()` attempts both cleanups independently;
- if both owners throw unexpected exceptions, `ExceptionGroup` preserves both;
- if one owner throws and the other returns `ActionResult(False, diagnostic)`, the
  ordinary failure diagnostic is attached as an exception note so it is not lost;
- ordinary dual `ActionResult(False)` remains ordinary return data, not exceptions.

### Documentation/reviews written

Read first:

- `design/reviews/NG2-2026-11-15-probe-agent-publisher-failure-review.md`
- `design/reviews/NG2-2026-11-15-process-local-publication-failure-review.md`
- `design/NG2/probe-execution-agent.md`
- `design/NG2/availability-probe-manager.md`

The process-local review contains later findings F7-F9 and final evidence appended after
its original PASS section.

## 4. What is still in process / not formally complete

The code/review work of this cycle is effectively complete, but the cycle itself is not
formally closed.

Still required:

1. create the normal 40m cycle checkpoint review file;
2. update that checkpoint with final HEAD/evidence;
3. close temporary draft PR #21 without merge;
4. do not claim the cycle complete until those bookkeeping steps are done.

Also verify whether a final CI run exists directly on current HEAD
`2695591b5207f831022d802d1f3eabdbbffa4321`. The last code-changing head before final
doc/review commits was green; the current HEAD includes only review/changelog material on
top of the tested code.

## 5. Open architecture / semantic questions

These are deliberately **not yet implemented** because upstream semantics are not fixed
enough:

### Structural runtime projection

Python reference still lacks the authoritative upstream
config/selection/binding model needed to derive:

```text
PayloadTrafficStateRequest
```

Do not invent a new general config schema merely to claim a complete RuntimeStateManager.

### Final status / ProfileState aggregation

Still open:

- final RuntimeStateManager/ProfileState model;
- how probe execution diagnostics participate in status;
- exact status aggregation semantics above the already-existing Manager state outputs.

Do not feed probe diagnostics back into route priority.

### Audit / retry cadence policy

Deterministic `audit()` passes exist.

What is **not** fixed:

- periodic audit interval;
- timer ownership;
- retry cadence/backoff policy.

Repository search found no normative cadence. Do not invent a scheduler component or
timer policy until this is decided.

### Production asynchronous Event Delivery

Only streams that genuinely require asynchronous replay/order should use it.

Availability path does **not** require EventEnvelope/revision/epoch/replay.

## 6. Recent decisions that may not be obvious from code alone

### Availability is an optional negative priority modifier

Normative meaning:

```text
availability_problems: bool
```

Initial state:

```text
false
```

If availability probing is disabled, there are no availability problems by definition.

Availability does not establish basic runtime viability and does not sink merely
unconfirmed channels at startup.

Startup order with probing must equal configured ranking without probing.

### No GOOD/BAD domain vocabulary

GOOD/BAD were only conversational shorthand.

The persistent domain concept is:

```text
availability_problems = yes | no
```

Do not reintroduce GOOD/BAD/UNCONFIRMED as public/runtime domain states unless a new
requirement genuinely needs them.

### Availability acts only on priority, never membership

Availability must never:

- add/remove a payload path;
- change binding eligibility;
- remove a route because a probe is bad;
- rewrite structural PayloadTrafficStateRequest.

It may only alter effective order / lower preferred-prefix materialization.

### All-clear availability is a real no-op

When zero paths have availability problems:

- effective order is configured order;
- `preferred_prefix_length=None`;
- enabling availability alone does not rematerialize payload NetworkRules.

The lower preferred-prefix hint exists only when there is an actual problem tail.

### Pings are colorless

Producer input per channel is bounded aggregate state:

```text
pending_good_news: 0..recovery_good_news
tick_pending: bool
```

Good news saturates at the recovery threshold.

Multiple undrained ticks collapse to one boolean fact.

There is no ping queue, tick queue, elapsed tick count or attempt-event journal.

### Same-pass asymmetry

Normative transition rules:

- `availability_problems=false -> true` only on tick;
- `availability_problems=true -> false` only on good news;
- tick never improves;
- good news never worsens;
- transition decision is based on state at entry to collector pass;
- a transition caused by one input kind is not immediately subjected to the opposite
  transition rule in the same pass.

Delayed replies count. If recovery threshold is 3, three delayed successful replies that
arrive together can clear the problem state in one pass.

### Policy-only changes

Current accepted behavior:

- preserve current `availability_problems` value / route class;
- reset hysteresis progress;
- clear pending input for that channel;
- do not restart probe tick cadence if only hysteresis thresholds change.

Probe cadence is separate from payload hysteresis.

## 7. Non-obvious architecture boundaries / invariants

### Manager / Agent / Machinery roles

Current component model is normative:

- Manager: Engine that observes + controls its managed domain;
- Agent: observe-only Engine facade;
- Calculator / Adapter / Executor / Driver: Machinery semantic roles;
- Runner: low-level execution/transport primitive below semantic Machinery, not a peer
  semantic role.

Do not classify by whether a class performs I/O. Classify by semantic responsibility.

### Runner vs Driver

Runner:

```text
raw invocation -> raw transport/execution result
```

Driver:

```text
meaningful technical operation over a concrete mechanism
```

Executor owns convergence to a caller-selected desired state/postcondition.

Manager should normally depend on semantic Machinery, not raw Runner.

### Synchronous dependency graph must remain a DAG

Event feedback cycles are allowed.

Synchronous Manager/Adapter back-edges are not.

The current availability shape deliberately avoids one Manager calling another Manager's
private Machinery.

### Payload owns availability hysteresis

`PayloadTrafficManager` owns:

- current `availability_problems`;
- failure/recovery hysteresis progress;
- bounded good-news/tick ingress;
- current effective route order;
- the sole transactional payload route-priority materializer.

`AvailabilityProbeManager` owns:

- physical ProbeRules/readiness;
- physical observation generation;
- current execution demand/plan.

`ProbeExecutionAgent` owns:

- physical send cadence;
- logical tick cadence;
- bounded send workers;
- stale physical generation rejection;
- local execution diagnostics.

### Physical generation remains justified

Do **not** delete `ProbeObservationGeneration`.

It exists narrowly because an old bounded physical worker may finish after a physical
ProbeRules/interface generation replacement.

It must not become a logical evidence epoch.

### Payload/probe contract separation

Payload-facing availability channel contains only:

```text
channel_id
path
enabled
failure_ticks
recovery_good_news
```

It contains no:

- target;
- mechanism;
- cadence;
- physical generation;
- attempt identity;
- timestamp.

`PayloadTrafficManager` must not import/store physical probe request/transport types.

### One shared Adapter, distinct owner identities

`LinuxNetworkPolicyRuntime` may use one owner-composing `NetworkRulesAdapter` instance
for PayloadTrafficManager and AvailabilityProbeManager.

The Managers remain distinct owners because each passes its own `self`.

Do not merge them into one global desired NetworkRules state above the Adapter.

## 8. Route priority / metric empty-slot transaction model

Availability-driven ordering uses the same sole transactional payload route executor as
all other payload route mutations.

There must not be a second availability route-move executor/queue.

For N eligible routes, lower routing has N+1 ordinary metric slots below
`BLACKHOLE_METRIC=65536`.

The free metric slot is **emergent**, not configured/stored as an object.

Important:

- all clear: no preferred-prefix boundary, no steady gap;
- problem tail exists: lower layer derives the free slot immediately before first problem
  route;
- all problem: current relative order is retained and first ordinary metric slot is free.

Move semantics are make-before-break:

```text
add route at new metric
verify/continue transaction
delete old metric instance
```

The route sorter/materializer is the **sole transactional executor per Profile/routing
scope**.

A new death/recovery input must not interleave another kernel route transaction. Inputs may
accumulate in bounded Manager ingress while the current synchronous materialization runs.

The baseline for planning is the **last verified successfully materialized projection**.
If a partial transaction fails, do not advance the baseline; re-observe authoritative
route state before planning further moves.

Do not add route deletion for availability problems.

## 9. Probe transport / execution current model

Physical sends may be deduplicated for logical channels sharing one physical plane.

Physical plane identity is based on mechanism/path/target.

Logical channels may have different:

- tick cadence;
- hysteresis thresholds.

Physical send cadence may use the fastest required cadence among shared logical consumers.

A valid physical reply fans out one good-news unit to each current logical consumer.

Missed physical sends are not burst-replayed.

Logical ticks are current timer facts; multiple undrained ticks collapse at payload input.

No logical windows, evidence epochs, elapsed interval catch-up or source-order publication
lock should return.

## 10. Publisher failure semantics

This is the main delta from the latest cycle.

### Agent-originated fanout

Because the Agent has long-lived scheduler/workers and may fan out to multiple consumers:

- adjacent publisher failures are isolated locally and logged;
- one consumer must not destroy scheduler/worker/sibling delivery;
- no reliable replay queue is added.

### Manager-originated synchronous publication

Manager publisher exceptions are synchronous call failures:

- remain visible;
- successful publication baseline advances only after publisher returns;
- later Manager operation/audit may retry.

Do not silently swallow Manager publication exceptions.

### Unexpected internal exceptions

Do not catch them broadly just to keep loops alive.

Known callback failures are isolated where they occur; unknown Agent implementation
failures remain visible.

## 11. Testing / CI state

Latest cycle review file records final evidence:

```text
final tested code head: 95427ba2aab64bd99dd46326991bc66104fef549
NG2 Python run 749
315 rootless unit tests PASS
full privileged Linux matrix PASS
```

The following privileged gates are green:

- selective probe-process isolation;
- EXP-025 stale probe conntrack generation;
- EXP-026 probe-class conntrack cleanup;
- EXP-027 route-priority transition;
- nft ICMP selector;
- Linux instance lifecycle;
- Linux Adapter;
- Linux LOCAL_PROCESS;
- Linux dataplane.

No new target/kernel experiment was required by the latest cycle.

Current branch HEAD `2695591b...` is review/changelog material on top of that tested code
and should be checked for an associated final workflow run before formal checkpoint.

Historical kernel behavior already proven by EXP-025/026/027 should not be re-experimented
without a changed kernel claim.

## 12. Planned next review/development units

Order should remain conservative.

### First: formally close the current cycle

Why first: code/reviews are done but cycle bookkeeping is not.

- verify final HEAD CI;
- create cycle checkpoint;
- close draft PR #21 without merge.

### Second: structural payload runtime projection

Only proceed if the existing repo now exposes a sufficiently authoritative upstream
config/selection/binding contract.

Goal:

```text
current structural runtime/config/binding facts
    -> PayloadTrafficStateRequest
```

Do not make availability part of this Request.

If upstream semantics are still absent, stop this unit rather than inventing them.

### Third: status/ProfileState model

Define the minimum current-state aggregation above existing Manager outputs.

Probe execution diagnostics may feed status/diagnostics, but must not feed availability
routing priority.

### Fourth: audit/retry cadence

Only after timer ownership/cadence policy is explicit.

Do not create an Agent/Runner solely because “something needs a timer.”

### Fifth: async Event Delivery

Only for streams with a proven need for asynchronous ordering/replay.

Availability does not need it.

## 13. Interactive vs autonomous work

### Autonomous now

Safe without user/stand interaction:

- formal current-cycle checkpoint + PR close;
- static/review cleanup;
- deterministic unit tests;
- existing privileged CI matrix;
- code/doc consistency review;
- structural projection implementation **only if** required upstream contracts are already
  explicit in repo;
- status model analysis that does not choose new user-visible semantics.

### Needs user semantic decision

Escalate before changing:

- user-visible config/schema;
- exact Profile/status semantics where multiple reasonable meanings exist;
- audit/retry cadence policy if it affects behavior;
- materially different architecture alternatives;
- destructive migrations;
- scope/prioritization trade-offs.

### Needs external/target stand

Only if a new claim is not covered by current deterministic/privileged evidence, especially:

- new kernel route/conntrack/nft semantics;
- target-specific behavior;
- lifecycle behavior unavailable in existing privileged namespace CI.

Do not run new experiments for already-proven EXP-025/026/027 claims.

## 14. What not to revisit

Do not reintroduce or re-research unless a new requirement invalidates the decision:

- GOOD/BAD/UNCONFIRMED availability state model;
- observation windows;
- evidence epochs/revisions for availability;
- elapsed interval catch-up;
- ping/tick event queues;
- AvailabilityProbeStateInfo as routing-control intermediate;
- PayloadTrafficIntentCalculator availability mediation;
- probing fields inside PayloadTrafficStateRequest;
- physical target/mechanism/cadence inside PayloadTrafficManager;
- separate availability route executor;
- configured/stored metric-hole object;
- availability-based route deletion;
- broad scheduler exception swallowing;
- reliable publisher replay/event bus for current process-local Agent callbacks;
- generic audit timer policy without an agreed cadence.

## 15. Known code/docs/review divergences

### Current-cycle checkpoint missing

The current branch has cycle/review files but no:

```text
design/reviews/NG2-2026-11-15-publisher-failure-recovery-40m-checkpoint.md
```

Create it before declaring cycle closed.

### Temporary PR still open

Draft PR #21 is a CI gate only and is still open. Close without merge after checkpoint.

### Review evidence vs branch HEAD

`design/reviews/NG2-2026-11-15-process-local-publication-failure-review.md` records final
tested code head `95427ba2...` / run 749 / 315 tests.

Branch HEAD `2695591b...` is later and contains review/changelog updates. Verify/record
whether a final workflow run exists for current HEAD when checkpointing.

### Review structure

The process-local review originally ended after F6 and later had F7-F9 + final evidence
appended. Content is valid, but a future doc-cleanup pass may renumber/restructure it for
presentation. Do not treat that formatting issue as an architecture problem.

---

# START HERE

1. Checkout/read branch `code-cycle-20261115-publisher-failure-recovery-40m` at
   `2695591b5207f831022d802d1f3eabdbbffa4321`.
2. Open first:
   `process-local-publication-failure-review.md`,
   `probe-agent-publisher-failure-review.md`,
   `linux_probe_execution.py`,
   `availability_probe_manager.py`,
   `runtime_assembly.py`.
3. Verify CI associated with current HEAD; last explicitly recorded tested code head is
   `95427ba2...`, run 749, 315 unit PASS + full privileged matrix.
4. Create the missing current-cycle checkpoint file with final evidence.
5. Close temporary draft PR #21 without merge.
6. Do not reopen availability/event-window/evidence-epoch design; that work is closed.
7. Do not invent structural config/binding or audit timer policy if upstream semantics are
   still absent.
8. Next real development unit is structural runtime projection
   `current structural facts -> PayloadTrafficStateRequest`, but only if its input model is
   already authoritative in repo.
9. Any new route/metric work must continue through the sole transactional payload route
   materializer with last-verified baseline and emergent empty-slot semantics.
10. Current cycle is complete only when final HEAD evidence is recorded, checkpoint exists,
    and PR #21 is closed without merge.


## 16. Mandatory input for the first NG3 review

This handoff must be included explicitly in the first whole-scope NG3 review.

It is **not** normative NG3 architecture and must not be copied forward mechanically. Its role
is historical/conversation delta and review evidence:

- identify NG2 decisions that were made deliberately and should not be accidentally
  rediscovered or reversed;
- identify unresolved semantics that NG2 intentionally did not invent;
- identify complexity that was removed because it did not serve real VPN-GATE scenarios;
- compare those decisions against the NG3 product requirements and component decomposition;
- distinguish reusable experimental evidence from obsolete NG2 implementation structure.

The first NG3 review must therefore ask, for every material item in this handoff:

1. which accepted NG3 requirement, if any, still needs the behavior;
2. which NG3 component responsibility, if any, legitimately realizes it;
3. whether the item is evidence, a constraint, a historical implementation decision or an
   unresolved question;
4. whether carrying it forward would preserve product value or merely preserve NG2 shape.

Absence of a current NG3 requirement is not by itself a reason to invent one in order to
retain an NG2 mechanism.
