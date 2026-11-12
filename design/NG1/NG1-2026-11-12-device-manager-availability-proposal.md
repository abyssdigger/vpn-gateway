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

## 5. Detector missing/stale policy — human decision

A stale/missing detector sample means the **control-plane detector is unhealthy**. It is
not positive evidence that the VPN path itself is unavailable.

Three possible policies:

### A. Fatal detector health — recommended first production policy

On DetectorSupervisionError for any currently bound generation:

- availability controller reports unhealthy;
- ROU runtime treats DeviceManager health failure like another supervised control-plane
  failure;
- forwarding is contained fail-closed;
- systemd restart policy attempts recovery;
- runtime does not silently reuse stale availability.

Pros:
- strongest invariant;
- never invents UNAVAILABLE;
- stale control-plane state cannot steer traffic indefinitely;
- consistent with existing fatal supervised-service health behavior.

Cons:
- one failed availability worker can temporarily stop all ROU forwarding;
- bad probe configuration can create a restart loop, which must be diagnosable.

### B. Freeze last stable normalized availability

On detector supervision failure:

- keep last verified normalized Availability;
- mark DeviceManager/status degraded;
- continue forwarding.

Pros:
- control-plane detector failure does not cause total outage.

Cons:
- a dead path may remain AVAILABLE/preferred indefinitely;
- failure detection silently stops working;
- stale state can outlive the condition it described.

Not recommended as the default first policy.

### C. Treat detector failure as UNAVAILABLE

On detector supervision failure, demote the affected interface.

Pros:
- localizes impact to one path.

Cons:
- violates the current "positive path evidence" meaning of UNAVAILABLE;
- conflates detector failure with network failure;
- a broken detector can change routing even when the VPN path is healthy.

Not recommended.

### Recommendation

Adopt **A — fatal detector health** for the first integrated DeviceManager.

A later independently supervised per-Device worker-restart model could reduce blast radius
without redefining Availability semantics.

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
- when absent: existing UNKNOWN behavior, no detector;
- when present: one explicit ICMP target, interval, timeout, failure threshold and recovery
  threshold;
- freshness limit derived and validated from the scheduling contract only after its formula
  is explicitly agreed.

This is deliberately a proposal, not normative TOML syntax.

## 7. Required implementation sequence after agreement

1. extend durable Planner state with last verified normalized Availability;
2. split DeviceEngine binding projection from availability decoration;
3. seed AvailabilityController from durable normalized state on restart;
4. add one supervised availability provider consuming only bound generations;
5. implement chosen detector-health policy;
6. add user-facing Device availability schema;
7. implement protocol-specific active probe worker(s);
8. rootless review;
9. privileged availability-transition integration;
10. real WireGuard/OpenConnect target validation.

## 8. What remains deliberately postponed

EXP-014 multi-interface remote-initiated flow pinning remains unrelated and postponed.

EXP-015 real TCP MTU/MSS signoff remains a separate production-readiness gate requiring the
real payload topology.

EXP-018 systemd/PID1 deployment smoke remains a live Debian 13 deployment gate.
