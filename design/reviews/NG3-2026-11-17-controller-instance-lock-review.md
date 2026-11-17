# VPN-GATE NG3 — controller instance lock review

**Date:** 2026-11-17  
**Cycle branch:** `ng3-design-cycle-20261117-direct-device-bootstrap-35m`

## Scope

Review the controller lifetime exclusion boundary that prevents two VPN-GATE controller
processes from concurrently owning cleanup/bootstrap/network-policy actuation for one
deployment instance.

This unit owns only runtime-directory integrity and the process lifetime lock.

## Verdict

**PASS.**

The lower lock contract is hardened, non-blocking, stale-file tolerant and independent from
the unresolved final deployment/config grammar.

No human product decision is required.

## Implementation

New module:

`design/NG3/code/python/rou/instance_lock.py`

Public contracts:

- `InstanceLockSpec`;
- `ControllerInstanceLock`;
- `ControllerInstanceLockError`;
- `ControllerInstanceBusyError`;
- `acquire_controller_instance_lock(...)`.

Normalized deployment input:

```text
runtime_directory: absolute path
expected_owner_uid
```

The lock filename is internal and fixed. It is not a separately configurable product field.

## Finding F1 — file existence/PID text must not be the ownership authority

A stale lock file after process death is normal filesystem state and must not prevent
restart.

**Disposition:** ownership is the kernel-held advisory lock:

```text
flock(fd, LOCK_EX | LOCK_NB)
```

The file may remain after release. Reacquisition succeeds once the prior descriptor is gone.

No PID-file liveness inference is introduced.

## Finding F2 — second controller must fail before resource mutation

Two concurrent controllers could each believe they own cleanup, managed-domain creation and
network-policy activation.

**Disposition:** acquisition is non-blocking. Busy lock raises a distinct
`ControllerInstanceBusyError` with “another VPN-GATE controller instance is running”.

No wait/backoff/retry belongs to this boundary.

The future startup coordinator must acquire this lock before cleanup/bootstrap/actuation.

## Finding F3 — runtime directory is part of the security boundary

Opening a lock under an unsafe directory would make lock-file hardening insufficient.

**Disposition:** the runtime directory must be:

- absolute;
- a real directory, not a symlink;
- exact mode `0700`;
- owned by the expected service UID.

If absent and creatable it is created with `0700`, then verified.

Existing wrong owner/mode/type is a fatal error and is not silently chmod/chown repaired.

## Finding F4 — lock file itself must be hardened

The lock file is opened with:

```text
O_RDWR | O_CREAT | O_CLOEXEC | O_NOFOLLOW
mode 0600
```

Fresh `fstat` then requires:

- regular file;
- exact mode `0600`;
- expected owner UID.

Existing unsafe mode or symlink is refused rather than repaired/followed.

## Finding F5 — deployment identity remains injected

Historical RC2/RC3 implementations used a concrete default runtime path and root ownership.

NG3 does not promote those values into current user semantics.

`InstanceLockSpec` receives the runtime directory and expected service UID from a later
deployment/startup assembly.

This keeps root foreground, systemd RuntimeDirectory and a future dedicated service identity
compatible with the same lower safety contract.

## Finding F6 — lock lifetime is explicit and minimal

`ControllerInstanceLock` owns one open file descriptor.

- context-manager exit releases it;
- explicit `release()` is idempotent;
- after release the same object cannot be re-entered as an acquired lock;
- no background thread or heartbeat is required.

Kernel/process teardown also releases the flock automatically.

## Evidence

Workflow `43991433019`, rootless unit job: **SUCCESS**

```text
Ran 513 tests
OK
```

New coverage proves:

- runtime directory + lock file creation modes/ownership;
- immediate second-acquisition refusal;
- stale-file reacquisition after release;
- context-manager release;
- idempotent release;
- runtime-directory symlink refusal;
- wrong directory mode refusal without repair;
- owner mismatch refusal;
- lock-file symlink refusal through `O_NOFOLLOW`;
- wrong existing lock mode refusal;
- relative runtime path rejection.

No privileged kernel-network experiment is required. The mechanism under test is ordinary
Linux/POSIX filesystem + `flock`, exercised directly by the rootless test process.

## Evidence continuity

This boundary intentionally carries forward the already reviewed RC2/RC3 hardening:

- private runtime directory;
- final-component symlink refusal;
- exact owner/mode;
- `O_NOFOLLOW`;
- non-blocking exclusive lifetime flock.

Not carried forward as product semantics:

- historical fixed `/run/vpn-gateway` path;
- historical lock filename;
- root UID as universal deployment identity;
- PID-file ownership semantics.

## Component-model review

This is a narrow lifecycle/ownership primitive, not a Manager or Agent.

The future lifecycle coordinator owns when to acquire/release it. The lock object itself has
no scheduling, retry or policy responsibility.

## Simplification review

Not introduced:

- PID liveness polling;
- lock retry loop;
- distributed lock;
- configurable shared multi-instance lock namespace;
- lock ownership database;
- runtime-directory repair via chmod/chown;
- systemd dependency in core logic.

## Next lifecycle boundary

The prerequisite chain now contains executable lower units for:

```text
controller exclusion
    -> managed network-domain infrastructure
    -> pure current desired-state assembly
    -> guarded network-policy activation
```

The next logical unit is startup phase orchestration around already-normalized inputs and
fresh current facts. It must preserve:

- lock before any owned cleanup/mutation;
- no READY before activation confirmation;
- lower failure containment;
- no duplication of the existing convergence/retry contracts.

Runtime event-loop/Manager scheduling remains separate from startup.

## Accumulated requirement-state inventory

### `decomp`

All six accumulated links remain **resolved**. Pending: **none**.

### `unreal`

**none**

### `[rejected_closure]`

**none**

## Human decisions required

**none**

## Conclusion

**PASS.**

Controller lifetime exclusion is now an explicit hardened lower prerequisite rather than an
implicit deployment assumption.
