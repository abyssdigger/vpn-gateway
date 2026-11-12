# NG1 future DeviceManager availability — production activation proposal

Status: **PROPOSAL — requires human agreement before normative architecture/config change**

Date: 2026-11-12

Evidence baseline:

- EXP-016: ECMP hash policy prerequisite PASS;
- EXP-019: WireGuard interface/process presence is not path liveness; active path probe
  distinguished live -> unavailable -> live on the same interface generation;
- EXP-020: OpenConnect process/interface presence is not path liveness; active path probe
  distinguished live -> unavailable -> live on the same interface generation;
- protocol-neutral hysteresis, freshness supervision, exactly-once evidence consumption and
  controller ownership are implemented rootlessly but are not connected to production.

## 1. What can be considered established

The following do not require further product-policy invention:

1. availability is independent from binding presence;
2. positive UNAVAILABLE needs path/protocol evidence, not interface/process presence;
3. evidence belongs to concrete `(ifname,ifindex)` generation;
4. repeated Planner reconciliation must not count one probe multiple times;
5. detector freshness/lifecycle is distinct from an INDETERMINATE probe outcome;
6. probe timestamps/sample ids are process-local and not durable state;
7. persistent shadow fallback already exists and EXP-013 proved its route behavior.

## 2. Required Planner/DeviceEngine integration shape

Production activation should change the current ordering from:

    EnvironmentSnapshot
        -> availability_provider(raw snapshot)
        -> DeviceEngine binding

to:

    EnvironmentSnapshot
        -> DeviceEngine binding identity/quota
        -> bound concrete generations
        -> DeviceManager availability controller
        -> availability-decorated binding snapshot
        -> TrafficEngine

Reason:

- DeviceManager must not duplicate selector/quota logic;
- over-quota/unrelated namespace interfaces do not need path probes;
- availability evidence is meaningful only for concrete bound generations.

This refactor is technical, not a user-facing policy decision.

## 3. Durable versus ephemeral availability state

Proposal:

### Durable Planner state

Persist only the last **verified normalized Availability** for each continuously bound
concrete interface generation:

    UNKNOWN | AVAILABLE | UNAVAILABLE

Purpose:

- reconstruct the previous verified kernel route generation;
- classify availability-only transitions incrementally;
- preserve the last stable routing decision across daemon restart.

Do not persist:

- sample ids;
- monotonic timestamps;
- partial success/failure streak counters.

### Ephemeral DeviceManager state

On DeviceManager/controller restart:

- sample sequence resets;
- timestamps reset;
- hysteresis streaks reset;
- the tracker may be seeded with the last durable normalized Availability for surviving
  concrete generations, with both streak counters zero;
- fresh current-generation evidence is still required before DeviceManager is considered
  healthy.

This preserves stable route preference without pretending old probe timestamps are fresh.

## 4. Availability-only kernel transition

Once previous normalized availability is durable, a binding-stable availability transition
is a provable incremental route transition:

AVAILABLE/UNKNOWN -> UNAVAILABLE:
- remove that member's normal route;
- persistent shadow fallback already exists;
- terminal Profile blackhole remains continuously present.

UNAVAILABLE -> AVAILABLE:
- add the member's stable normal route;
- fallback remains unchanged.

No global ip_forward barrier is required for this proven transition. Structural/unknown
route/policy drift remains barriered.

EXP-013 already provides the relevant kernel behavior evidence; additional unit/integration
coverage is required, but no new kernel hypothesis is currently identified.

## 5. Detector readiness and local quarantine — human decision

The first draft considered global runtime failure when detector evidence becomes
missing/stale. Internal review rejected that as unnecessarily broad when the failure can be
scoped to one concrete monitored binding.

### Proposed separate readiness axis

Availability retains its current meaning:

    UNKNOWN | AVAILABLE | UNAVAILABLE

Add an orthogonal detector-readiness state for monitored bindings:

    UNMONITORED
    PENDING
    READY
    FAILED

Meaning:

- UNMONITORED: no availability detector is configured for the Device; current schema-v1
  UNKNOWN behavior is unchanged;
- PENDING: detector is configured, but this concrete generation does not yet have trusted
  fresh evidence in the current controller lifecycle;
- READY: supervised evidence is fresh and normalized Availability is meaningful;
- FAILED: previously monitored evidence is missing/stale or the per-binding detector is
  unhealthy.

### Payload eligibility

For TrafficEngine:

- UNMONITORED -> payload-eligible using existing UNKNOWN semantics;
- READY -> payload-eligible using existing UNKNOWN/AVAILABLE/UNAVAILABLE tiers;
- PENDING -> no payload route/ACCEPT/fallback membership;
- FAILED -> no payload route/ACCEPT/fallback membership.

PENDING/FAILED bindings remain DeviceEngine-visible. Probe/transport recovery may continue;
only payload eligibility is quarantined.

