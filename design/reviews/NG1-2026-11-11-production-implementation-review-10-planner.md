# Production implementation review 10 — PlannerEngine reconciliation

Role: external expert review focused on end-to-end control-plane correctness, fresh
observation semantics, verified commit boundaries, crash behavior and Rust migration.

## Scope

Reviewed `planner.py`, Planner lifecycle tests and all production modules it coordinates:
DeviceEngine, TrafficRuntimeState, kernel desired/mutation/verification, namespace
prerequisites, filter, NAT provider boundary and command backend.

## Findings

### F1 — availability evidence must be fresh per environment snapshot

The first Planner version accepted one availability mapping for the whole reconcile.
That could reuse pre-barrier Device health evidence after an interface transition or a
long repair cycle.

Severity: medium, observation correctness.

Recommendation: accept an availability provider evaluated independently for every fresh
EnvironmentSnapshot used to project desired state.

Disposition: fixed with `AvailabilityProvider`.

### F2 — delayed metric reuse requires an immediate second reconcile

Verified removal commits may free a metric slot while a candidate remains
`waiting_for_slot`. No new kernel event is guaranteed after that commit.

Severity: medium, liveness.

Recommendation: make the result explicitly request another immediate reconcile rather
than waiting for an event.

Disposition: fixed with `PlannerResult.needs_immediate_reconcile`.

### F3 — durable runtime-state commit must precede forwarding reopen

Stable candidate/metric history is part of verified control-plane state. If forwarding
were opened and the daemon crashed before persisting that history, restart could allocate
different normal metrics for a still-continuous interface generation.

Severity: high, crash consistency.

Recommendation: provide a verified-state persistence callback and invoke it after complete
closed-barrier verification but before `ip_forward=1`. Persistence failure must remain
fail-closed. The same callback may checkpoint already-verified steady/open state.

Disposition: fixed. Planner now persists verified state before exposure.

### F4 — duplicate live verification in crash-reopen path

The initial reopen branch called the complete verifier and then separately re-read
kernel/filter/NAT state. Besides unnecessary work, that could compare different live
generations.

Severity: low/medium, consistency.

Recommendation: use one complete verification generation.

Disposition: fixed.

## Whole-scope review

The resulting lifecycle is:

1. fresh observe;
2. fresh Device availability normalization;
3. pure projection;
4. if already completely verified/open: durable checkpoint and commit;
5. if completely verified/closed: durable checkpoint, open, fresh verify;
6. otherwise close forwarding;
7. fresh barrier snapshot and reprojection;
8. prerequisites;
9. route/RPDB, filter and selected NAT-provider apply;
10. fresh closed-state verification;
11. durable runtime-state persistence;
12. open forwarding;
13. fresh final verification;
14. commit result.

Any exception after entering Planner control causes a best-effort forwarding close.
Interface churn during transition requests an immediate fresh retry rather than silently
continuing with mixed generations.

## Rust-alignment review

Planner dependencies are explicit providers/callbacks rather than global singletons.
Projection types are immutable and error classes map naturally to Rust Result variants.
The one-pass reconcile function is suitable for later conversion to a state-machine enum
without changing ownership boundaries.

## Verdict

Approved after F1–F4 corrections. No remaining recommendation in Planner scope.
