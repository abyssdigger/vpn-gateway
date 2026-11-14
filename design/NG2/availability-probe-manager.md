# VPN-GATE NG2 — AvailabilityProbeManager

**Status:** active NG2 design  
**Date:** 2026-11-14  
**Scope:** active availability-probe managed domain  
**Routing policy:** `design/NG2/availability-routing-model.md`

## 1. Responsibility

`AvailabilityProbeManager` owns the active probe subsystem:

- latest accepted `AvailabilityProbeSetRequest`;
- probe-specific `NetworkRules` ownership;
- probe-rules observation and repair;
- concrete-interface/rules readiness generation;
- execution-side probe evidence;
- publication of `AvailabilityProbeStateInfo`.

It does not own:

- Profile binding membership;
- payload route membership;
- payload route metrics;
- selection of the last surviving payload path;
- VPN process lifecycle;
- user-facing configuration parsing.

Availability is an input to payload **priority**, not an admission gate.

## 2. Minimal routing semantics

The normative availability/routing model is intentionally small:

```text
eligible paths
    +
configured priority
    +
confirmed-live evidence
    +
current effective order
        |
        v
bubble promotion
        |
        v
PayloadProfileRequest.ordered_paths
```

Probe evidence never removes an eligible path.

For routing preference only two classes matter:

```text
CONFIRMED_LIVE
NOT_CONFIRMED_LIVE
```

`UNREACHABLE`, local probing error and absence of sufficient current evidence may remain
different diagnostic conditions, but none of them means "delete this payload path".

## 3. Probe request

The current normalized request remains:

```text
probe_id
mechanism
concrete InterfaceIdentity
IPv4 target
enabled
AvailabilityWindowPolicy
    interval_seconds
    failure_intervals
```

`enabled=false` is logical probe state, not timing policy. It disables autonomous probing
without deleting the configured logical probe. Its target, path association and timing
configuration therefore remain available for later re-enable.

Physical ProbeRules are calculated only from enabled logical probes. Disabling the last
consumer of a physical `(mechanism, InterfaceIdentity, target)` plane closes that plane;
disabling one of several logical consumers sharing the same plane leaves it intact.

Every normalized logical probe carries timing policy. There is no policy-less manual mode;
`enabled=false` is the only normalized way to keep a configured probe while disabling
autonomous execution.

Timing policy is not part of physical `ProbeRulesCalculator` output.

## 4. Probe NetworkRules

Pure machinery:

```text
AvailabilityProbeSetRequest
        |
        v
ProbeRulesCalculator
        |
        v
NetworkRulesSpec
```

The physical plane is keyed by:

```text
(mechanism, InterfaceIdentity, target)
```

Several logical `probe_id` values may share one physical plane.

The Manager uses itself as one opaque owner of the shared `NetworkRulesAdapter`.

## 5. Rules readiness and interface generation

Probe evidence is authoritative only while probe rules are freshly:

```text
KNOWN + MATCHED + READY
```

Every request names a concrete `InterfaceIdentity(ifname, ifindex)`.

Same-name/new-ifindex is a new concrete generation. Evidence from an older generation must
not be reused.

The Manager keeps an owner-wide rules-readiness epoch:

- no epoch exists before fresh READY;
- physical desired-rules change invalidates the epoch;
- loss of READY invalidates the epoch;
- later fresh READY starts a new epoch;
- logical-only request change with physically identical rules preserves the epoch and
  invalidates only the changed logical probe evidence.

This epoch is Manager-local. It is not encoded into routing tables, uid, conntrack mark or
nft objects.

## 6. Good-news model

Production availability semantics are **not attempt-oriented**.

The routing-relevant positive input is only a generation-bound fact about the physical
probe plane:

```text
good_news(
    mechanism,
    concrete InterfaceIdentity,
    target,
    ProbeObservationGeneration
)
```

