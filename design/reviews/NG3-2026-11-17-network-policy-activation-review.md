# VPN-GATE NG3 — network-policy activation subassembly review

**Date:** 2026-11-17  
**Cycle branch:** `ng3-design-cycle-20261117-policy-activation-35m`

## Scope

Review the bounded procedural assembly that composes already accepted lower network-policy
units into one readiness-producing operation:

1. verify payload containment;
2. observe/classify the invariant nft scaffold;
3. bootstrap/repair the scaffold only when the existing scaffold-only mutation contract
   safely covers the state;
4. run the complete cross-domain structural transaction;
5. report READY only from a confirmed exact lower state;
6. after any lower failure, independently verify/re-establish
   `ForwardingGate=DISABLED` without retrying the failed lower operation.

This unit is intentionally smaller than product startup/lifecycle.

## Implements

- `VPNG0004-R4.R4` — payload forwarding is not ready before safe initial policy state is
  confirmed;
- `VPNG0004-R4.R5` — uncertainty/failure is followed by authoritative containment rather
  than unknown allowing state;
- `VPNG0005-R5.R1` — startup assembly needs a verified runtime-policy postcondition before
  readiness;
- `VPNG0005-R5.R6.R1` — successful start/readiness semantics depend on confirmed
  postconditions, not command issuance;
- `VPNG0006-R6.R3` — blocking lifecycle/policy failures remain explicit;
- `VPNG0006-R6.R4` — READY is distinct from desired/unconfirmed state.

**Constrained by:**

- `VPNG0007-R7.R1` — no generic lifecycle framework or hidden retry policy;
- `VPNG0007-R7.R3.R1` — lower boundaries are composed through explicit contracts.

All governing R/C nodes were already `[closed]`; no requirement refinement was required.

## Verdict

**PASS.**

`activate_network_policy(...)` is a valid bounded activation subassembly for the currently
implemented Release-1 lower network-policy state.

No human product decision is required.

## Implementation

New module:

`design/NG3/code/python/rou/network_policy_activation.py`

Public contracts:

- `NetworkPolicyActivationStatus`
- `NetworkPolicyActivationResult`
- `activate_network_policy(...)`

The result preserves:

- initial containment result;
- current scaffold comparison;
- scaffold-prepare result when that phase was needed;
- complete structural-transaction result;
- failure-containment result when a lower phase failed;
- the original failure category when final containment itself fails.

`ready` is true only for `READY` plus a confirmed structural transaction.

## Finding F1 — containment must precede even scaffold observation/mutation

A startup-like activation cannot rely on the nft scaffold already being trustworthy.

**Disposition:** the first operation is an independent
`ForwardingGate=DISABLED` converge/reread.

If this cannot be confirmed:

- no scaffold observation is trusted as an activation basis;
- no scaffold mutation occurs;
- no structural transaction runs;
- result is `INITIAL_CONTAINMENT_FAILED`.

This remains below user policy semantics and acts only inside the managed namespace.

## Finding F2 — exact scaffold and scaffold-only repair are different states

`compare_payload_nft_scaffold(...)` deliberately reports every non-scaffold table object as
`unclassified_objects`. That is correct for the scaffold-only mutation unit but would be too
strict for a full activation: an exact scaffold may legitimately already contain Profile,
Device, NAT or publication-local rules.

Blindly calling `prepare_payload_nft_scaffold_once(...)` for every activation would therefore
reject valid already-materialized policy.

**Disposition:**

```text
OWNED + exact invariant scaffold
    -> skip scaffold-only prepare
    -> let complete structural transaction classify all coexisting objects
```

Rootless regression verifies that an exact scaffold with an existing policy rule does not
call the scaffold helper.

## Finding F3 — incomplete scaffold plus coexisting objects remains bounded failure

The existing scaffold preparation evidence supports:

- absent marked table -> create full scaffold atomically;
- owned table with missing invariant chains and no other objects -> add missing scaffold
  chains;
- conflict/unclassified scaffold-only scope -> refuse mutation.

It does **not** prove arbitrary repair of a partially damaged scaffold while other policy
objects coexist.

**Disposition:**

```text
incomplete scaffold + non-scaffold objects
    -> SCAFFOLD_CONFLICT
    -> no scaffold repair
    -> no structural transaction
    -> confirm/re-establish ForwardingGate=DISABLED
```

This is not promoted into a product limitation. It is the safe current recovery boundary.
A later cleanup/recovery unit may broaden recoverable partial-state shapes only with its own
ownership/evidence proof.

## Finding F4 — scaffold preparation is invoked only when necessary

Activation performs one contained scaffold observation first.

Cases:

```text
ABSENT
    -> existing guarded scaffold bootstrap

OWNED + missing chains + scaffold-only contents
    -> existing guarded scaffold repair

OWNED + exact scaffold
    -> no scaffold mutation

marker/scaffold conflict
    -> fail closed
```

No duplicate scaffold model or new nft mutation mechanism is introduced.

## Finding F5 — lower failures are never retried by activation

