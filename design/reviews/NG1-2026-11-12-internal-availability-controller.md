# Internal review — availability controller lifecycle owner

Date: 2026-11-12

Role: internal expert review under `CONTINUOUS-DEVELOPMENT.md`.

## Scope

Reviewed AvailabilityController as the future process-local owner of:

- ProbeEvidenceStore;
- SupervisedAvailabilityState;
- explicit hysteresis/freshness policies;
- concurrent probe publication versus serialized availability reconciliation.

The controller is not connected to production Planner/runtime.

## Finding F1 — evidence and consumed state require one lifecycle owner

Severity: high future-integration correctness.

The preceding review identified that restarting the evidence sequence independently from
consumed sample/history state would invalidate exactly-once assumptions.

### Disposition

Accepted and fixed by construction.

AvailabilityController creates and owns both domains. Recreating the controller resets
both together. Neither domain has a persistence API.

## Finding F2 — failed supervision must not partially commit/prune controller state

Severity: high transactional correctness.

Missing/stale/corrupt evidence may fail reconciliation. Such failure must not update
hysteresis state or destroy evidence needed for diagnosis/recovery.

### Disposition

Correct as implemented.

The controller:

1. snapshots evidence;
2. performs complete supervised reconciliation;
3. only after success commits next state;
4. only after success prunes disappeared-generation samples.

Regression tests prove stale/missing failure leaves state/evidence unchanged.

## Finding F3 — concurrent probe publication must remain safe across reconcile

Severity: medium concurrency correctness.

A probe can complete while reconciliation is using an older immutable evidence snapshot.

### Disposition

Correct as implemented.

ProbeEvidenceStore serializes publication internally. Reconciliation consumes one immutable
snapshot. A concurrently published newer sample remains in the store and is consumed on the
next reconcile.

No shared mutable TimedProbeSample object exists.

## Finding F4 — current production Planner availability-provider boundary is not suitable for direct wiring

Severity: high integration architecture.

Current Planner calls:

    AvailabilityProvider(EnvironmentSnapshot)

before DeviceEngine has produced the normalized bound-interface snapshot.

Future active probing/supervision should operate on concrete currently bound interface
generations, not rediscover Device bindings independently from raw namespace interfaces.

Directly wiring AvailabilityController through the existing provider signature would either:

- duplicate DeviceEngine selector/quota logic in DeviceManager; or
- require samples for unrelated namespace interfaces.

### Disposition

Accepted as an integration gate.

No Planner refactor is made in this review unit. Before production activation, the
availability boundary must be moved/extended so DeviceEngine first establishes binding
identity and the availability layer consumes that normalized bound set.

This is a production-core refactor and must be reviewed with the chosen stale-detector
policy, not guessed now.

## Finding F5 — stale/missing detector consequence remains product policy

Severity: human-decision boundary.

The controller correctly raises DetectorSupervisionError. It intentionally does not decide
whether the runtime should:

- globally contain/restart;
- preserve last normalized state while reporting degraded health;
- or use another explicitly designed state.

Mapping detector failure directly to UNAVAILABLE is specifically not implied by raw
EXP-019/020 evidence and would violate the current "positive evidence" principle.

### Disposition

Requires human agreement before production integration.

## Test/evidence status

Rootless NG1 and RC3 workflows are green on the reviewed controller baseline.

Tests prove:

- distinct evidence drives hysteresis;
- repeated reconcile without a new sample does not;
- stale/missing errors are transactional;
- successful reconcile prunes disappeared generations;
- controller replacement resets both ephemeral domains;
- invalid typed inputs fail at the boundary.

## Rust-alignment assessment

The ownership model maps directly to one process-owned controller with:

- shared thread-safe evidence registry;
- serialized state transition;
- immutable snapshots/results;
- explicit error variants.

No persistence/clock/probe protocol is hidden in the normalized state.

## Verdict

AvailabilityController is approved with no remaining recommendation in its own scope.

Production integration is blocked on two deliberately separate decisions:

1. stale/missing detector policy;
2. Planner boundary refactor to consume normalized bound generations.

Do not wire the controller to production until both are reviewed.
