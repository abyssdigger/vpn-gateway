# NG2 review — payload tails from superseded probing designs

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-payload-probing-tail-review-40m`  
**Scope:** payload-domain code/contracts only; no runtime assembly

## Review question

After simplifying availability into an optional priority modifier, does the payload domain
still contain artifacts from earlier designs where probing/evidence was part of the main
runtime intent?

## Verdict

**FINDINGS — cleanup required before runtime assembly.**

The payload rules/state projection itself is mostly clean, but the current
`PayloadTrafficManager` integration still carries several concrete probe-domain details
that are no longer justified.

## F1 — availability boundary leaks into the structural payload Request contract

**Severity:** architecture / ownership

Current:

```text
PayloadProfileRequest
    ...
    ordered_paths
    no_problem_prefix_length
```

`no_problem_prefix_length` is not structural payload intent. It is transient current
priority-materialization state derived from the optional availability tool.

This contradicts the desired boundary:

```text
PayloadTrafficStateRequest = structural/admin payload intent only
```

and also makes `PayloadRulesCalculator` accept an availability-derived field.

### Recommended correction

Remove `no_problem_prefix_length` from `PayloadProfileRequest`.

Keep the external/configured payload request pure:

```text
name
direction
destinations
ordered configured PayloadPath values
```

Inside `PayloadTrafficManager`, derive an internal routing-priority projection and apply
it only while building the lower `NetworkRulesSpec`.

The lower routing contract may still carry a technical prefix/gap hint if Linux
materialization genuinely needs it, but that hint must not be part of the public payload
Request type.

## F2 — PayloadTrafficManager knows the complete physical probe model

**Severity:** architecture / unnecessary coupling

Current imports and state include:

- `AvailabilityProbeSetRequest`;
- `AvailabilityProbeRequest`;
- `LogicalProbeChannel`;
- `ProbeGoodNewsInfo`;
- `ProbeTickInfo`;
- target IPv4 address indirectly;
- ProbeMechanism indirectly.

Payload priority does not need target or mechanism. It needs only:

```text
availability channel id
payload path identity
enabled
hysteresis thresholds
good-news count
tick fact
Profile/channel assignment
```

The Agent already rejects a stale physical worker result against the current physical
generation/plane before publishing good news. Payload therefore does not need to
revalidate physical target/mechanism.

### Recommended correction

Define a small availability-facing payload contract independent of probe transport, e.g.:

```text
AvailabilityPriorityChannel
    channel_id
    path
    enabled
    failure_ticks
    recovery_good_news

AvailabilityGoodNews(channel_id)
AvailabilityTick(channel_id)
ProfileAvailabilityAssignment(profile_name, channel_ids)
```

The runtime assembly layer maps current logical probe configuration/Agent output into this
contract.

No target, mechanism, attempt identity, timestamp or epoch crosses into payload.

## F3 — interval_seconds is bundled into payload hysteresis policy

**Severity:** unnecessary coupling

`AvailabilityChannelPolicy` currently contains:

```text
interval_seconds
failure_ticks
recovery_good_news
```

The collector state machine uses only the two thresholds. The interval belongs to probe
execution cadence.

As a result, PayloadTrafficManager stores and compares timing data that it never uses
directly.

### Recommended correction

Separate:

```text
probe execution cadence:
    interval_seconds

payload availability hysteresis:
    failure_ticks
    recovery_good_news