The activation subassembly is not a reconciliation loop.

If scaffold preparation or the structural transaction fails, the failed lower operation is
not invoked again.

The only subsequent action is a separate safety-containment convergence:

```text
ForwardingGate = DISABLED
```

A later Manager reconciliation may start a new activation from fresh state. That later
operation is not a continuation/replay of this failed attempt.

## Finding F6 — failure containment has its own observable failure

A lower operation may fail while payload forwarding is unexpectedly enabled or its effective
state is uncertain.

Activation therefore records the original lower failure and performs one explicit containment
attempt.

Outcomes:

- containment confirmed -> return the original scaffold/structural failure category;
- containment unconfirmed -> return `FAILURE_CONTAINMENT_FAILED` while preserving
  `failure_status` for the original failure.

This prevents a policy failure and a failure to re-establish the safety boundary from being
collapsed into one opaque diagnostic.

## Finding F7 — READY is inherited from the strong structural postcondition

Activation does not invent a weaker readiness check.

The structural transaction already requires:

- exact route/RPDB state;
- exact composite nft state;
- current interface generation;
- verified forwarding activation;
- fresh post-activation whole-state confirmation.

Therefore activation reports `READY` only when
`StructuralPolicyTransactionResult.confirmed` is true.

No extra command-success shortcut is added.

## Finding F8 — zero-path Profile is a valid READY state

A Profile with no current VPN path remains a policy domain. Readiness does not require an
external VPN process/interface to exist when the normalized desired state is zero-path.

The privileged activation integration starts with:

- no `vpn_gate` table;
- `ip_forward=1`;
- a live ambient/main route from host traffic to ALT.

Activation bootstraps the four-chain invariant scaffold, converges:

- desired Profile table;
- terminal blackhole default;
- host-boundary RPDB dispatch;
- no ordinary VPN path route;
- no Profile forward-allow rules;

then verifies exact state and re-enables forwarding.

Real host traffic remains blocked and cannot fall through to the ambient ALT route.

This proves READY means “required current policy is safely materialized”, not “a VPN path
currently exists”.

## Finding F9 — subsequent current-path activation uses the same boundary

The same privileged environment then supplies a current VPN path and calls
`activate_network_policy(...)` again.

The exact scaffold is recognized and **not** sent through scaffold-only repair.

The complete structural transaction adds the desired path route and Profile nft admission,
keeps the existing payload dispatch/guard semantics, verifies exact state, activates
forwarding and real UDP traffic reaches VPN.

Thus the subassembly covers both startup-like bootstrap and a later already-scaffolded
activation without two code paths.

## Evidence

### Rootless baseline

Workflow `43963746909`: **SUCCESS**

```text
Ran 467 tests
OK
```

Activation decision-table coverage includes:

- absent scaffold bootstrap;
- exact scaffold with coexisting policy objects;
- partial scaffold-only repair;
- partial scaffold plus other objects refusal;
- reserved nft owner conflict;
- scaffold observation failure;
- structural transaction failure with no retry;
- initial containment failure;
- failure re-containment failure as a distinct result.

### Privileged Linux evidence

Same workflow, `linux-payload-forward`: **SUCCESS**

```text
NETWORK_POLICY_ACTIVATION_ZERO_PATH_BOOTSTRAP=PASS
NETWORK_POLICY_ACTIVATION_CURRENT_PATH=PASS
NG3 network policy activation integration: PASS
```

The test uses disposable network namespaces and real:

- iproute2 route/RPDB state;
- nftables;
- `net.ipv4.ip_forward`;
- forwarded UDP traffic.

## Component-model review

The new unit is procedural assembly around existing lower Executor/Driver boundaries.

It is **not**:

- a LifecycleManager;
- a new network-policy Manager;
- a retry Agent;
- a persistent transaction owner;
- a status aggregator.

It stores no long-lived state and has no autonomous scheduling behavior.

## Simplification review

Not introduced:

- generic phase framework;
- lifecycle state machine;
- retry counter/backoff;
- rollback journal;
- durable activation history;
- duplicate nft observer;
- duplicate route/RPDB observer;
- new kernel mutation Driver;
- new desired-state grammar;
- global readiness registry.

The implementation is one synchronous bounded function because the accepted requirements need
a verified result, not a new persistent component.

## Residual lifecycle boundaries

This PASS does **not** mean full `start` / `stop` / `restart` implementation is complete.

Still separate:

- instance ownership/exclusion;
- creation/verification of the managed network namespace and boundary links;
- config load/validation sequencing;
- complete semantic config/binding -> lower desired-state assembly;
- runtime Manager reconciliation scheduling;
- shutdown/quiesce/cleanup;
- RuntimeStatusAgent publication;
- concrete control-surface CLI/service integration.

The activation unit accepts already-normalized lower desired state and must remain reusable
inside those later phases.

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

The lower network-policy startup/reconciliation path now has one explicit activation
subassembly from verified containment through scaffold bootstrap/repair and complete
structural convergence to truthful READY. It does not broaden lifecycle scope or hide retry
semantics.
