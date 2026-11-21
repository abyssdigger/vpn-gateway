# VPN-GATE NG3 — bounded controller stop / owned-domain cleanup review

**Date:** 2026-11-17  
**Cycle branch:** `ng3-design-cycle-20261117-stop-cleanup-restart-35m`

## Scope

Review the first executable bounded stop operation for the currently implemented controller
lifetime:

- retained lifetime lock from READY startup;
- protective forwarding containment;
- owned managed-domain teardown;
- cleanup failure classification;
- lifetime-lock release ordering;
- live stop -> clean restart evidence.

This unit does not introduce runtime Manager/Agent shutdown because no such long-lived runtime
owner is executable in the current startup session yet.

## Requirements

**Implements:**
- `VPNG-U005-R5.R4`;
- `VPNG-U005-R5.R5`;
- `VPNG-U005-R5.R6.R2`;
- `VPNG-U006-R6.R3`.

**Constrained by:**
- `VPNG-U001-R1.R3.C1`;
- `VPNG-U004-R4.R6.R1`;
- `VPNG-U007-R7.R1`.

## Verdict

**PASS.**

The current controller can now stop from READY with an explicit owned-network postcondition and
cannot report success merely because cleanup commands were issued.

No human product decision is required.

## Implementation

New module:

`design/NG3/code/python/rou/controller_stop.py`

Public contracts:

- `ControllerStopStatus`;
- `ControllerStopResult`;
- `stop_controller_once(...)`.

The accepted bounded sequence is:

```text
retained lifetime lock
    ->
attempt fresh ForwardingGate=DISABLED
    ->
regardless of that result, attempt destroy_managed_network_domain(...)
    ->
fresh absence verification performed by managed-domain teardown
    ->
only after confirmed namespace + host-boundary absence release lifetime lock
```

## Finding F1 — containment failure must not suppress stronger cleanup

A failed gate observation or failed gate write does not prove that teardown is impossible.
Skipping domain removal would leave an owned host boundary and namespace merely because the
protective pre-step was uncertain.

**Disposition:** stop always attempts managed-domain teardown after the bounded containment
attempt.

If teardown succeeds, freshly confirmed absence is a stronger terminal postcondition than the
earlier uncertain forwarding observation.

## Finding F2 — cleanup failure must retain process ownership while retry remains possible

Releasing the lifetime lock while the current process still knows that its owned managed domain
remains would permit another controller to begin ownership work against unresolved state.

**Disposition:** when teardown fails, stop retains the lifetime lock.

The result distinguishes:

- `CLEANUP_FAILED_CONTAINED` — forwarding closure independently confirmed;
- `CLEANUP_FAILED_UNCONTAINED` — forwarding closure not confirmed.

Both are observable incomplete stop states and neither reports success.

## Finding F3 — successful cleanup precedes lock release

`destroy_managed_network_domain(...)` already performs fresh postcondition verification:

- configured named network namespace absent;
- configured host boundary veth absent.

Only after that function returns successfully does stop release the lifetime flock.

This preserves the current startup review invariant that no READY controller releases its
ownership lock while VPN-GATE-owned forwarding infrastructure remains active.

## Finding F4 — external VPN lifecycle is not silently adopted by stop

NG3 Release 1 leaves VPN-channel provisioning/configuration to the administrator/integration.

Stop therefore does not:

- enumerate or kill external VPN processes;
- issue protocol-specific shutdown;
- explicitly delete administrator-owned VPN path interfaces.

It removes VPN-GATE-owned managed-domain infrastructure. Any integration-specific consequence
for a VPN endpoint that lived inside that domain belongs to the supported onboarding/cleanup
contract and the explicit `EXP-049` applicability evidence gate.

This matches normative transition rule `TIP-L5`: administrator-owned external VPN process
lifecycle must not prevent cleanup of VPN-GATE-owned managed-domain state.

## Finding F5 — no generic cleanup registry is justified yet

The current READY session has no executable runtime Manager/Agent loops. Adding callback
registries, cleanup DAGs, retry queues or a LifecycleManager would create mechanism without a
current owner/requirement.