Any valid reply through the current concrete probe plane is good news regardless of which
send caused it. The Manager fans one such fact out to every enabled logical `probe_id`
sharing the same physical `(mechanism, InterfaceIdentity, target)` plane.

No routing-policy contract requires:

- attempt id;
- matching reply to a semantic attempt object;
- per-attempt `NO_REPLY`;
- recovery streak;
- retry cadence;
- verdict timeout attached to one send.

A valid good-news event immediately confirms the path live and resets accumulated missed
intervals.

## 7. Negative integral

Negative evidence is accumulated at observation-window boundaries.

For one logical probe the minimal state is:

```text
confirmed_live
missed_intervals
good_news_since_boundary
```

At a boundary:

```text
good news seen:
    missed_intervals = 0
    confirmed_live = true

no good news:
    missed_intervals += 1
    if missed_intervals >= failure_intervals:
        confirmed_live = false
```

One positive reply is sufficient for recovery. There is no `recovery_threshold`.

A local probing error does not prove remote unreachability. For routing preference it
simply fails to provide positive evidence; diagnostics may retain the local error reason.
The same interval integral prevents a transient local fault from becoming an immediate
persistent negative conclusion.

## 8. Routing consequence

`AvailabilityProbeStateInfo` is consumed by runtime priority calculation, not by
`BindingCalculator`.

The current routing rule is:

- confirmed-live paths may bubble above paths without confirmed live evidence;
- live paths preserve configured priority;
- paths without confirmed-live evidence are retained;
- if no confirmed-live alternative exists, probing does not perturb the current payload
  order.

The exact algorithm and route-transition requirements are normative in
`availability-routing-model.md`.

## 9. Current executable split

The clean pure policy core is implemented in:

```text
availability_routing.py
    AvailabilityWindowPolicy
    AvailabilityWindowState
    calculate_effective_path_order()
```

`AvailabilityProbeRequest.enabled` remains outside the timing type. The old autonomous
attempt scheduler remains removed.

`AvailabilityProbeManager` now owns the production evidence/window state above its
verified NetworkRules generation boundary:

```text
note_good_news(path, target, generation, mechanism)
close_interval(probe_id, generation)
```

Properties:

- good-news is accepted only for the current READY generation;
- stale-generation good-news and stale window boundaries are ignored;
- one physical reply fans out to all enabled logical consumers of that plane;
- good-news publishes `REACHABLE` immediately and resets the negative integral;
- a window without good-news increments the integral;
- `UNREACHABLE` is published only after `failure_intervals`;
- local sender failure has no direct routing transition: unless good-news arrives, the
  window simply closes without positive evidence;
- logical policy change with unchanged physical rules preserves the READY generation but
  resets only that logical probe's evidence window;
- physical rules-generation change resets all evidence windows.

The Manager still does **not** depend on a synchronous ProbeDriver and does not expose
attempt-oriented `attempt_once()/evaluate_once()`.

`LinuxIcmpProbeDriver` remains standalone diagnostic/evidence machinery. Its blocking
single-shot `REPLY/NO_REPLY/ERROR` API is not promoted to the production semantic
boundary: in particular, `NO_REPLY` must not become a routing event.

The production execution contract is now explicit and remains non-attempt-oriented.

`ProbeExecutionPlanCalculator` projects the current enabled logical request plus READY
`ProbeObservationGeneration` into:

```text
ProbeExecutionPlan
    generation
    physical planes:
        mechanism
        concrete InterfaceIdentity
        target
        send interval
    logical windows:
        probe_id
        observation interval
```

Several logical probes that share one physical plane share transport sends. The physical
send interval is the smallest interval requested by its enabled consumers. Logical window
cadence remains per `probe_id`, so consumers with different `failure_intervals` or
intervals do not share hysteresis state.

Execution may report only two production facts back across this boundary:

```text
ProbeGoodNewsInfo
ProbeWindowBoundaryInfo
```

There is deliberately no production `NO_REPLY` event. Absence of a reply acquires routing
meaning only when `AvailabilityProbeManager` processes a logical window boundary.

