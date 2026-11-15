# VPN-GATE NG2 — AvailabilityProbeManager

> **2026-11-15 normative update:** availability hysteresis, input aggregation and the
> collector-to-route-materializer boundary are now defined by
> `design/NG2/availability-collector-materializer.md`. The observation-window,
> `evidence_epoch`, `elapsed_intervals` and asynchronous collector/materializer ordering
> text below is retained temporarily as implementation-migration context and is not
> normative where it conflicts with that document.

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
- current concrete physical generation;
- generation-bound execution demand for the probe Agent.

It does not own:

- Profile binding membership;
- payload route membership;
- payload route metrics;
- GOOD/BAD availability hysteresis and counters;
- route-priority materialization;
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

## 6. Execution observations

Production availability semantics remain non-attempt-oriented.

A current physical reply produces colorless good news associated with the current logical
consumer/channel. The physical generation guard exists only to reject results from an
obsolete ProbeRules/interface generation.

`AvailabilityProbeManager` does not turn those replies into routing verdicts. Routing
hysteresis is owned by the bounded collector inside `PayloadTrafficManager`, defined in
`design/NG2/availability-collector-materializer.md`.

The execution side also produces a logical tick. The tick has level semantics for the
collector: repeated undrained firings collapse to one pending fact.

There is no production negative reply event.

## 7. Execution plan

The Manager projects current enabled probes plus the READY physical generation into
execution demand.

The plan contains the information needed to:

- send probes on each current concrete physical plane;
- schedule one tick cadence for each logical channel;
- reject old physical-worker results after generation invalidation.

It does not contain:

- logical `evidence_epoch`;
- elapsed-window counts;
- failure/recovery counters;
- route priority.

A logical-policy-only change updates/reset the affected collector channel through the
current configuration path; it does not require a separate execution evidence epoch.

## 8. Collector boundary

The routing-relevant availability state is not materialized inside this Manager.

Current good-news/tick observations update the bounded producer-facing input owned by
`PayloadTrafficManager`:

```text
pending_good_news: saturating counter
tick_pending: bool
```

That input port is deliberately non-blocking: producers update bounded aggregates under a
short lock and return. The PayloadTrafficManager collector loop owns GOOD/BAD policy and
synchronous route-priority materialization.

`AvailabilityProbeStateInfo` may remain as diagnostic/status projection during
implementation migration, but it is not the routing-control intermediate.

## 9. Physical generation safety

Every physical request names a concrete `InterfaceIdentity(ifname, ifindex)`.

Same-name/new-ifindex is a new concrete generation. A worker result from an invalidated
generation must not contribute good news after the new generation becomes current.

This is the only epoch-like mechanism required by this availability path. It guards
physical worker lifetime; it does not order collector inputs or materializer requests.

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

The current Linux execution path reuses the same prerequisite through the already proven
single-shot ping Driver, hidden below `LinuxDiagnosticPingSendAdapter`. Its ownership
belongs to execution machinery, never `NetworkRulesAdapter` policy.

The long-lived lifecycle belongs to `LinuxProbeExecutionAgent`; individual ping workers
are bounded technical sends and remain generation-checked.

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

1. Event Delivery envelope revision/ordering implementation around the currently tested
   latest-value handlers;
2. daemon/runtime assembly that instantiates `LinuxProbeExecutionAgent` and connects the
   real Event Delivery Environment;
3. Profile/status consumption of generation-scoped local execution diagnostics;
4. target/live validation only if the execution mechanism later differs materially from
   the already proven capability-free `ping` worker.

Filter/NAT semantic order remains independent from route priority.

No retry scheduler, recovery threshold, per-attempt `NO_REPLY` policy or shadow fallback
tier should be reintroduced without a new concrete requirement.