**Disposition:** current stop is direct procedural composition.

When later executable runtime owners exist, their concrete quiesce/release operations must be
added as independent cleanup domains under `VPNG-U005-R5.R5`.

## Failure/result semantics

`STOPPED` means:

- managed-domain teardown returned only after fresh absence confirmation;
- lifetime lock release was then attempted successfully.

`LOCK_RELEASE_FAILED` remains explicit even though network cleanup completed. This prevents a
local process-lifetime anomaly from being silently reported as a fully successful operation.

A stop call against an already released startup session is rejected before network cleanup so
a stale session object cannot accidentally tear down resources of a later controller.

## Evidence

### Rootless

GitHub Actions run `43997143534`, job `unit`: **SUCCESS**

```text
Ran 531 tests
OK
```

New tests prove:

- containment -> teardown -> lock-release ordering;
- failed containment still attempts teardown;
- teardown success after failed containment still yields STOPPED;
- contained cleanup failure retains the lock;
- uncontained cleanup failure is distinct and retains the lock;
- stale/released session is rejected before cleanup;
- lock-release failure remains observable after successful domain cleanup.

### Privileged Linux

Same workflow run, job `linux-payload-forward`: **SUCCESS**

Observed markers:

```text
CONTROLLER_STOP_OWNED_DOMAIN_REMOVED=PASS
CONTROLLER_STOP_LOCK_RELEASE_AFTER_CLEANUP=PASS
CONTROLLER_STOP_RESTART_REACQUIRE=PASS
CONTROLLER_STOP_REPEAT_CLEAN_CYCLE=PASS
NG3 bounded controller startup/stop integration: PASS
```

The live cycle proves:

1. READY startup holds the controller flock;
2. a second controller is refused;
3. bounded stop removes the owned namespace and host boundary;
4. the lock is released only afterward;
5. a clean new startup can reacquire ownership and recreate the domain;
6. the second clean stop also succeeds.

## Component-model review

No component family is added.

This is procedural lifecycle orchestration over existing Machinery boundaries:

- ForwardingGate;
- managed-network-domain lifecycle;
- controller lifetime lock.

It owns no autonomous schedule or persistent semantic state and therefore does not justify a
Manager/Engine.

## Simplification review

Not introduced:

- LifecycleManager;
- cleanup callback registry;
- generic dependency graph;
- retry queue;
- rollback journal;
- external VPN process manager;
- protocol-specific tunnel shutdown;
- persistent cleanup state.

## Accumulated requirement-state inventory

### `decomp`

Six accumulated links remain resolved. Pending: **none**.

### `unreal`

**none**

### `[rejected_closure]`

**none**

### Explicit pending evidence gate

`EXP-049` remains **PLANNED/PENDING** for administrator VPN onboarding applicability. It does
not block this owned-domain stop unit.

## Human decisions required

**none**

## Next logical unit

Implement the explicit `restart` lifecycle operation required by
`VPNG-U005-R5.R6.R3` as the smallest composition of the now-reviewed operations:

```text
stop current session
    -> only if STOPPED
start from fresh authoritative state
```

Do not add restart-specific recovery state or a lifecycle framework unless this composition
proves insufficient.

## Conclusion

**PASS.**

The controller now has a bounded executable stop operation with verified owned-domain cleanup,
explicit incomplete-cleanup states, and correct lifetime-lock release ordering.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005-R5.R4` -> `VPNG-M001-R1.R1.R4`
- `VPNG-U005-R5.R5` -> `VPNG-M001-R1.R1.R5`
- `VPNG-U005-R5.R6.R2` -> `VPNG-M001-R1.R1.R6.R2`
- `VPNG-U005-R5.R6.R3` -> `VPNG-M001-R1.R1.R6.R3`
- `VPNG-U006-R6.R3` -> `VPNG-M001-R2.R1.R3`
- `VPNG-U007-R7.R1` -> `VPNG-D001-R1.R1.R1`

The original IDs in the historical body are intentionally preserved.
