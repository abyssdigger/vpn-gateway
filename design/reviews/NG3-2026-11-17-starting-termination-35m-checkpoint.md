# VPN-GATE NG3 — STARTING termination CD checkpoint

**Date:** 2026-11-17  
**Cycle:** `ng3-design-cycle-20261117-starting-termination-35m`  
**CYCLE_INTERVAL:** 35m  
**CYCLE_START_COMMIT:** `535e017a5598c6e6d58ab3993fb28558213fbda3`  
**T0:** 2026-11-17T05:13:53Z

## Cycle boundary

The coherent STARTING-termination review unit completed before the nominal interval.

Last pre-checkpoint logical commit:

`660f5470a0ddd8b8efa5fe37228ac9dd2495ac90` at
`2026-11-17T05:17:43Z`.

Elapsed logical-development interval before checkpoint: approximately **3m50s**.

The next process-control adapter is intentionally not started in this cycle because it is a
separate mechanism/deployment unit rather than another checkpoint inside the same core startup
composition.

## Completed review unit — phase-bounded STARTING termination

Implemented:

- read-only `ControllerStopRequested` input to bounded startup;
- request check before lock acquisition;
- request check immediately after lock acquisition;
- request checkpoints after every completed startup phase:
  - managed-domain preflight;
  - candidate policy load/validation;
  - managed-domain ensure;
  - fresh interface observation;
  - desired-state build;
  - network-policy activation;
- final post-activation / pre-READY cleanup boundary;
- explicit `STOPPED` and `STOP_CLEANUP_FAILED` startup outcomes;
- retained `ControllerStartupStoppingContext` when interrupted cleanup is incomplete and the
  lifetime lock remains held;
- shared owned-domain cleanup primitive reused by READY stop and STARTING interruption.

No lower Driver/Executor is cancelled mid-mutation.

## Accepted control boundary

```text
external asynchronous stop source
    -> record request only

bounded synchronous startup
    -> observe request at completed phase boundary
    -> never enter a later startup phase after observation
    -> if managed-domain ownership has begun:
         run ordinary owned-domain cleanup under same lifetime lock
    -> final checkpoint occurs after activation but before READY
```

The external POSIX signal/service-manager adapter remains a later replaceable process-interface
unit.

## Evidence

GitHub Actions run `44022903111`, head
`1cb208bf8d948b034933e2d92b139fc8f0dd3c03`: **SUCCESS**.

### Rootless

`unit`: **SUCCESS**

```text
Ran 541 tests
OK
```

Rootless evidence includes a table proof that each post-preflight phase checkpoint stops before
the next phase, plus explicit pre-ownership, post-lock, final post-activation and incomplete
cleanup cases.

### Privileged Linux

`linux-payload-forward`: **SUCCESS**

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

The live test deliberately requests stop only at the final checkpoint after successful
network-policy activation. No READY session is exposed; the managed domain is removed and the
lock released only after confirmed cleanup.

## Review

`design/reviews/NG3-2026-11-17-starting-termination-review.md`

Verdict: **PASS**.

Human decisions required: **none**.

## Requirement-state inventory

### `decomp`

Six accumulated requirement links remain present and resolved.

Pending: **none**.

### `unreal`

Active links: **none**.

### `[rejected_closure]`

Active requirement entries: **none**.

### Other explicit pending evidence

- `EXP-049` administrator external-VPN onboarding applicability:
  **PLANNED/PENDING execution**.

## Remaining gates

- concrete process-control adapter feeding `ControllerStopRequested`;
- transition from READY into actual RUN ownership / runtime Manager reconciliation;
- user-facing current status/readiness publication;
- final optional-policy grammar;
- production probe materialization;
- `EXP-049` external-VPN onboarding applicability execution.

## Next intended review unit

Smallest concrete process-control adapter:

```text
install before startup
    ->
SIGTERM/SIGINT or equivalent callback records a stop latch only
    ->
bounded startup / later RUN owner observes the latch synchronously
```

The unit must not restore the historical RC2 daemon state machine, background event loop or
network operations inside signal handlers without a new requirement.

## Checkpoint verdict

**PASS — CURRENT STARTING-TERMINATION REVIEW UNIT COMPLETE.**

The branch is ready for one linear mainline snapshot. Autonomous development stops at this
checkpoint and resumes with a reset cycle clock on the next user-authorized CD.
