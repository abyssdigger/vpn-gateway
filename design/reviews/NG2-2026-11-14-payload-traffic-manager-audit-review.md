# NG2 — PayloadTrafficManager audit/reconcile review

**Дата:** 2026-11-14  
**Тип:** autonomous internal development review  
**Scope:** one deterministic drift/audit reconcile pass

## Findings

### A1 — repair must be convergence-driven

**Disposition:** accepted and implemented.

audit() repairs only when PayloadRulesState.convergence != MATCHED.

Therefore MATCHED+READY, MATCHED+DEGRADED and MATCHED+ISOLATED are all valid non-drift
states. In particular, zero-path protective isolation does not create a repair loop when it
is the correct materialization of current desired rules.

### A2 — audit refresh ActionResult is not state

**Disposition:** accepted and implemented.

audit() always interprets get_last_state() through PayloadRulesStateCalculator. A failed
renew_state() produces repair/UNKNOWN behavior according to observation, not a synthetic
FAILED verdict.

### A3 — repair reuses current desired without a new RequestEvent

**Disposition:** accepted and implemented.

When current rules are divergent or unknown, audit() calls apply(self, latest_desired).
No new RequestEvent or causal replay is needed.

### A4 — failed repair is observed again

**Disposition:** accepted and implemented.

If repair apply() fails, the same request-path helper performs renew_state(self), reads
get_last_state(self), recalculates rules state and publishes only the final provable current
projection.

### A5 — successful synchronous repair need not publish transient drift

**Disposition:** accepted.

If audit observes drift, repairs it immediately, and final state equals the previously
published state, no intermediate drift InfoEvent is emitted. InfoEvents represent current
state, not operation history.

### A6 — recovery after published degradation must be visible

**Disposition:** accepted and covered.

A failed repair can publish ISOLATED. A later successful audit then publishes READY/MATCHED,
because semantic dedup compares against the last successfully published projection.

### A7 — audit scheduling remains outside this unit

**Disposition:** accepted.

The implementation provides one deterministic audit() pass only. Timer/event cadence and
retry scheduling are separate Engine runtime concerns and are not embedded into the
semantic reconcile method.

## Component/domain review

No new architectural component was introduced.

PayloadTrafficManager remains the only Engine in this path. Its synchronous dependencies
remain PayloadRulesCalculator, PayloadRulesStateCalculator and NetworkRulesAdapter.

The audit path does not know Linux mutation order, barriers, nft/routes/sysctl mechanics or
Adapter allocation state.

## Evidence

NG2 Python CI passed on commit 5c6f878446a1b2e25d09c836011c143508ac1325.

Tests cover:

- audit before first request is a no-op;
- matched audit refreshes without reapply;
- matched isolated intent is not repaired;
- drift is repaired from current desired without a new request;
- failed repair publishes observed isolation;
- unknown/stale observation triggers repair;
- successful repair suppresses transient drift publication when final state is unchanged;
- recovery after a previously published isolated state publishes READY/MATCHED.

## Final verdict

**PASS.**

No unresolved finding blocks this review unit.

Next work should move below the semantic boundary into NetworkRulesAdapter implementation,
or separately define RuntimeStateManager ProfileState mapping. The current
PayloadTrafficManager semantic control loop is complete enough to support either.
