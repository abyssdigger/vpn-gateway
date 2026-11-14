# VPN-GATE NG2 — AvailabilityProbeManager

**Status:** active NG2 design  
**Date:** 2026-11-14  
**Scope:** active availability-probe managed domain

## 1. Responsibility

AvailabilityProbeManager owns the active probe subsystem.

It owns:

- the latest accepted `AvailabilityProbeSetRequest`;
- probe-specific NetworkRules ownership through the common NetworkRulesAdapter;
- interpretation of ProbeRulesState;
- probe-attempt lifecycle;
- current probe evidence for each logical `probe_id`;
- publication of AvailabilityProbeStateInfo.

It does not own:

- Profile binding decisions;
- payload routing/NAT/filtering;
- VPN process lifecycle;
- NetworkRules physical allocation;
- user-facing timing configuration parsing.

## 2. Network rules machinery

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

The Manager uses itself as one opaque owner of the shared NetworkRulesAdapter.

Observed rules are interpreted through:

```text
ProbeRulesStateCalculator(
    desired NetworkRulesSpec,
    observed NetworkRulesState
)
    -> ProbeRulesState
```

ProbeRulesState is intentionally distinct from PayloadRulesState:

```text
knowledge
convergence
usability
```

Only `KNOWN + MATCHED + READY` permits active probe evidence to be authoritative.

## 3. Rules-before-execution invariant

A probe attempt may contribute current availability evidence only after fresh rules
observation proves the desired probe plane READY.

An Adapter action SUCCESS alone is insufficient.

If rules become UNKNOWN or DIVERGED/INVALID:

- current probe evidence for that rules generation is no longer authoritative;
- the Manager must not reinterpret an execution failure as remote UNREACHABLE;
- the Manager must reconcile/refresh rules before accepting new evidence.

This prevents both:

- false negative from a restrictive local plane;
- false positive from alternate-path escape or widened local policy.

## 4. Interface generation

Every request names a concrete `InterfaceIdentity(ifname, ifindex)`.

Same-name/new-ifindex is a new generation.

Probe execution independently rechecks the concrete generation immediately before the
attempt. NetworkRules observation and Driver generation checking are complementary:
neither is replaced by the other.

Probe evidence must not survive a concrete-generation change.

The Manager represents this with an owner-wide **rules-readiness epoch**. The epoch is
Manager-local and opaque to NetworkRulesSpec/Linux technical identity:

- no epoch exists before fresh `KNOWN + MATCHED + READY`;
- leaving READY invalidates all evidence from the current epoch;
- a later fresh transition back to READY starts a new epoch;
- changing the physical desired `NetworkRulesSpec` invalidates the previous epoch;
- a same-name/new-ifindex request therefore cannot reuse old evidence;
- logical-only request changes that leave the physical probe plane unchanged preserve the
  rules-readiness epoch and invalidate evidence/scheduling only for changed `probe_id`
  entries.

The epoch is not a kernel/network generation identifier and is not encoded into uid,
conntrack mark, routing tables or nft rules.

A physical backend rebuild that leaves the Manager's semantic rules observation continuously
fresh READY does not by itself invalidate already completed evidence. Future attempt safety
remains the responsibility of the verified probe plane plus its lower-domain generation
mechanism.

## 5. Single-shot ICMP Driver

The first executable worker is `LinuxIcmpProbeDriver`.

It performs one bound attempt and returns:

```text
REPLY
NO_REPLY
ERROR
```

These are raw attempt outcomes.

The first explicit verdict baseline is intentionally minimal and lives above this Driver:

```text
REPLY    -> REACHABLE
NO_REPLY -> UNREACHABLE
ERROR    -> UNKNOWN
```

This is a one-attempt baseline, not a hidden retry/hysteresis contract.

Local failures such as generation mismatch, process prerequisite failure or ping execution
error return ERROR, not NO_REPLY. ERROR therefore never becomes remote UNREACHABLE.

## 6. Linux technical identity

Linux runtime assembly supplies one authoritative technical process identity.

Network policy receives:

```text
LinuxLocalProcessConfig
    uid
    ct_mark
```

Probe execution receives the same `LinuxLocalProcessConfig` plus process-only values such
as gid and executable path.

The semantic AvailabilityProbeSetRequest contains none of these Linux values.

The uid must not be independently duplicated in Adapter and Driver configuration.

## 7. ping socket prerequisite

The first Linux Driver uses capability-free ping sockets.

Before each single-shot attempt it idempotently writes and freshly verifies the
namespace-local `net.ipv4.ping_group_range` for its configured gid.

This prerequisite belongs to process execution, not NetworkRulesAdapter.

The current Driver does not restore an unknown previous value after each attempt.
Shutdown ownership can be added when the complete Manager lifecycle is implemented.

## 8. Logical probes and physical planes

Logical identity:

```text
probe_id
```

Network plane identity used by ProbeRulesCalculator:

```text
(mechanism, InterfaceIdentity, target)
```

