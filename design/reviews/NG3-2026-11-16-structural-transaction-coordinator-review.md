# VPN-GATE NG3 — bounded structural transaction coordinator review

**Date:** 2026-11-16  
**Cycle branch:** `ng3-design-cycle-20261116-cross-domain-structural-cont-35m`

## Scope

Review the explicit multi-step coordinator above the already accepted one-step cross-domain
structural Executor.

The one-step Executor remains responsible for:

- fresh whole-state observation;
- one safe structural mutation;
- strict postcondition progress;
- exact-state forwarding activation and final verification.

This unit answers only:

> how does one requested structural transaction continue across multiple verified one-step
> results without introducing a hidden retry loop or arbitrary retry budget?

## Verdict

**PASS.**

`converge_structural_policy(...)` is a bounded transaction coordinator whose continuation is
derived from strictly decreasing unresolved lower-state distance.

It retries no failure state and replays no mutation plan.

## Implementation

New module:

`design/NG3/code/python/rou/structural_policy_transaction.py`

Public contracts:

- `StructuralPolicyTransactionStatus`
  - `CONFIRMED`
  - `FAILED`
  - `REGRESSED`
- `StructuralPolicyTransactionResult`
- `converge_structural_policy(...)`

The one-step module now exposes:

`structural_policy_distance(StructuralPolicyComparison) -> int`

This distance is a technical convergence measure only. It counts unresolved recognized
route/RPDB/nft differences and is not user health, readiness or priority semantics.

## Continuation contract

The coordinator performs no lower observation or mutation itself. Each loop iteration invokes
the complete one-step Executor, which replans from fresh authoritative state.

Continuation is:

```text
STEP_APPLIED
    + initial/final comparison present
    + final distance < initial distance
        -> next fresh one-step attempt

CONFIRMED
        -> transaction CONFIRMED

any other one-step terminal status
        -> transaction FAILED
        -> no retry

unfinished next fresh attempt starts farther from desired
than the previous verified final state
        -> transaction REGRESSED
        -> no further attempt
```

A later reconciliation/audit may begin a new transaction from fresh state. It does not resume
the stopped transaction.

## Finding F1 — arbitrary max_steps would encode recovery policy in the wrong layer

The privileged integration previously used a local test helper with a fixed maximum number of
steps. That is acceptable as a test guard but not as the production transaction contract.

A fixed retry/step count would create an arbitrary implementation threshold unrelated to
semantic state size.

**Disposition:** production coordinator has no `max_steps` or retry counter.

## Finding F2 — structural distance provides a finite continuation proof

Every accepted `STEP_APPLIED` result is already required by the one-step Executor to make
strict progress.

The coordinator independently checks:

```text
final_distance < initial_distance
```

before it continues.

Distance is non-negative. If fresh state between attempts does not regress, repeated
continuation is therefore finite.

External progress is allowed: the next fresh initial distance may be smaller than the
previous final distance.

## Finding F3 — external regression must not become hidden retry behavior

A Manager/audit loop may legitimately encounter new drift while a transaction is in
progress.

Silently continuing indefinitely would turn this coordinator into a retry/reconciliation
policy owner.

**Disposition:** if an unfinished next attempt starts farther from desired than the prior
verified final state, the transaction returns `REGRESSED` and stops.

The caller may later start a new transaction from fresh state.

## Finding F4 — a fresh confirmed state remains authoritative even after inter-attempt drift

Regression can only be detected after the next one-step Executor has performed its own fresh
observation. That one-step attempt may itself safely repair the newly observed state and
reach exact verified `CONFIRMED`.

Returning `REGRESSED` after that would discard stronger fresh evidence and could report a
failed transaction while forwarding is correctly active.

**Disposition:** terminal `CONFIRMED` takes precedence. Inter-attempt regression stops only
an unfinished transaction.

A dedicated rootless regression covers this edge.

## Finding F5 — terminal one-step failures are never retried by the coordinator

Statuses such as:

- `PRECONDITION_FAILED`;
- `CONFLICT`;
- `BARRIER_FAILED`;
- `BARRIER_LOST`;
- `APPLY_FAILED`;
- `POSTCONDITION_FAILED`;
- `ACTIVATION_FAILED`;
- `FINAL_VERIFICATION_FAILED`;
- `SAFETY_RECLOSE_FAILED`;

terminate the transaction immediately as `FAILED`.

The coordinator does not reinterpret or retry them.

This preserves the separation between one requested transaction and a later Manager
reconciliation/audit policy.

## Privileged evidence

Final code workflow:

`43951894991` — **SUCCESS**

Rootless suite:

```text
Ran 458 tests
OK
```

Privileged structural integration marker:

```text
STRUCTURAL_CROSS_DOMAIN_TRANSACTION_COORDINATOR=PASS
NG3 cross-domain structural convergence integration: PASS
```

The live scenario first forces a same-name/new-ifindex stale-generation refusal, then supplies
the new current interface identity and invokes the production coordinator.

The coordinator performs the remaining multi-step structural restoration and reaches exact
confirmed forwarding through the new VPN generation.

## Component-model review

The coordinator is procedural Executor orchestration, not a new Engine or Manager.

It owns no long-lived desired state, timer, retry policy or publication state.

No new component category is introduced.

## Simplification review

Not introduced:

- retry count;
- timeout-based transaction loop;
- stale plan replay;
- rollback journal;
- persistent transaction state;
- background worker;
- cancellation/supersession semantics;
- another observation backend;
- another network-policy desired model.

## Residual boundary

This unit still does not implement full startup/shutdown lifecycle assembly.

A later startup orchestration may compose, in order:

1. containment / ForwardingGate closure;
2. invariant nft scaffold bootstrap/repair when needed;
3. complete structural transaction coordination;
4. readiness publication only after verified confirmation.

That future assembly must not duplicate the convergence/retry semantics closed here.

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

The complete structural transaction now has an explicit finite coordinator above the
fresh one-step Executor. Multi-step convergence no longer depends on integration-test-local
looping or an arbitrary step budget.
