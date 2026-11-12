# Internal review — availability collector boundary

Date: 2026-11-12

Role: internal expert review under CONTINUOUS-DEVELOPMENT.md.

## Scope

Reviewed the future availability plumbing introduced after EXP-019 and EXP-020:

- DeviceEngine binding ownership;
- Planner availability input;
- runtime/runtime-app composition;
- generation identity;
- interaction with persistent shadow fallback;
- future DeviceManager activation boundary.

## Finding F1 — snapshot-only AvailabilityProvider was too weak for proven evidence

Severity: medium architecture/API.

EXP-019 and EXP-020 proved that process/interface presence is not sufficient positive path
liveness evidence and that useful evidence may require an active tunnel-bound probe.

The previous provider shape was effectively a pure function of EnvironmentSnapshot. A
closure could technically perform hidden I/O, but that would make active probing an
implicit side effect inside policy projection and blur the observation boundary.

### Disposition

Accepted and fixed.

A dedicated `AvailabilityCollector` boundary now receives:

- namespace;
- host command backend;
- fresh EnvironmentSnapshot;
- concrete DeviceBindingSnapshot already selected by DeviceEngine.

This makes active/protocol-specific observation explicit without inventing policy.

## Finding F2 — availability collection must not participate in binding selection

Severity: high ownership consistency.

If a future collector had to rediscover interfaces from selectors/config, it could duplicate
or diverge from DeviceEngine historical candidate ordering and quota semantics.

### Disposition

Accepted and fixed.

Planner ordering is now:

1. fresh environment observation;
2. DeviceEngine selects bound/over-quota concrete generations with availability UNKNOWN;
3. optional collector observes only those selected generations;
4. normalized availability annotates the immutable binding snapshot;
5. TrafficEngine/routing projection consumes the annotated bindings.

Availability cannot reorder, promote, bind or unbind interfaces.

## Finding F3 — over-quota candidates should not acquire availability semantics

Severity: low/medium future-complexity.

Classifying over-quota candidates would create an unused second state space and imply
pre-warming semantics that schema version 1 does not define.

### Disposition

Accepted and fixed.

Collector results may reference only current `bindings.bound` identities. Evidence for a
stale generation or over-quota identity is rejected. Over-quota candidates remain UNKNOWN
until DeviceEngine promotes them.

## Finding F4 — generation identity must survive availability evidence

Severity: high safety.

A probe result for retired `vpns00@ifindex=10` must never classify a fresh
`vpns00@ifindex=20`.

### Disposition

Accepted and fixed.

Availability normalization keys evidence by `InterfaceIdentity(ifname, ifindex)` and
rejects any identity not present in the current bound generation set.

Rootless regression coverage includes same-name stale-generation rejection.

## Finding F5 — collector plumbing must not silently activate production UNAVAILABLE

Severity: high product/safety boundary.

The existing runtime state schema does not persist sufficient availability history to prove
all future AVAILABLE/UNAVAILABLE transitions incrementally, and product semantics for probe
target, cadence and failure/recovery thresholds are not yet defined.

### Disposition

Accepted and explicitly gated.

Schema-v1 production instantiates no real collector. The runtime composition accepts an
injected collector only as future/test plumbing.

Before DeviceManager activates positive UNAVAILABLE classification, a separate reviewed
product decision must define:

- probe target/admission semantics;
- cadence/timeouts;
- failure and recovery thresholds;
- transport-specific versus common policy;
- durable availability-history requirements and transition proof.

EXP-019/020 provide raw evidence, not that policy.

Collector implementation errors remain ordinary Planner/runtime failures and therefore
fail closed. A valid collector should express uncertain evidence as normalized UNKNOWN,
not by throwing an exception.


## Finding F6 — status test fixture still used the pre-refactor projector signature

Severity: low test-maintenance.

The first exact-head CI run failed four status tests because their helper called the old
`compile_planner_projection(config, committed, environment, provider, address)` shape.
Production status code itself was not implicated.

### Disposition

Accepted and fixed.

The status fixture now follows the same explicit sequence as production projection:

1. DeviceEngine reconciles bindings from the environment;
2. the resulting DeviceReconcileResult is passed to `compile_planner_projection`.

This adds another regression against re-coupling binding discovery to availability policy.

## Rust-alignment review

The new boundary is preferable for a Rust port:

- binding selection remains one immutable DeviceEngine result;
- availability is a separate evidence collector trait;
- evidence uses generation-typed identities;
- projection remains pure after evidence collection;
- schema-v1 can use a no-collector option without hidden behavior.

## Tests/evidence

Added rootless coverage for:

- stale same-name generation rejection;
- over-quota result rejection;
- normalized enum enforcement;
- immutable binding order/identity preservation;
- collector receiving DeviceEngine-selected bound/over-quota generations;
- runtime composition forwarding the injected collector.

The first exact-head CI attempt exposed F6 and was corrected. The corrected exact-head
GitHub CI run is the acceptance gate for this review unit.

## Verdict

All source and test findings are resolved.

The review unit is approved subject to green rootless and privileged CI on the corrected
head. Production
DeviceManager availability policy remains deliberately outside this unit.
