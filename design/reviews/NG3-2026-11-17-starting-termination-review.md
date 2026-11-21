# VPN-GATE NG3 — phase-bounded STARTING termination review

**Date:** 2026-11-17  
**Cycle branch:** `ng3-design-cycle-20261117-starting-termination-35m`

## Scope

Review the first executable controller contract for an asynchronous stop request received while
startup is still in `STARTING`, including the critical boundary after a successful
network-policy activation but before READY publication.

This unit implements the core synchronous checkpoint semantics. It does not choose a concrete
POSIX-signal/service-manager adapter.

## Requirements

**Implements:**
- `VPNG0005-R5.R1`;
- `VPNG0005-R5.R4`;
- `VPNG0005-R5.R5`;
- `VPNG0005-R5.R6.R1`;
- `VPNG0005-R5.R6.R2`;
- `VPNG0006-R6.R3`.

**Constrained by:**
- `VPNG0007-R7.R1`.

## Verdict

**PASS.**

The bounded startup assembly can now observe an externally supplied stop request at every
completed startup phase boundary and cannot continue into a later phase after that request is
observed.

No human product decision is required.

## Implementation

Modified:

- `design/NG3/code/python/rou/controller_startup.py`;
- `design/NG3/code/python/rou/controller_stop.py`;
- public exports in `rou/__init__.py`;
- startup rootless and privileged integration tests.

New/extended contracts:

- `ControllerStopRequested` — read-only callable process-control input;
- `ControllerStartupStatus.STOPPED`;
- `ControllerStartupStatus.STOP_CLEANUP_FAILED`;
- `ControllerStartupStoppingContext`;
- shared `cleanup_controller_owned_domain_once(...)`.

## Finding F1 — asynchronous request is an input fact, not a network-operation owner

The core controller does not install signal handlers and does not allow an asynchronous handler
to perform kernel mutations.

Accepted boundary:

```text
external process adapter / signal handler
    -> record stop request only

synchronous startup checkpoint
    -> observe stop_requested()
    -> perform ordered cleanup under controller ownership
```

This preserves a single network-state owner and keeps POSIX/service-manager mechanics
replaceable.

## Finding F2 — checkpoints belong after bounded phases, not inside lower mutations

The implemented observation points are:

```text
entry
after lock acquisition
after managed-domain preflight
after candidate policy load/validation
after managed-domain ensure
after fresh interface observation
after pure desired-state build
after network-policy activation, before READY
```

A request observed at one checkpoint prevents the next phase from starting.

Lower Drivers/Executors are not interrupted mid-command or mid-transaction.

## Finding F3 — before ownership, stop must not create cleanup work

If the request is already present at startup entry:

- no lifetime lock is acquired;
- no managed-domain operation is attempted;
- result is `STOPPED`.

If the request appears after lock acquisition but before managed-domain work:

- the lock is released;
- no network cleanup is invented;
- result is `STOPPED`.

This matches the accepted rule that an attempted startup does not clean resources merely
because it was invoked when it never began owned network work.

## Finding F4 — after confirmed preflight, interrupted startup reuses product stop cleanup

Once managed-domain preflight has completed, every observed stop request invokes the same
owned-domain cleanup primitive as ordinary stop:

```text
ForwardingGate=DISABLED attempt
    ->
independent managed-domain teardown attempt
    ->
fresh namespace + host-boundary absence confirmation
    ->
release lifetime lock
```

The stop path was factored so READY stop and STARTING interruption do not carry two copies of
cleanup semantics.

## Finding F5 — the post-activation / pre-READY checkpoint is mandatory

A successful network-policy activation is capable of leaving managed forwarding active.

Therefore:

```text
activation READY
    + stop already requested
    != controller READY
```

Startup performs one final checkpoint before constructing a
`ControllerStartupSession`.

If stop is observed there, startup immediately executes owned cleanup while still holding the
original lifetime lock.

This closes the previously explicit window where a termination request could arrive after
lower activation and before READY publication.

## Finding F6 — incomplete interrupted cleanup retains ownership

When managed-domain cleanup fails and the lock remains acquired:

- startup returns `STOP_CLEANUP_FAILED`;
- no READY session exists;
- `ControllerStartupStoppingContext` retains the lifetime lock and exact stop result.

Startup does not release that lock and does not continue.

A lock-release error after successfully confirmed network cleanup is represented separately by
the lower stop result and is not falsely wrapped as a retained-lock context.

## Finding F7 — ordinary phase failure remains ordinary failure

A stop request does not rewrite a failing startup phase into successful stop.

