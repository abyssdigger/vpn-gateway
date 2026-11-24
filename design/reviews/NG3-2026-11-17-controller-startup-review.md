# VPN-GATE NG3 — bounded controller startup review

**Date:** 2026-11-17  
**Cycle branch:** `ng3-design-cycle-20261117-direct-device-bootstrap-35m`

## Scope

Review the first executable bounded controller startup composition over already accepted lower
boundaries:

- controller lifetime exclusion;
- non-creating managed-domain preflight;
- candidate policy load/validation;
- managed-domain ensure;
- fresh current interface observation;
- pure complete payload desired-state build;
- guarded network-policy activation;
- READY only from confirmed activation.

This is a synchronous startup operation, not a LifecycleManager or runtime reconciliation
loop.

## Verdict

**PASS.**

The startup path now preserves the required ownership/safety ordering and reaches verified
zero-path READY on real Linux without creating infrastructure for an invalid candidate
configuration or allowing a second controller to enter startup concurrently.

No human product decision is required.

## Implementation

New module:

`design/NG3/code/python/rou/controller_startup.py`

New managed-domain lower primitive:

`preflight_managed_network_domain(...)`

Public startup contracts:

- `PreparedPayloadPolicy`;
- `ValidatedPolicyLoader`;
- `ControllerStartupStatus`;
- `ControllerStartupSession`;
- `ControllerStartupResult`;
- `start_controller_once(...)`.

## Startup ordering

The executable order is:

```text
acquire controller lifetime lock
    ->
managed-domain preflight WITHOUT creation
    ->
load + validate candidate policy
    ->
ensure/create exact contained managed domain
    ->
fresh managed-domain link inventory
    ->
pure current desired-state build
    ->
activate_network_policy(...)
    ->
READY + retained lifetime lock
```

This recovers the accepted lifecycle semantics without creating a new long-lived component.

## Finding F1 — invalid candidate config must not create fresh infrastructure

The architecture requires stale/owned state containment before trusting a candidate config,
but it does not justify creating a new namespace/veth before that candidate validates.

Calling `ensure_managed_network_domain(...)` before config load would therefore be too
eager on the absent-domain path.

**Disposition:** added `preflight_managed_network_domain(...)`.

It:

- contains and exactly verifies an existing complete domain;
- confirms fully absent namespace+host-boundary state without mutation;
- rejects partial/divergent state;
- never creates absent infrastructure.

Only after candidate load/validation succeeds does startup call the creating
`ensure_managed_network_domain(...)`.

Privileged evidence proves a synthetic invalid candidate leaves both namespace and host veth
absent.

## Finding F2 — lock acquisition precedes every owned startup operation

Startup acquires the hardened lifetime flock before:

- managed-domain preflight;
- config load;
- domain creation;
- desired-state construction;
- activation.

A busy lock returns `LOCK_BUSY` immediately and no later phase executes.

On successful startup the lock remains held in `ControllerStartupSession`.

## Finding F3 — current interface generation is sampled only after domain ensure

A fresh domain has no namespace-side boundary ifindex until creation completes.

The candidate loader therefore does not receive or invent current interface facts.

Instead it returns a pure `PreparedPayloadPolicy` object whose:

`build_current(host_boundary, interfaces)`

is invoked only after exact domain ensure and one fresh managed-domain link inventory.

The verified current namespace-side boundary `InterfaceIdentity` must appear in that fresh
inventory.

## Finding F4 — policy/config semantics remain outside lifecycle orchestration

Startup does not parse Device/Profile TOML directly and does not know final deferred
NAT/firewall/publication grammar.

Its seam is:

```text
load_validated_policy()
    -> PreparedPayloadPolicy

PreparedPayloadPolicy.build_current(...)
    -> PayloadNetworkPolicyDesiredState
```

This lets configuration/integration-specific assembly evolve without duplicating lifecycle
ordering.

## Finding F5 — current-fact/desired-build failure is re-contained before lock release

Once managed-domain ensure has succeeded, startup may own a safe reusable infrastructure
domain.

If fresh interface observation or desired-state construction then fails, startup performs one
explicit `ForwardingGate=DISABLED` convergence/reread before releasing the lifetime lock.

If containment confirms:

- return the original phase failure;
- retain the exact contained domain for a later startup attempt.

If containment cannot be confirmed:

- return distinct `FAILURE_CONTAINMENT_FAILED`;
- preserve the original failure category.

