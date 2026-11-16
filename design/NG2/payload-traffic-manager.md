# VPN-GATE NG2 — PayloadTrafficManager

**Status:** normative NG2 design  
**Date:** 2026-11-15  
**Scope:** steady-state payload policy, optional availability priority, and network-rules convergence  
**Related:** `design/component-model.md`, `design/NG2/network-rules-adapter.md`,
`design/NG2/availability-collector-materializer.md`

## 1. Role

`PayloadTrafficManager` is the Manager Engine that owns the current payload forwarding
policy.

It is responsible for:

- current structural/admin payload intent;
- configured path priority for each Profile;
- optional availability-derived priority adjustment;
- translation of payload semantics into common `NetworkRulesSpec`;
- one serialized reconcile/materialization executor;
- drift observation/repair;
- publication of `PayloadTrafficStateInfo`.

It does **not** own:

- VPN process lifecycle;
- interface discovery/binding;
- probe execution, target selection or cadence;
- Linux table IDs, RPDB priorities or route metrics;
- nft syntax/names;
- kernel mutation ordering;
- lower-domain verification commands.

Those responsibilities stay outside the payload domain.

## 2. Inputs

Payload has two independent control inputs.

### 2.1. Structural payload intent

```text
PayloadTrafficStateRequest
    profiles[]
        name
        direction
        destinations
        ordered_paths[]
            InterfaceIdentity
            traffic envelope
            NAT mode
```

This Request is purely structural/admin intent.

It does **not** contain:

- availability channels;
- probing configuration;
- availability verdicts;
- preferred-prefix/gap position;
- route metrics;
- Linux materialization data.

The configured `ordered_paths` is the baseline administrative priority.

### 2.2. Optional availability-priority input

Availability is a separate auxiliary input:

```text
AvailabilityPriorityConfig
    channels[]
        channel_id
        path
        enabled
        AvailabilityHysteresisPolicy
            failure_ticks
            recovery_good_news

    assignments[]
        profile_name
        channel_ids[]
```

This contract is deliberately probe-independent.

It contains no:

- target address;
- probe mechanism;
- probe cadence;
- physical generation;
- attempt identity;
- timestamp.

Probe execution may be the producer of this signal, but payload priority does not depend
on probe transport semantics.

If no enabled assigned channel participates in a Profile, availability is inactive for that
Profile and must be a true semantic no-op.

### 2.3. Availability observations

Runtime observations are also probe-independent:

```text
AvailabilityGoodNews(current AvailabilityPriorityChannel)
AvailabilityTick(current AvailabilityPriorityChannel)
```

The full immutable channel descriptor is carried only as a cheap stale-definition guard.
Payload accepts an observation only if it exactly matches the current channel descriptor.

No EventEnvelope/epoch is required for this local boundary.

## 3. Availability is not payload membership

Availability is only a priority modifier.

It must never:

- add a payload path;
- remove a payload path;
- change binding eligibility;
- change a Profile destination;
- alter traffic envelope or NAT policy.

Initial state is:

```text
availability_problems = false
```

Disabled availability is also equivalent to no availability problem.

Configured order therefore remains authoritative at startup and whenever availability is
inactive.

The channel state machine is normative in
`design/NG2/availability-collector-materializer.md`.

## 4. Availability aggregation by Profile/path

One Profile may associate multiple availability channels with the same path.

For one Profile/path:

- disabled channels do not participate;
- if no enabled assigned channel exists for that path, availability has no opinion;
- a path is considered to have availability problems only when **all enabled assigned
  channels for that path** currently have `availability_problems=true`.

One non-problem enabled channel is sufficient to keep the path in the normal class.

This is intentionally less aggressive than "any failed probe demotes the path."

## 5. Effective path order

The Manager calculates current effective order from:

```text
configured order
last verified effective order
current set of problem paths
```

Rules:

1. structural/admin change rebases to current configured order;
2. paths without availability problems form the leading prefix in configured priority;
3. paths with problems remain present;
4. problem paths preserve their current relative order;
5. if all paths have problems, current relative order is retained;
6. if no path has problems, effective order equals configured order.

The last verified effective order is retained because it is route-materialization state
needed to preserve relative ordering. It is not probe/evidence history.

## 6. Bounded availability input

Per channel:

```text
pending_good_news: 0..recovery_good_news
tick_pending: bool
```

Good news saturates at the recovery threshold.

Repeated undrained ticks collapse to one pending fact.

The Manager owns one short serialization lock:

- producer ingress updates bounded state under the lock;
- if the reconcile executor is already active, ingress returns;
- otherwise that caller may become the executor;
- the lock is never held over Calculator or Adapter I/O.

No ping queue, tick queue, collector thread, materializer-ready event or availability
route-plan queue is required.

## 7. Single reconcile executor

All payload work shares one serialized executor:

```text
structural request
availability config
availability observation
audit
        |
        v
single reconcile loop
        |
        v
NetworkRulesAdapter
```

A running Adapter transaction is immutable.

New inputs arriving while it runs may update latest pending state, but cannot interleave
the current lower transaction.

Coalescing rules:

- newer structural request supersedes older pending structural request;
- newer availability config supersedes older pending availability config;
- good news/ticks accumulate in bounded per-channel state;
- audit is deferred behind newer pending policy work.

There is no second route-priority executor.

## 8. PayloadRulesCalculator

`PayloadRulesCalculator` is a Direct pure Calculator:

```text
calculate(PayloadTrafficStateRequest) -> NetworkRulesSpec
```

It translates only structural payload semantics:

- Profile routing domains;
- destinations;
- current ordered paths;
- terminal fail-close action;
- dispatch;
- direction/new-flow admission;
- traffic envelopes;
- NAT intent.