Several logical probes may therefore share one physical network plane.

Timing/hysteresis is explicitly per logical `probe_id`, not per physical plane.
`AvailabilityProbeRequest.policy` therefore does not participate in
`ProbeRulesCalculator` output. Two logical probes sharing one plane may have different
cadence, timeout and thresholds.

Execution deduplication remains a future optimization only if it preserves each logical
probe contract.

## 9. Implemented rules-control slice

The first executable AvailabilityProbeManager slice is implemented independently of
scheduling cadence.

It owns:

- latest accepted full AvailabilityProbeSetRequest;
- semantic idempotence of repeated equivalent snapshots;
- current desired ProbeRulesCalculator output;
- NetworkRulesAdapter owner lifecycle;
- ProbeRulesState calculation;
- owner-wide rules-readiness epoch;
- UNKNOWN publication while no authoritative probe evidence exists;
- deterministic rules audit/repair;
- fail-closed invalidation when a probe_id leaves the desired set.

A deterministic rules audit pass is defined independently of scheduling cadence:

```text
renew NetworkRules
        |
        v
calculate ProbeRulesState
        |
        +-- READY ----------------------> rules usable
        |
        +-- UNKNOWN / INVALID
                |
                v
        apply current desired rules
                |
                v
        obtain fresh state again
```

Probe execution consumes only the READY branch.

Rules audit is also performed as part of each attempted probe validity envelope.

The Manager also exposes `evaluate_once()` as the minimal direct policy-bearing boundary. It reuses
`attempt_once()` and materializes only the minimal one-attempt verdict mapping. The raw
`attempt_once()` API remains policy-free and independently testable.

Equivalent full snapshots are order-insensitive by probe_id and do not create a new
readiness epoch or force structural reapply when the current rules remain READY.

When a probe_id is removed from the desired full snapshot, the Manager publishes one final
UNKNOWN state with no observation generation before forgetting that probe locally. This
prevents a latest-value subscriber from retaining stale REACHABLE/UNREACHABLE evidence for
a probe that is no longer requested.

## 10. Event publication

Executable payload types:

```text
AvailabilityProbeState
    UNKNOWN | REACHABLE | UNREACHABLE

ProbeObservationGeneration
    opaque Manager-local positive sequence

AvailabilityProbeStateInfo
    probe_id
    state
    reason/details
    observation_generation
```

AvailabilityProbeStateInfo is current state per logical `probe_id`.

Until both conditions hold:

1. matching READY probe rules generation;
2. valid current probe evidence for that generation;

the published availability state is UNKNOWN rather than inferred failure.

A result collected under an older rules/interface generation is stale evidence.

UNKNOWN carries no authoritative observation generation.
REACHABLE/UNREACHABLE must carry the ProbeObservationGeneration under which their evidence
was accepted.


## 11. Single-attempt validity envelope

The generic lower semantic Driver contract is:

```text
ProbeDriver.execute(
    AvailabilityProbeRequest,
    explicit timeout_seconds
) -> ProbeAttemptResult

ProbeAttemptOutcome
    REPLY | NO_REPLY | ERROR
```

`LinuxIcmpProbeDriver` is the first concrete implementation.

The implemented `attempt_once(probe_id, timeout_seconds=...)` path does not feed a raw
outcome into result/hysteresis policy based only on a pre-attempt READY observation.

Implemented order:

```text
fresh READY epoch
    -> capture current ProbeObservationGeneration
    -> ProbeDriver.execute(...)
    -> NetworkRulesAdapter.renew_state(self)
    -> ProbeRulesStateCalculator
    -> require rules still READY for the captured epoch
    -> only then pass REPLY / NO_REPLY to result policy
```

If the post-attempt observation is UNKNOWN/INVALID, the current epoch ends and
`attempt_once()` returns no `ProbeAttemptObservation`. Later repair cannot retroactively
validate that attempt.

When both checks remain READY in the same epoch, the method returns a
`ProbeAttemptObservation` containing the raw `ProbeAttemptResult`.

`evaluate_once()` is layered strictly above that raw boundary:

```text
attempt_once()
    |
    +-- no valid observation ---------> keep/publish UNKNOWN
    |
    +-- REPLY ------------------------> REACHABLE
    +-- NO_REPLY ---------------------> UNREACHABLE
    +-- ERROR ------------------------> UNKNOWN
```

A READY rules audit preserves an already authoritative REACHABLE/UNREACHABLE publication
when its `observation_generation` is still the current Manager epoch. Audit must not create
a transient UNKNOWN before every new attempt.

ProbeAttemptOutcome.ERROR is a local execution failure and is never directly equivalent to
remote UNREACHABLE.

## 12. Minimal verdict baseline

The current executable baseline deliberately chooses no counters and no timers.

One valid attempt is enough to publish one current verdict for the active readiness epoch:

