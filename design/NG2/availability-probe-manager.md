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
optional AvailabilityWindowPolicy
    interval_seconds
    failure_intervals
```

`enabled=false` is logical probe state, not timing policy. It disables autonomous probing
without deleting the configured logical probe. Its target, path association and timing
configuration therefore remain available for later re-enable. Enable/disable does not
change the physical ProbeRules plane; current logical evidence is invalidated.

`policy=None` is retained only as an internal/manual transition state while runtime
assembly is incomplete. It is not the preferred user-facing way to disable a configured
probe.

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

The routing-relevant positive input is only:

```text
good_news(probe_id)
```

Any valid reply through the current concrete probe plane is good news regardless of which
send caused it.

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

`AvailabilityProbeRequest.enabled` remains outside the timing type.
```

The old autonomous scheduler has been removed.

The current `AvailabilityProbeManager.attempt_once()` and `evaluate_once()` remain only as
explicit diagnostic/verification primitives over the already proven lower boundary. They
must not be used as production routing policy.

Likewise, `LinuxIcmpProbeDriver` is currently a verified synchronous single-shot worker.
It proves generation binding, capability-free execution and result classification, but its
blocking attempt API does not define the final sender/receiver runtime architecture.

A later execution integration may replace this worker contract without changing the
good-news/window routing semantics.

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

The current Linux single-shot worker uses capability-free ping sockets and idempotently
writes/verifies namespace-local `net.ipv4.ping_group_range` for its gid.

This remains execution machinery, not `NetworkRulesAdapter` policy.

Shutdown cleanup of this process prerequisite remains open until the final execution
lifecycle is selected.

## 12. Removed policy

The following are no longer part of NG2 availability routing semantics:

```text
retry_interval_seconds
timeout_seconds as verdict policy
recovery_threshold
serial run_due() scheduler
per-attempt NO_REPLY hysteresis
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

The remaining work is deliberately narrow:

1. integrate a non-attempt-correlated good-news source with `AvailabilityWindowState`;
2. define diagnostic publication of persistent local probing errors without changing
   routing safety;
3. feed confirmed-live evidence into effective payload ordering, not binding membership;
4. integrate the already proven EXP-027 route-slot fast path into the eventual runtime
   ordering flow;
5. keep filter/NAT semantic order independent from route priority; the current
   PayloadRulesCalculator already canonicalizes path-policy generation for this purpose.

No retry scheduler, recovery threshold or shadow fallback tier should be reintroduced
without a new concrete requirement.