It does not know availability configuration or hysteresis.

It does not allocate Linux-specific identifiers or generate Linux commands.

## 9. Lower routing priority hint

The common lower routing domain has an optional technical field:

```text
RoutingDomainSpec.preferred_prefix_length: int | None
```

This is **not** part of `PayloadTrafficStateRequest`.

The Manager injects a non-None value into the already-calculated `NetworkRulesSpec`
only while at least one path in that Profile currently has availability problems.

Semantics for N paths:

```text
None -> no auxiliary priority boundary is active; this includes inactive/disabled
        availability and active availability with zero current problem paths
K    -> at least one problem path exists; first K paths are preferred and lower layer
        derives one free metric before path K+1
0    -> every eligible path is currently in the problem tail
```

The name is intentionally generic. The lower Adapter does not need to know that the
preferred-prefix hint happened to originate from availability.

The free metric slot remains emergent lower-domain state; it is not stored/configured as
an object.

## 10. Desired-state construction

For one reconcile:

```text
PayloadTrafficStateRequest
        |
        v
calculate effective ordered_paths
        |
        v
PayloadRulesCalculator
        |
        v
NetworkRulesSpec
        |
        +-- if availability active:
        |      inject preferred_prefix_length
        |
        v
desired NetworkRulesSpec
```

If the resulting desired `NetworkRulesSpec` is semantically identical to the current
desired rules, no materialization is started.

Drift is checked by `audit()`, not by replaying identical RequestEvents.

## 11. NetworkRulesAdapter boundary

The Manager uses the common Direct Adapter:

```text
apply(owner, spec) -> ActionResult
renew_state(owner) -> ActionResult
get_last_state(owner) -> NetworkRulesState
cleanup(owner) -> ActionResult
```

`ActionResult` reports operation success/failure only. It is not a payload verdict.

A successful `apply()` means the Adapter freshly verified the requested semantic
projection.

A failed operation is followed by observation and state calculation; the Manager never
invents a synthetic FAILED payload state solely from the operation result.

Linux mutation/verification internals remain behind this boundary.

## 12. Payload state

The Manager publishes:

```text
PayloadTrafficStateInfo
    rules_state: PayloadRulesState
        knowledge
        convergence
        safety
        service

    profiles[]
        profile_name
        observed_paths: tuple[InterfaceIdentity, ...] | UNKNOWN
```

`observed_paths` is the actual observed materialized routing order for the requested
Profile.

It is valid payload state even if an optional availability signal influenced that order.

No probe verdict, reachability state, availability counter or availability diagnostic is
part of `PayloadTrafficStateInfo`.

`PayloadRulesState` remains multidimensional:

- knowledge: `KNOWN | UNKNOWN`;
- convergence: `MATCHED | DIVERGED | UNKNOWN`;
- safety: `SAFE | UNSAFE | UNKNOWN`;
- service: `READY | DEGRADED | ISOLATED | UNKNOWN`.

## 13. Audit and drift repair

`audit()` performs one deterministic pass:

```text
renew_state()
get_last_state()
calculate PayloadRulesState

if convergence != MATCHED:
    apply(current desired)
    observe again

publish semantic state if changed
```

Repair is driven by convergence, not service severity.

Therefore a correctly materialized isolated/zero-path request does not create a repair
loop merely because service is isolated.

## 14. Failure semantics

Pure Calculator rejection means invalid/unrepresentable input and occurs before lower
mutation.

Adapter failure means only that the requested synchronous lower operation did not complete
with a verified success.

After failure the Manager observes what can actually be proven and publishes that state.

Unexpected lower exceptions must release reconcile ownership so the Manager cannot remain
permanently wedged.

## 15. Core invariants

1. Structural payload intent is independent of availability.
2. Availability never changes payload membership.
3. Probe target/mechanism/cadence never enter the payload domain.
4. Availability disabled/absent is a true priority no-op.
5. PayloadTrafficManager owns exactly one reconcile/materialization executor.
6. A lower transaction cannot be modified while running.
7. Current desired state persists until superseded.
8. Drift repair does not require a new RequestEvent.
9. PayloadTrafficManager does not know Linux allocation identifiers.
10. NetworkRulesAdapter does not know Profile satisfaction or availability hysteresis.
11. Same-name/new-ifindex remains a distinct concrete `InterfaceIdentity`.
12. `preferred_prefix_length` is lower routing intent, not user/payload configuration.
13. The free route metric slot is emergent and never persistent configuration.
14. Payload state output contains observed payload facts, not probe verdicts.

## 16. Evidence

Relevant evidence retained:

- EXP-012: drift/fail-closed structural repair and verification;
- EXP-017: same-name/new-ifindex generation identity;
- EXP-023: availability may change while interface identity remains stable;
- EXP-027: route-only priority permutation with make-before-break metric moves;
- current privileged Linux Adapter/LOCAL_PROCESS/dataplane integrations.

The payload/probing decoupling itself introduces no new kernel claim. It was validated by
the existing deterministic and privileged suites.

## 17. Remaining work

Payload management itself has no open availability-state redesign.

Remaining runtime work is assembly:

- produce structural `PayloadTrafficStateRequest`;
- produce `AvailabilityPriorityConfig` from normalized runtime configuration;
- send the physical probe request separately to `AvailabilityProbeManager`;
- wire `ProbeExecutionAgent` good-news/tick output to PayloadTrafficManager;
- project probe execution diagnostics into status/diagnostics;
- schedule audit/retry policy around the already deterministic `audit()`.

General Event Delivery revision/ordering remains relevant only to asynchronous streams
that actually need it; it is not part of the local availability ingress.
