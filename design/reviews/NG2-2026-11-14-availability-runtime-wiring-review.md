# NG2 autonomous review — availability runtime wiring

**Date:** 2026-11-14  
**Branch:** `code-cycle-20261114-availability-runtime-wiring`  
**Baseline:** `02c932c9993c58ba8508809a37eada661f0be1f7`

## Scope

Reviewed the first executable path:

```text
valid probe reply
 -> AvailabilityProbeManager window state
 -> AvailabilityProbeStateInfo
 -> RuntimeStateManager
 -> probe/Profile evidence projection
 -> PayloadTrafficIntentCalculator
 -> PayloadTrafficStateRequest
 -> serialized PayloadTrafficManager
 -> existing NetworkRulesAdapter / route-priority Executor
```

The review specifically looked for:

- accidental return of per-attempt availability semantics;
- hidden state inside Calculators;
- coupling availability to binding membership;
- ambiguous probe-to-Profile ownership;
- rebase rules broader than the agreed path-order policy;
- transaction interleaving under re-entrant or concurrent delivery;
- unused new Engine abstractions;
- contradictions with EXP-027 and the free-slot route transition model.

## Findings

### F1 — positive evidence belonged to the physical plane, not one semantic attempt

**Status:** accepted and fixed.

Production ingress is generation-bound:

```text
(mechanism, InterfaceIdentity, target, ProbeObservationGeneration)
```

One valid reply fans out to all enabled logical consumers sharing that physical plane.

No attempt id, semantic reply correlation or per-attempt `NO_REPLY` was added.

### F2 — negative evidence must remain a window integral

**Status:** accepted and executable.

For each enabled logical probe the Manager owns:

```text
confirmed_live
missed_intervals
good_news_since_boundary
```

Good-news immediately publishes REACHABLE and resets the integral. Empty windows increment
the integral and publish UNREACHABLE only at `failure_intervals`.

A technical sender error has no direct routing transition; absent good-news it is just one
window without positive evidence.

### F3 — shared physical plane and logical policy required separate state

**Status:** accepted and fixed.

Logical consumers sharing one physical probe plane may have different timing policy. A
physical reply therefore fans out into separate logical `AvailabilityWindowState`
instances.

A logical-only policy change preserves the READY rules generation but resets only that
logical evidence window.

### F4 — probe_id -> Profile association was missing from the runtime contract

**Status:** accepted and fixed without changing physical ProbeRules.

Added runtime-derived:

```text
ProfileProbeAssignment(profile_name, probe_ids)
```

It remains outside physical probe rules and Linux policy. A logical probe may feed multiple
Profiles.

Runtime validates assignments before publication:

- Profile must exist;
- probe_id must exist;
- probe concrete path must be eligible for that Profile.

### F5 — effective-order calculation must not hide history inside Calculator

**Status:** accepted and fixed.

`PayloadTrafficIntentCalculator` is externally stateless. It receives explicitly:

- current configured payload snapshot;
- previous configured snapshot;
- current effective snapshot;
- current Profile availability evidence.

RuntimeStateManager owns latest-value storage.

### F6 — initial rebase condition was too broad

**Status:** accepted and fixed.

An early implementation rebased effective order when any `PayloadProfileRequest` field
changed.

That contradicted the agreed rule. Rebase now occurs only when:

- the Profile is new;
- eligible path membership changes;
- configured path priority changes;
- current effective membership is no longer representable.

Changes to direction, destinations, traffic envelope or NAT policy do not by themselves
erase current bubble-order history. Output still uses the newest configured path metadata.

### F7 — inactive availability and zero-live availability must remain distinct

**Status:** confirmed.

```text
confirmed_live = None
    -> availability-derived priority inactive
    -> configured order
    -> confirmed_live_prefix_length=None

confirmed_live = {}
    -> availability active, no positive evidence
    -> preserve current effective order
    -> confirmed_live_prefix_length=0
```

Neither state removes payload membership.

### F8 — transaction serialization could not rely on accidental single-threaded delivery

**Status:** accepted and fixed.

PayloadTrafficManager now owns exactly one reconcile executor.

The pending model is latest-value:

```text
A active
B arrives -> pending B
C arrives -> pending C
A completes
C starts
```

A short mutex protects executor ownership and pending state. The mutex is not held across
Adapter I/O, so re-entrant delivery does not deadlock. Concurrent delivery cannot start a
second materializer.

Audit uses the same executor.

Unexpected lower exception releases executor ownership so later events cannot remain
permanently queued behind a dead executor.

### F9 — RuntimeStateManager also needed concurrent latest-value serialization

**Status:** accepted and fixed.

RuntimeStateManager uses a re-entrant lock around its latest-value cache, calculation and
publication. Concurrent probe-state callbacks therefore cannot publish a stale calculation
after a newer one merely because their execution overlapped.

This does **not** solve late delivery of an old Event revision after a newer invocation has
already completed. That remains the EventEnvelope epoch/revision filter responsibility.

### F10 — existing blocking LinuxIcmpProbeDriver is not the production transport contract

**Status:** explicitly retained as an open gate.

The diagnostic worker returns one blocking:

```text
REPLY | NO_REPLY | ERROR
```

result and has a technical timeout. Promoting that API directly into availability policy
would recreate the attempt boundary just removed.

Therefore this review does not relabel it as production sender/receiver. The remaining
execution unit must provide valid-reply good-news plus interval triggers while keeping
NO_REPLY/ERROR out of routing semantics.

## Complexity audit

No new availability Manager/Engine was added.

The new split is:

```text
AvailabilityProbeManager        # existing Engine, now owns evidence windows
RuntimeStateManager             # existing conceptual Engine, first executable slice

ProbeProfileEvidenceCalculator  # pure Machinery
PayloadTrafficIntentCalculator  # pure Machinery
```

This is smaller than adding a dedicated AvailabilityRoutingManager or scheduler.

No retry scheduler, recovery threshold, shadow route tier, ECMP failover or per-flow pinning
was introduced.

## Evidence

Latest reviewed executable head before documentation-only commits:

`dc0bd94f1446a05e64f56561f10183375e82649e`

passed:

- NG2 unit suite: **290 tests PASS**;
- privileged NG2 Linux integration: PASS;
- EXP-027: PASS;
- Linux Adapter availability route transition A4: PASS;
- NG1 Python validation: PASS.

Additional focused coverage proves:

- immediate good-news recovery;
- failure-window hysteresis;
- shared physical-plane fan-out;
- stale readiness-generation rejection;
- logical-policy window reset;
- disabled consumer exclusion;
- probe -> Profile evidence projection;
- inactive vs zero-live semantics;
- configured-priority/membership rebase;
- preservation of bubble order across unrelated Profile policy changes;
- single-path retention;
- re-entrant request coalescing;
- actual concurrent request serialization;
- end-to-end good-news arriving during an active payload apply.

## Remaining gates

1. production probe sender/receiver transport;
2. ownership of interval triggers/cadence without semantic attempt scheduling;
3. diagnostic persistent local execution-error publication;
4. Event Delivery Environment epoch/revision filter for late old events;
5. final target validation if production execution transport materially differs from the
   already proven diagnostic ping mechanics.

## Verdict

**PASS** for the runtime semantic wiring and transaction-serialization review unit.

The availability evidence -> payload priority path is now executable without changing
binding membership and without reopening the rejected attempt-oriented design.

The sender/receiver transport is intentionally not claimed complete.
