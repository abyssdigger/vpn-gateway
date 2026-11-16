# VPN-GATE NG3 — Route-Priority Executor Attempt Code Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-primary-requirements-basis-40m`  
**Reviewed commit:** `178885596cb67b279c3aa0e0520fb67025721043`

## Scope

This unit adds the first executable NetworkPolicyExecutor orchestration boundary for the
already accepted pure-priority transition design.

It intentionally does not implement Linux route commands. It specifies the control contract
that a physical backend must obey.

## Requirement / architecture gate

Relevant accepted nodes:

- `VPNG0003-R3.R2`, `VPNG0003-R3.R3`, `VPNG0003-R3.R4`;
- `VPNG0004-R4.R2`, `VPNG0004-R4.R3`, `VPNG0004-R4.R3.R1`,
  `VPNG0004-R4.R5`;
- `VPNG0005-R5.R2`, `VPNG0005-R5.R3`;
- `VPNG0007-R7.R3`, `VPNG0007-R7.R5`.

The architecture already requires fresh observation before non-authoritative planning,
re-observation after partial failure, final postcondition verification and no stale-plan
replay. No requirement refinement was needed.

## Reviewed behavior

`converge_route_priority_once()` performs exactly one attempt:

1. obtain a fresh authoritative normalized owned-route snapshot;
2. derive a convergence plan from that snapshot;
3. execute semantic duplicate-cleanup or make-before-break move steps;
4. on any mutation failure:
   - stop immediately;
   - discard the unexecuted tail;
   - re-observe authoritative state;
   - return `APPLY_FAILED` without hidden retry;
5. after all mutation calls return, re-observe again;
6. return `SUCCESS` only when the fresh final snapshot exactly equals the desired
   one-metric-per-path assignment;
7. otherwise return `POSTCONDITION_FAILED`.

The result retains initial/final observations, complete planned steps, completed steps and
the failed semantic step when applicable.

## Expert review findings

No material defect was found in the bounded orchestration contract.

### R1 — broad backend exception capture

**Disposition:** accepted for this boundary.

The attempt boundary deliberately treats any ordinary backend mutation exception as failure
of the physical step, because continuing with the old plan would be unsafe regardless of the
backend error subtype.

Initial observation/planning failures are not converted into mutation results because no
network mutation has started. A failure of the mandatory re-observation itself also
propagates rather than pretending that an authoritative final state exists.

### R2 — no per-step global re-observation

**Disposition:** accepted.

The semantic `move_route_priority()` backend operation owns its local add-new -> verify ->
delete-old contract. The attempt-level Executor performs the mandatory fresh observation
after a failed step and after the complete successful plan.

If a backend silently fails to establish the expected state while returning success, a
subsequent step may fail and force re-observation, or the final fresh postcondition check
rejects false success. No desired state is reported as confirmed merely because commands
were issued.

## Evidence

GitHub Actions:

```text
workflow: NG3 Python
run:      43818702005
commit:   178885596cb67b279c3aa0e0520fb67025721043
result:   success
tests:    105
summary:  Ran 105 tests ... OK
```

The workflow also compiles the NG3 Python package.

Covered scenarios include:

- successful clean swap with a second authoritative observation;
- failure after route add but before old-route delete;
- immediate re-observation of the resulting duplicate state;
- next invocation re-planning from that duplicate rather than replaying stale steps;
- duplicate-cleanup failure;
- no-op transition still requiring fresh verification;
- final observed postcondition mismatch not being reported as success;
- preservation of initial and final evidence in the result.

## Residual boundary

Still not implemented:

- physical owned-route observation/normalization from Linux;
- exact owned route identity;
- physical `RoutePriorityMove` add/verify/delete realization;
- exact duplicate deletion;
- physical re-observation and route postcondition checks against the kernel;
- structural-policy guarded convergence.

Those remain explicit next review units.

## Final verdict

**PASS.**

The unit preserves the accepted safety/recovery semantics and closes the Executor
single-attempt orchestration contract without inventing retry policy or Linux representation
semantics.