- REPLY publishes REACHABLE with the current ProbeObservationGeneration;
- NO_REPLY publishes UNREACHABLE with the current ProbeObservationGeneration;
- ERROR publishes UNKNOWN without an observation generation;
- an attempt discarded by the validity envelope publishes no remote verdict.

Repeated semantically identical verdicts are publication-idempotent.

Any physical rules transition that opens a new readiness epoch invalidates older
REACHABLE/UNREACHABLE publications for the Manager. A logical-only request change invalidates
only the affected `probe_id` publication while unchanged logical probes retain evidence
from the still-current rules epoch.

This baseline is intentionally replaceable by a later retry/hysteresis policy without
changing ProbeDriver or ProbeAttemptObservation.

## 13. Per-probe cadence and hysteresis

The next executable layer is a normalized optional `AvailabilityProbePolicy` attached to
each logical `AvailabilityProbeRequest`:

```text
interval_seconds
retry_interval_seconds
timeout_seconds
failure_threshold
recovery_threshold
```

`policy=None` means that the logical probe is not autonomously scheduled by the Manager.
It remains available to explicit `evaluate_once()` callers. This is useful for staged
assembly and tests; production runtime assembly may require policy for probes that are
expected to run autonomously.

Threshold defaults are 1/1, preserving the already-agreed single-attempt verdict baseline.
No arbitrary default wall-clock values are invented: interval, retry interval and timeout
must be supplied explicitly by the normalized policy producer.

The Manager owns only deterministic scheduling state. It does not sleep and does not own a
thread or event loop. The outer runtime calls:

```text
run_due(monotonic_now)
```

and the Manager executes all currently due probes serially in deterministic `probe_id`
order.

Scheduling semantics:

- a newly scheduled probe is immediately due;
- after a stable valid verdict/check, the next attempt uses `interval_seconds`;
- while contrary evidence has not yet reached its transition threshold, the next attempt
  uses `retry_interval_seconds`;
- local ERROR or an attempt rejected by the validity envelope also uses
  `retry_interval_seconds`;
- matching evidence cancels an incomplete opposite streak;
- a new Manager readiness epoch resets all threshold streaks and due-state.

Hysteresis is verdict retention, not UNKNOWN insertion:

```text
REACHABLE
    +-- NO_REPLY x (failure_threshold - 1) --> remain REACHABLE
    +-- NO_REPLY x failure_threshold       --> UNREACHABLE

UNREACHABLE
    +-- REPLY x (recovery_threshold - 1)   --> remain UNREACHABLE
    +-- REPLY x recovery_threshold         --> REACHABLE
```

From UNKNOWN, the corresponding threshold must also be satisfied before publishing an
authoritative REACHABLE/UNREACHABLE verdict.

A local Driver ERROR remains exceptional evidence and immediately publishes UNKNOWN,
clearing pending streaks. It is never counted toward remote failure hysteresis.

A policy-only or other logical-only change invalidates current evidence, streaks and due
state only for the changed `probe_id`. If the physical `NetworkRulesSpec` is unchanged,
the Manager preserves the current rules-readiness epoch and freshly audits the existing plane
rather than forcing a structural apply.

A physical probe-plane change still invalidates the owner-wide rules epoch and therefore all
authoritative probe evidence carried by that epoch.

No jitter, parallel attempts, in-flight cancellation or stale-verdict time-to-live is
defined by this slice.

## 14. Still intentionally open

The remaining lower-domain evidence gate before production conntrack remediation is
EXP-026 Debian 13 target confirmation. EXP-025 is already target-confirmed
STALE-INHERITANCE, and the intended Debian 13 `/usr/bin/ping` executable is confirmed.

The following still require an explicit later contract:

- user-facing timing/policy grammar and normalization;
- jitter;
- outer runtime tick/event-loop integration;
- parallel attempt policy, if any;
- cancellation on a superseding request while a synchronous Driver call is already in flight;
- stale-verdict time-to-live, if any beyond active cadence;
- shutdown cleanup of process runtime prerequisites.

The observation-generation representation is no longer open at the semantic level:
AvailabilityProbeManager uses an owner-wide rules-readiness epoch as described above.

These timing/result-policy choices are not inferred from payload policy or from EXP-024.

## 15. Evidence

Current evidence:

- EXP-024: selective local-process routing/filter mechanism PASS on Debian 13;
- production LOCAL_PROCESS NetworkRules backend: apply/renew/dataplane PASS;
- EXP-025: Debian 13 target-confirmed STALE-INHERITANCE across same-name/new-ifindex
  replacement;
- EXP-026: privileged-CI probe-class selective conntrack cleanup PASS; Debian 13 target
  confirmation pending;
- projected generation loss retains dedicated uid guard across another owner's structural
  reconcile;
- ProbeRulesStateCalculator: unit PASS;
- LinuxIcmpProbeDriver: unit + privileged CI integration PASS;
- LinuxIcmpProbeDriver with `/usr/bin/ping`: Debian 13 target LP1..LP7 PASS.