Plan activation has deterministic phase semantics:

```text
t = activation:
    start all logical observation windows
    issue one send immediately on every physical plane

t = later boundary:
    first close windows whose deadline is now
    then issue sends whose next physical deadline is now
```

Thus the first observation window is never consumed before any probe has been sent. At a
shared timestamp, a send starts the next window rather than retroactively supplying good
news to the window that just closed. Replies are classified by arrival, not by attempt
correlation.

Good-news and boundary events for one execution generation must be emitted through one
ordered execution stream. EventEnvelope ordering remains responsible for rejecting late
older revisions once that infrastructure is implemented.

The Manager serializes request/audit/good-news/window handlers with one re-entrant state
lock. A physical generation transition therefore cannot race an old reply into the new
window state.

The current code stops at this semantic execution contract. Concrete long-lived
sender/receiver machinery and its process/socket lifecycle remain the next lower
implementation unit; it must consume the plan without restoring the diagnostic
single-shot `ProbeAttemptResult` contract.

## 10. Linux technical identity

Linux runtime assembly supplies one authoritative process identity:

```text
LinuxLocalProcessConfig
    uid
    ct_mark
```

Probe execution additionally receives process-only values such as gid and executable path.

The semantic probe request contains none of those Linux values.

## 11. ping socket prerequisite

The standalone Linux diagnostic worker proves capability-free ping sockets with
namespace-local `net.ipv4.ping_group_range`.

The final production sender/receiver may reuse the same prerequisite, but its ownership
belongs to execution machinery, never `NetworkRulesAdapter` policy. Shutdown cleanup is
defined together with that final execution lifecycle.

## 12. Removed policy

The following are no longer part of NG2 availability routing semantics:

```text
retry_interval_seconds
timeout_seconds as verdict policy
recovery_threshold
serial run_due() scheduler
per-attempt NO_REPLY hysteresis
synchronous ProbeDriver dependency in AvailabilityProbeManager
attempt_once()/evaluate_once() Manager API
ERROR -> immediate routing UNKNOWN transition
availability-driven BindingCalculator removal
UNAVAILABLE_METRIC / shadow fallback tier
```

Historical reviews/checkpoints that contain those concepts remain evidence of the design
path and are not rewritten as though the later simplification had always existed.

## 13. Evidence

Still-valid lower evidence:

- EXP-024: selective LOCAL_PROCESS routing/filtering PASS on Debian 13;
- EXP-025: same-name/new-ifindex stale conntrack generation demonstrated;
- EXP-026: selective probe-class conntrack cleanup PASS in privileged CI;
- Linux LOCAL_PROCESS Adapter integration PASS;
- Linux ICMP selector/nft integration PASS;
- target `/usr/bin/ping` generation-bound execution evidence remains valid.

These experiments prove probe-plane safety properties. They do not require the removed
per-attempt routing policy.

## 14. Open implementation units

The runtime semantic path is now executable through:

```text
valid reply
 -> AvailabilityProbeManager good-news/window state
 -> AvailabilityProbeStateInfo
 -> RuntimeStateManager
 -> Profile availability evidence
 -> PayloadTrafficIntentCalculator
 -> PayloadTrafficStateRequest
 -> serialized PayloadTrafficManager
 -> NetworkRulesAdapter route-priority fast path
```

Remaining work is narrower:

1. concrete long-lived sender/receiver machinery implementing `ProbeExecutionPlan`;
2. diagnostic publication of persistent local probing errors without changing routing
   safety;
3. Event Delivery envelope revision/ordering implementation around the currently tested
   latest-value handlers;
4. target/live validation of the final execution transport if it differs materially from
   the already proven diagnostic `ping` worker.

Filter/NAT semantic order remains independent from route priority.

No retry scheduler, recovery threshold, per-attempt `NO_REPLY` policy or shadow fallback
tier should be reintroduced without a new concrete requirement.