Startup does not retry the failed observation/build phase.

## Finding F6 — activation failure is not wrapped in another retry loop

`activate_network_policy(...)` already owns its lower containment semantics.

Startup calls it exactly once.

- ordinary activation failure -> `ACTIVATION_FAILED`;
- activation reports unconfirmed failure containment ->
  `FAILURE_CONTAINMENT_FAILED`.

No second activation attempt or replay is introduced.

## Finding F7 — startup failure does not automatically destroy a verified domain

A successfully ensured managed domain is fail-closed infrastructure and can be reused on a
later start.

Automatically tearing it down after every later startup failure would add destructive
recovery policy not required by current semantics and would complicate diagnostics.

**Disposition:** only creation failure rolls back inside the managed-domain lifecycle.
Post-ensure startup failure leaves the domain contained.

Explicit stop/cleanup remains a separate logical boundary.

## Finding F8 — READY session retains ownership

`ControllerStartupSession` can exist only when:

- lifetime lock remains acquired;
- domain preflight is confirmed;
- managed domain is confirmed;
- activation is READY.

Startup never returns READY after releasing the controller lock.

Releasing that lock while forwarding remains active is not a valid startup operation; future
stop/cleanup orchestration must contain/quiesce and clean owned state before releasing it.

## Evidence

### Rootless

Workflow `43992995110`: **SUCCESS**

```text
Ran 525 tests
OK
```

Startup phase tests cover:

- exact successful phase order;
- retained lifetime lock on READY;
- invalid candidate does not call domain ensure;
- preflight failure stops before config load;
- domain ensure failure stops before activation;
- interface observation failure is re-contained;
- desired build failure is re-contained;
- re-containment failure is distinct;
- activation failure is invoked once/no retry;
- activation containment failure is preserved;
- busy lock stops before preflight.

The earlier red runs `43992583393` / `43992615209` were fixture defects only:
the tests supplied an opaque object without `.namespace` and referenced a nonexistent
ForwardingGate status. Production startup implementation had already passed its workflow;
the corrected fixtures are green without weakening any assertion.

### Privileged Linux

Workflow `43993208722`, `linux-payload-forward`: **SUCCESS**

Markers:

```text
CONTROLLER_STARTUP_INVALID_CONFIG_NO_DOMAIN_CREATE=PASS
CONTROLLER_STARTUP_ZERO_PATH_READY=PASS
CONTROLLER_STARTUP_SECOND_INSTANCE_REFUSED=PASS
CONTROLLER_STARTUP_CLEANUP_AFTER_LOCK_RELEASE=PASS
NG3 bounded controller startup integration: PASS
```

The live gate proves:

1. controller lock acquisition + absent-domain preflight;
2. invalid candidate validation failure creates no namespace/veth;
3. valid zero-path policy creates the managed domain, materializes fail-closed policy and
   reaches READY;
4. READY retains the lifetime flock;
5. a second startup attempt receives `LOCK_BUSY`;
6. after explicit lock release, managed-domain teardown succeeds.

## Component-model review

The startup function is procedural lifecycle orchestration.

It is not a Manager because it owns no independent long-lived semantic state or autonomous
reconciliation schedule.

Existing lower responsibilities remain separate:

- instance lock — process exclusion primitive;
- managed-domain lifecycle — infrastructure Executor;
- prepared policy — pure semantic/current-fact Calculator boundary;
- activation — network-policy convergence assembly.

## Simplification review

Not introduced:

- LifecycleManager;
- startup retry queue;
- generic phase framework;
- persistent startup journal;
- duplicate policy parser;
- duplicate network observer;
- automatic destructive teardown on every failure;
- signal/event-loop machinery.

## Remaining lifecycle boundary

This PASS completes bounded startup to READY, but not product lifecycle as a whole.

Still separate:

- stop/quiesce/cleanup orchestration;
- restart composition;
- signal/checkpoint behavior around STARTING/RUN;
- runtime Manager reconciliation/audit;
- current status publication;
- final external optional-policy grammar;
- probe production materialization.

The next logical unit should review and implement **stop/cleanup** ordering. It must attempt
independent owned-domain cleanup even when another cleanup area fails and must release the
lifetime lock only after required containment/cleanup attempts have completed.

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

The controller now has a bounded executable startup path from exclusive ownership through
candidate validation, managed-domain construction, current desired-state assembly and
verified network-policy activation to READY.
