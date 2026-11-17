# VPN-GATE NG3 — stop/cleanup/restart CD checkpoint

**Date:** 2026-11-17  
**Cycle:** `ng3-design-cycle-20261117-stop-cleanup-restart-35m`  
**CYCLE_INTERVAL:** 35m  
**CYCLE_START_COMMIT:** `e509290c549c099a58f4c74c68e887135d9ef5ee`  
**T0:** 2026-11-17T01:37:10Z

## Cycle boundary

The coherent lifecycle block completed materially before the nominal 35-minute boundary.

Last pre-checkpoint logical commit:

`69a356a35c74229dca3de8ce865b3b498c888d5b` at
`2026-11-17T01:43:32Z`.

Elapsed logical-development interval before checkpoint: approximately **6m22s**.

No independent signal/checkpoint runtime unit is started merely to consume the remaining
interval. That unit introduces a distinct process-control mechanism and remains the next CD
boundary.

## Prerequisite carried from the interrupted model-switch cycle

The branch starts from the saved interrupted tip
`63a6c82b085a1f4a0d6f8540f5aa5e06f7b9731f`.

This CD first completed its already-reviewed closure bookkeeping:

- `VPNG0001-R1.R3.C1.R1.R1` changed from `[pending_closure]` to `[closed]`;
- architecture applicability gate remains accepted;
- `EXP-049` remains a planned/pending **evidence execution** gate, not an architecture
  closure blocker.

Because the prior cycle was explicitly interrupted by a model-level switch and was not
published as a main snapshot, the next main snapshot from this completed cycle will also carry
that saved applicability-gate work.

## Completed review unit A — bounded controller stop / cleanup

Added:

- `design/NG3/code/python/rou/controller_stop.py`;
- rootless stop ordering/failure tests;
- live startup -> stop integration;
- architecture section `12.0.4`;
- `NG3-2026-11-17-controller-stop-cleanup-review.md`.

Accepted semantics:

```text
retained lifetime lock
    ->
attempt ForwardingGate=DISABLED
    ->
independently attempt owned managed-domain teardown
    ->
confirmed namespace + host-boundary absence
    ->
release lifetime lock
```

Cleanup failure retains the lifetime lock while the process remains alive and distinguishes
confirmed-contained from uncontained incomplete cleanup.

External VPN process/interface lifecycle is not silently adopted by the controller; supported
integration cleanup/re-entry remains part of the onboarding/EXP-049 contract.

### Evidence

GitHub Actions run `43997143534`:

- rootless `unit`: **SUCCESS**, `Ran 531 tests / OK`;
- privileged `linux-payload-forward`: **SUCCESS**.

Observed markers:

```text
CONTROLLER_STOP_OWNED_DOMAIN_REMOVED=PASS
CONTROLLER_STOP_LOCK_RELEASE_AFTER_CLEANUP=PASS
CONTROLLER_STOP_RESTART_REACQUIRE=PASS
CONTROLLER_STOP_REPEAT_CLEAN_CYCLE=PASS
```

## Completed review unit B — bounded controller restart

Added:

- `design/NG3/code/python/rou/controller_restart.py`;
- rootless restart composition tests;
- production restart invocation in the live lifecycle integration;
- architecture section `12.0.5`;
- `NG3-2026-11-17-controller-restart-review.md`.

Accepted semantics:

```text
restart(current READY session)
    ->
stop_controller_once(...)
    ->
only if STOPPED:
    start_controller_once(...)
    ->
READY | START_FAILED
```

Stop failure prevents startup. Startup failure is preserved directly. No restart-specific
retry, rollback, lock-transfer protocol or lifecycle journal is introduced.

### Evidence

GitHub Actions run `43997511963`:

- rootless `unit`: **SUCCESS**, `Ran 534 tests / OK`;
- privileged `linux-payload-forward`: **SUCCESS**.

Observed markers:

```text
CONTROLLER_STOP_OWNED_DOMAIN_REMOVED=PASS
CONTROLLER_STOP_LOCK_RELEASE_AFTER_CLEANUP=PASS
CONTROLLER_RESTART_STOP_THEN_START_READY=PASS
CONTROLLER_RESTART_NEW_SESSION_LOCK_HELD=PASS
CONTROLLER_STOP_REPEAT_CLEAN_CYCLE=PASS
NG3 bounded controller startup/stop/restart integration: PASS
```

## Requirement-state inventory

### `decomp`

Six accumulated links remain resolved.

Pending: **none**.

### `unreal`

**none**

### `[rejected_closure]`

**none**

### Other explicit pending evidence

- `EXP-049` — administrator external-VPN onboarding applicability: **PLANNED/PENDING
  execution**.

This is not a `decomp`, `unreal` or rejected architecture closure.

## Human decisions required

**none**

## Next intended review unit

Phase-bounded termination handling during startup / transition into RUN:

- stop handlers effective before startup creates owned mutable state;
- stop requested during `STARTING` prevents later startup phases;
- once a phase may have created safety-relevant owned state, termination must run
  containment/cleanup rather than abandon it;
- do not promote historical RC2 signal implementation into NG3 automatically;
- first determine the smallest replaceable checkpoint/control contract required by current
  requirements.

## Checkpoint verdict

**PASS — CURRENT LIFECYCLE REVIEW BLOCK COMPLETE.**

The branch is ready for one linear mainline snapshot. Autonomous development stops at this
checkpoint and resumes with a reset cycle clock on the next user-authorized CD.