Existing phase-specific startup failure semantics and safety containment remain authoritative;
the only new behavior occurs at completed phase checkpoints.

This avoids hiding configuration, observation, activation or containment failures behind an
unrelated graceful-stop request.

## Evidence

### Rootless

GitHub Actions run `44022903111`, head
`1cb208bf8d948b034933e2d92b139fc8f0dd3c03`: **SUCCESS**

```text
Ran 541 tests
OK
```

The new tests prove:

- request at entry prevents lock acquisition;
- request immediately after lock prevents domain work and releases the lock;
- every post-preflight phase boundary stops before the next phase;
- final post-activation request never publishes a READY session;
- interrupted cleanup failure retains the lock through an explicit stopping context;
- existing startup/stop/restart behavior remains green.

### Privileged Linux

Same workflow run, `linux-payload-forward`: **SUCCESS**

Observed markers:

```text
CONTROLLER_STARTING_STOP_AFTER_ACTIVATION_NO_READY=PASS
CONTROLLER_STARTING_STOP_OWNED_DOMAIN_CLEANUP=PASS
CONTROLLER_STARTING_STOP_LOCK_RELEASE_AFTER_CLEANUP=PASS
CONTROLLER_STARTUP_ZERO_PATH_READY=PASS
CONTROLLER_STARTUP_SECOND_INSTANCE_REFUSED=PASS
CONTROLLER_STOP_OWNED_DOMAIN_REMOVED=PASS
CONTROLLER_RESTART_STOP_THEN_START_READY=PASS
CONTROLLER_STOP_REPEAT_CLEAN_CYCLE=PASS
NG3 bounded controller startup/STARTING-stop/stop/restart integration: PASS
```

The integration deliberately requests stop only at the eighth checkpoint, proving that
network-policy activation had already succeeded. The result still does not expose READY,
removes the managed namespace and host boundary, releases the lifetime lock after cleanup, and
permits a subsequent ordinary clean startup.

## Component-model review

No new Engine, Manager or Agent is introduced.

The stop-request predicate is a replaceable process-control input. Checkpoint evaluation is
procedural lifecycle orchestration and owns no independent semantic state beyond the
in-progress startup call.

## Simplification review

Not introduced:

- daemon state machine;
- signal thread;
- background event loop;
- cancellation tokens inside lower Drivers;
- retry/backoff loop;
- phase rollback journal;
- duplicate STARTING cleanup implementation.

## Remaining lifecycle/process gap

The core checkpoint contract is now executable, but a concrete deployment/process adapter is
still absent.

A later unit may map SIGTERM/SIGINT, service-manager requests or another control surface to the
`ControllerStopRequested` predicate. That adapter must be installed before invoking startup
and must not perform network mutations from the asynchronous handler.

This is mechanism/deployment work, not an unresolved product-semantics decision.

## Accumulated requirement-state inventory

### `decomp`

Six accumulated requirement links remain present and resolved.

Pending `decomp`: **none**.

### `unreal`

Active requirement `unreal` links: **none**.

### `[rejected_closure]`

Active requirement entries with `[rejected_closure]`: **none**.

(The requirements methodology prose defines the marker text; that definition is not an active
requirement entry.)

### Other explicit pending evidence

`EXP-049` remains **PLANNED/PENDING execution** for administrator external-VPN onboarding
applicability.

## Human decisions required

**none**

## Next logical unit

Review the smallest concrete process-control adapter needed to feed this accepted predicate:

```text
install stop source before start_controller_once(...)
    ->
asynchronous callback records request only
    ->
startup/RUN owner observes request synchronously
```

Do not restore the historical RC2 daemon state machine or event-loop machinery unless a
current requirement proves it necessary.

## Conclusion

**PASS.**

The controller now has an executable, phase-bounded STARTING termination contract, including
the safety-critical post-activation/pre-READY cleanup boundary, without importing obsolete
daemon machinery.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG0005-R5.R1` -> `VPNG9101-R1.R1.R1`
- `VPNG0005-R5.R4` -> `VPNG9101-R1.R1.R4`
- `VPNG0005-R5.R5` -> `VPNG9101-R1.R1.R5`
- `VPNG0005-R5.R6.R1` -> `VPNG9101-R1.R1.R6.R1`
- `VPNG0005-R5.R6.R2` -> `VPNG9101-R1.R1.R6.R2`
- `VPNG0006-R6.R3` -> `VPNG9101-R2.R1.R3`
- `VPNG0007-R7.R1` -> `VPNG9001-R1.R1.R1`

The original IDs in the historical body are intentionally preserved.