```

A cadence change may still cause the runtime assembly/configuration path to reset
hysteresis progress if policy says so, but the payload domain does not need to own the
numeric interval.

## F4 — ProfileProbeAssignment is named and keyed as a probe-domain object

**Severity:** terminology / ownership

Current:

```text
ProfileProbeAssignment(profile_name, probe_ids)
```

At the payload boundary this is no longer about physical probes. It associates optional
availability channels with paths/Profile priority policy.

### Recommended correction

Rename/project to something like:

```text
ProfileAvailabilityAssignment(profile_name, channel_ids)
```

The probe subsystem may still use `probe_id` internally. The payload domain should not.

## F5 — availability boundary is emitted even when availability is absent

**Severity:** semantic residue

Current `_calculate_effective_request()` always computes:

```text
no_problem_prefix_length = len(configured_order) - len(problem_paths)
```

With no availability configuration/assignment:

```text
problem_paths = {}
no_problem_prefix_length = N
```

The Linux result is contiguous and therefore harmless, but every payload Profile is still
semantically marked with an availability-derived boundary even when the optional tool is
not in use.

### Recommended correction

If no enabled availability channel participates in a Profile, do not create an
availability-priority boundary at all.

The pure structural payload order should pass through unchanged.

If the lower generic routing contract retains an optional prefix/gap hint:

```text
availability inactive -> hint absent
availability active   -> derived current prefix value
```

This makes "probing disabled" a true no-op rather than merely a special all-clear value.

## F6 — active documents still describe availability as part of PayloadTrafficStateRequest

**Severity:** documentation contradiction

`payload-traffic-manager.md` and `runtime-event-model.md` still say the structural
`PayloadTrafficStateRequest` contains availability channel assignment/policy.

The executable code already uses a separate `configure_availability()` path, so the docs
describe a superseded coupling.

### Recommended correction

Define two independent inputs:

```text
PayloadTrafficStateRequest
    structural/admin payload intent

AvailabilityPriorityConfig
    optional auxiliary priority input
```

Neither is nested inside the other.

## F7 — CurrentRuntimeSnapshot still lists availability_probe_states

**Severity:** dead architecture artifact

`runtime-event-model.md` still contains:

```text
CurrentRuntimeSnapshot
    ...
    availability_probe_states
```

The executable `AvailabilityProbeStateInfo` routing path was deleted in the preceding
cycle.

### Recommended correction

Remove `availability_probe_states` from the runtime-control snapshot.

Probe execution diagnostics may have a separate diagnostic/status cache, but they must not
re-enter payload priority calculation.

## F8 — payload state output is not itself contaminated by probe verdicts

**Disposition:** retain

`PayloadTrafficStateInfo` and `PayloadRulesState` contain no availability/probe state.

`observed_paths` is the actual ordered materialized routing projection. This is a valid
payload fact even when the order happened to be influenced by the optional availability
tool.

No separate "healthy", "reachable", probe verdict or evidence field should be added.

## F9 — retaining current verified effective order is justified

**Disposition:** retain

`PayloadTrafficManager` keeps the last verified effective ordering so problem paths can
preserve current relative order and route rearrangements start from a verified baseline.

This is route-priority materialization state, not probe evidence history.

It should remain, although its type should no longer be `PayloadTrafficStateRequest` once
F1 is fixed.

## F10 — the generic lower routing boundary still uses availability-flavored naming

**Severity:** low / lower-domain cleanup

`RoutingDomainSpec.no_problem_prefix_length` and some active Adapter documentation still
talk about "non-confirmed/live" tails.

The lower domain genuinely needs enough information to place the emergent free metric
slot; therefore the field itself is not necessarily obsolete.

However, after F1 the generic lower contract should use neutral routing terminology, for
example a preferred-prefix/gap-position semantic, rather than naming an availability
problem.

This is a lower-domain naming cleanup, not a reason to put the field back into payload
intent.

## Recommended cleanup order

Before runtime assembly:

1. make `PayloadTrafficStateRequest` purely structural by removing the prefix field;
2. introduce the tiny probe-independent availability-priority input contract;
3. split hysteresis thresholds from probe cadence;
4. rename ProfileProbeAssignment to an availability-channel assignment;
5. make inactive availability produce no routing-boundary hint;
6. remove stale runtime/docs references to availability inside payload Request/snapshot;
7. neutralize lower routing boundary naming if the technical hint remains necessary;
8. rerun payload + full Linux route-priority regression.

No new kernel experiment is needed: these are ownership/type cleanup changes around the
already-proven route-priority materializer.
