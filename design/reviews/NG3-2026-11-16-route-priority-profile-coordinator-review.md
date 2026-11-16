# VPN-GATE NG3 — Profile Multi-Domain Route-Priority Coordinator Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-primary-requirements-basis-40m`  
**Implementation/evidence commits reviewed:**  
- `85c2743a26b26527547bf5f47711936e507d80a4`
- `383bb0fd26b4130e582dc1ea4d27519d4a87ce78`
- `e885188cebfc92cd048cee75eaea1d833b171146`

## Scope

This unit closes the next layer above one physical route-key backend.

A Profile can contain multiple destination route-key domains. Each domain is independently
observable and independently recoverable, but Profile-level success must not be inferred
from the success of one domain or from stale earlier observations.

The coordinator therefore provides:

- deterministic domain ordering independent of user destination-list order;
- exactly one bounded fresh convergence attempt per supplied domain;
- no hidden retry/replay loop;
- continued processing of independent domains after one domain fails;
- one final fresh verification pass across every domain;
- Profile confirmation only when all final domain snapshots equal their desired assignments.

## Requirement / architecture gate

Relevant accepted nodes:

- `VPNG0003-R3.R1` through `R3.R4` for configured/effective path order;
- `VPNG0004-R4.R2`, `R4.R3.R1`, `R4.R5` for authoritative state and safe partial transitions;
- `VPNG0005-R5.R2`, `R5.R3` for recovery from current state;
- `VPNG0007-R7.R3`, `R7.R3.R1`, `R7.R5` for explicit bounded contracts.

The prior physical-domain review already established that aggregation across destinations
cannot replace per-route-key observation.

No new product promise was required.

## Accepted coordinator semantics

For one Profile:

```text
canonical ordered domains
    |
    +-> domain attempt 1: fresh observe -> plan -> bounded apply -> verify
    +-> domain attempt 2: fresh observe -> plan -> bounded apply -> verify
    ...
    |
    v
fresh final observation of every domain
    |
    v
SUCCESS only if all final snapshots equal desired state
```

A failed domain does not authorize stale replay in another domain. Each other domain's
attempt starts from its own fresh observation.

A domain attempt may report an operational failure while a later authoritative final
observation nevertheless proves that the desired state exists. In that case the diagnostic
attempt failure is retained, but Profile completion is determined by the confirmed
postcondition, consistent with lifecycle requirement semantics.

## Finding F1 — regression test confused attempt error channel with attempt result

**Severity:** test-only  
**Disposition:** fixed in `383bb0fd`

`converge_route_priority_once()` converts a physical mutation failure into an
`APPLY_FAILED` execution result after mandatory re-observation. It does not throw that
ordinary mutation failure to the coordinator.

The initial coordinator test incorrectly expected `attempt_error` to be populated.

The corrected test now distinguishes:

- `attempt_error`: failure to obtain an execution result at all;
- `attempt.status = APPLY_FAILED`: a bounded attempt completed with a recorded mutation
  failure;
- final `confirmed`: independent fresh postcondition truth.

The corrected scenario additionally proves that a reported attempt failure does not override
a later exact authoritative final postcondition.

## Evidence

Final GitHub Actions run:

```text
workflow: NG3 Python
run:      43820419873
commit:   e885188cebfc92cd048cee75eaea1d833b171146
unit:     144 tests, OK
linux-route-priority: PASS
overall:  success
```

The privileged Linux integration now exercises two real destination domains for one Profile
after first proving single-domain swap and duplicate-state recovery.

The integration verifies that:

- both domains converge to the same desired path order;
- the Profile coordinator reports SUCCESS;
- a subsequent direct observation of both physical domains confirms the desired final
  metrics.

## Review result

No material code defect remains in the bounded coordinator.

The implementation correctly rejects:

- an empty domain set;
- mixed Profile IDs in one coordinator call;
- duplicate domain identities.

It canonicalizes destination processing order rather than giving set-like destination input
an accidental user policy meaning.

## Residual boundary

Still outside this unit:

- generation/allocation of the complete set of physical route-key domain requests from
  normalized Profile policy;
- guarded structural-policy convergence when path membership/direction/filtering/NAT changes;
- RPDB/nft materialization;
- availability probe execution;
- full lifecycle/runtime scheduling.

## Final verdict

**PASS AFTER TEST FIX.**

The Profile-level pure-priority convergence path is now evidenced from deterministic pure
planning through real per-domain Linux mutation and final multi-domain postcondition
verification.