This gives local fail-closed behavior without claiming the VPN path itself is
UNAVAILABLE and without stopping unrelated Devices/Profiles.

### Why not map detector failure to UNAVAILABLE

UNAVAILABLE means positive path evidence justified demotion. Detector failure is evidence
about the control plane, not the VPN path.

Mapping detector failure to UNAVAILABLE would:

- weaken that semantic distinction;
- keep the binding in persistent fallback;
- allow last-resort payload to use a path whose evidence is not trustworthy.

Local quarantine is therefore preferred.

### Why not globally stop ROU

A single per-binding detector failure is scopeable. Global ip_forward=0 would interrupt
unrelated verified Profiles/Devices and would reintroduce the broad-barrier behavior the
project deliberately removed from ordinary lifecycle transitions.

Global runtime containment remains appropriate for failures that cannot be scoped safely,
for example corruption of the DeviceManager/controller itself or owned-state integrity
loss.

### New binding and restart behavior

For a detector-enabled newly bound generation with no durable stable availability:

1. binding is visible to DeviceEngine;
2. readiness begins PENDING;
3. no payload state is generated for it;
4. fresh supervised probe samples advance hysteresis;
5. while normalized Availability remains UNKNOWN, readiness remains PENDING;
6. the first stable AVAILABLE or UNAVAILABLE decision establishes READY;
7. READY then selects the existing normal/fallback tier.

This prevents a brand-new monitored path from entering the normal tier merely because one
fresh failure sample has not yet reached a configured failure threshold.

On controller/runtime restart:

- durable last stable AVAILABLE/UNAVAILABLE may seed surviving concrete generations for
  hysteresis continuity;
- probe ids/timestamps/streaks reset;
- monitored generations begin PENDING regardless of the durable seed;
- a fresh supervised sample confirms the new controller lifecycle and may re-establish
  READY while retaining the seeded stable Availability until hysteresis changes it;
- a durable UNKNOWN seed is not sufficient for READY: the generation remains PENDING until
  a stable AVAILABLE/UNAVAILABLE decision is reached.

Thus persisted Availability reconstructs stable history; it never substitutes for fresh
detector readiness.

### Recommendation

Adopt this separate readiness/local-quarantine model for the first integrated
DeviceManager.

This recommendation changes product semantics and therefore requires human agreement
before normative architecture or production Planner changes.

## 6. User-facing active-probe policy — human decision

EXP-019/020 prove an active tunnel-bound probe can supply useful raw evidence, but they do
not prove universal defaults.

A minimal explicit schema could conceptually require, per Device:

    availability probe type
    probe target IPv4
    probe interval
    per-probe timeout
    failure threshold
    recovery threshold
    freshness limit

No defaults should be invented until agreed.

Open questions:

1. Is first production probe type ICMP-only, or must TCP/UDP probes be supported from the
   first schema?
2. Is one Device-level probe target sufficient, or should multiple targets be supported?
3. Should freshness limit be explicit, or derived from cadence/timeout?
4. Should availability detection be optional per Device, with omitted detection preserving
   current UNKNOWN behavior indefinitely?

Recommended simplest first slice:

- availability detection optional;
- when absent: readiness UNMONITORED and existing UNKNOWN behavior;
- when present: one explicit ICMP target, interval, timeout, failure threshold, recovery
  threshold and freshness limit;
- no hidden/default timing values in the first schema.

An explicit freshness limit is preferred over a derived magic formula in schema version 1.
A later schema may add safe shorthands once operating evidence supports them.

This is deliberately a proposal, not normative TOML syntax.

## 7. Required implementation sequence after agreement

1. add detector-readiness domain state without changing Availability semantics;
2. extend durable Planner state with last verified normalized Availability only;
3. split DeviceEngine binding projection from availability/readiness decoration;
4. seed AvailabilityController from durable normalized state while forcing monitored
   generations to PENDING after restart;
5. make TrafficEngine consume only payload-eligible binding generations;
6. classify readiness/availability-only route changes as proven incremental transitions
   when previous generation is known;
7. add user-facing Device availability schema;
8. implement protocol-specific active probe worker(s);
9. add status/diagnostics for UNMONITORED/PENDING/READY/FAILED;
10. rootless expert review;
11. privileged availability/readiness transition integration;
12. real WireGuard/OpenConnect target validation.

No production Planner/runtime wiring occurs before human approval of the readiness model
and first user-facing probe policy.

## 8. What remains deliberately postponed

EXP-014 multi-interface remote-initiated flow pinning remains unrelated and postponed.

EXP-015 real TCP MTU/MSS signoff remains a separate production-readiness gate requiring the
real payload topology.

EXP-018 systemd/PID1 deployment smoke remains a live Debian 13 deployment gate.
