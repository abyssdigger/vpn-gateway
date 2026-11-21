# VPN-GATE NG3 — bounded controller restart review

**Date:** 2026-11-17  
**Cycle branch:** `ng3-design-cycle-20261117-stop-cleanup-restart-35m`

## Scope

Review the explicit product restart operation required by `VPNG-U005-R5.R6.R3` as the
smallest composition of the already accepted bounded stop and startup operations.

## Requirements

**Implements:**
- `VPNG-U005-R5.R6.R3`;
- `VPNG-U006-R6.R3`.

**Constrained by:**
- `VPNG-U005-R5.R6.R2`;
- `VPNG-U007-R7.R1`.

## Verdict

**PASS.**

Restart requires no new persistent lifecycle state or component. The existing stop and startup
postconditions compose directly.

## Implementation

New module:

`design/NG3/code/python/rou/controller_restart.py`

Public contracts:

- `ControllerRestartStatus`;
- `ControllerRestartResult`;
- `restart_controller_once(...)`.

Executable semantics:

```text
stop_controller_once(current session)
    ->
if stop != STOPPED:
    STOP_FAILED
    startup is not invoked
    ->
start_controller_once(...)
    ->
READY | START_FAILED
```

## Finding F1 — incomplete stop must block restart startup

A restart that proceeds after a contained or uncontained cleanup failure would violate the
requirement that unresolved previous-instance state not be silently declared a successful
restart.

**Disposition:** `start_controller_once(...)` is not called unless the stop result is exactly
`STOPPED`.

The exact stop result is preserved in `ControllerRestartResult` for diagnosis.

## Finding F2 — restart should reuse ordinary startup rather than create a second startup path

The post-stop state is the same authoritative starting point required by normal startup.

Duplicating config load, domain creation, binding observation or network-policy activation
inside restart would create two lifecycle implementations with avoidable drift.

**Disposition:** successful stop is followed by one ordinary `start_controller_once(...)`.

The exact startup result is preserved. A non-READY result becomes restart `START_FAILED`
without retry.

## Finding F3 — no hidden ownership bypass across the stop/start boundary

Successful stop releases the old controller lifetime lock only after owned-domain absence is
confirmed.

Restart then reacquires ownership through the normal hardened startup lock path.

No private lock-transfer token or bypass is introduced. If another legitimate controller
acquires the deployment lock between those operations, the new startup reports its ordinary
lock-busy failure and restart reports `START_FAILED`.

This is safe and simpler than inventing cross-operation lock handoff semantics not required by
the current product contract.

## Finding F4 — no restart-specific recovery state is justified

No accepted requirement needs:

- automatic repeated start attempts;
- rollback to the old READY instance;
- saved kernel snapshots;
- persistent restart journals;
- partial-start resume;
- special restart generations.

A failed post-stop start leaves the product in the ordinary failed-start state with its
existing containment semantics.

## Evidence

### Rootless

GitHub Actions run `43997511963`, job `unit`: **SUCCESS**

```text
Ran 534 tests
OK
```

New restart tests prove:

- stop failure blocks startup completely;
- STOPPED followed by READY startup returns the new session;
- startup failure is preserved as `START_FAILED`;
- stop and start are each invoked at most once.

### Privileged Linux

Same workflow run, job `linux-payload-forward`: **SUCCESS**

Observed lifecycle markers:

```text
CONTROLLER_STOP_OWNED_DOMAIN_REMOVED=PASS
CONTROLLER_STOP_LOCK_RELEASE_AFTER_CLEANUP=PASS
CONTROLLER_RESTART_STOP_THEN_START_READY=PASS
CONTROLLER_RESTART_NEW_SESSION_LOCK_HELD=PASS
CONTROLLER_STOP_REPEAT_CLEAN_CYCLE=PASS
NG3 bounded controller startup/stop/restart integration: PASS
```

The live test proves that production restart:

1. tears down the current owned network domain;
2. releases the previous lifetime lock only after cleanup;
3. reacquires controller ownership through normal startup;
4. recreates and reactivates the managed domain to READY;
5. returns a new session holding the new lifetime lock;
6. can subsequently stop cleanly again.

## Component-model review

No new component family is introduced.

Restart is a thin product lifecycle operation composing two procedural assemblies with already
defined responsibilities and postconditions.

## Simplification review

Not introduced:

- LifecycleManager;
- restart state machine;
- retry/backoff policy;
- lock-transfer protocol;
- rollback transaction;
- persistent lifecycle journal.

## Accumulated requirement-state inventory

### `decomp`

Six accumulated links remain resolved. Pending: **none**.

### `unreal`

**none**

### `[rejected_closure]`

**none**

### Explicit pending evidence gate

`EXP-049` remains **PLANNED/PENDING** for administrator VPN onboarding applicability.

## Human decisions required

**none**

## Next logical unit

The next lifecycle gap is the already documented phase/checkpoint boundary for a termination
request during `STARTING` / transition into RUN.

That unit should remain separate from this restart composition because it introduces a process
control/checkpoint mechanism rather than another product lifecycle operation.

## Conclusion

**PASS.**

The explicit restart operation now has executable semantics and live evidence without adding a
second startup path or restart-specific lifecycle machinery.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005-R5.R6.R2` -> `VPNG-M001-R1.R1.R6.R2`
- `VPNG-U005-R5.R6.R3` -> `VPNG-M001-R1.R1.R6.R3`
- `VPNG-U006-R6.R3` -> `VPNG-M001-R2.R1.R3`
- `VPNG-U007-R7.R1` -> `VPNG-D001-R1.R1.R1`

The original IDs in the historical body are intentionally preserved.
