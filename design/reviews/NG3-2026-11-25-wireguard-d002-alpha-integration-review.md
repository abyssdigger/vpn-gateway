# NG3 D.002 alpha runtime integration review — 2026-11-25

**Review unit:** alpha invocation and A.008 publication of D.002 runtime reconciliation  
**Reviewed implementation head:** `ac8969d706d9127308df28f1eb3ea5f5515cc57f`  
**Requirements:** `VPNG-U001-R1.R3.R8*`, `VPNG-M001-R2.R1*`  
**Architecture:** A.001, A.008, C.001, D.001, D.002, D.003  
**Evidence:** `EV-00240`

## Verdict

**PASS — D.002 is now in the normal alpha runtime reconciliation path and its authoritative
current realization reaches A.008 without conflating no-owner, local failure, or unrelated
Profile state.**

The only remaining generalized R8 materialization gap is R8.R6: A.007 evidence currentness
still lacks the applicable D.002 ownership generation.

## Findings and dispositions

### F1 — D.002 must run only after its shared lower probe plane exists

**Decision:** accepted.

Alpha invokes D.002 only when the current availability cycle has a confirmed full-union
probe-routing transaction. D.002 then obtains its own fresh owner-scoped readiness per physical
attempt through EV-00230; it does not reuse A.007's scoped precondition.

### F2 — startup, periodic and explicit triggers must use one retained Manager state

**Decision:** accepted.

One coordinator and D.003 enforcer live for the daemon lifetime. Startup performs the initial
trigger before READY. Periodic normal reconciliation calls the same coordinator, preserving
D.002 sticky/reserve state. Protective-mode normal-release uses the same normal reconciliation
function, providing the explicit trigger without a second selection implementation.

### F3 — confirmed no-owner is not a local runtime failure

**Decision:** accepted.

Alpha gates on `WireGuardPeerRuntimeResult.confirmed`, not `.ready`. Therefore a
fresh-confirmed D.003 no-owner state remains a truthful current unavailable-group realization
rather than causing startup/reconciliation failure merely because no remote candidate replied.

### F4 — local D.002 problem must be visible without invalidating unrelated state

**Decision:** accepted.

When D.002 returns an authoritative problem realization during periodic operation, A.008 keeps
that typed realization, marks global readiness DEGRADED and retains already confirmed
Profile/effective and A.007 projections. The new `mark_degraded` status operation changes only
readiness/problem/explicit unknown fields.

### F5 — a failed prerequisite must not leave old D.002 status current

**Decision:** fixed during review.

If D.001 is unconfirmed, or payload/A.007 work prevents a fresh D.002 trigger, alpha clears the
old D.002 realization before publication and marks `wireguard_peer_realizations` unknown when
managed groups are configured. Confirmed D.001 shutdown likewise clears D.002 status.

### F6 — R8.R6 is deliberately not hidden in runtime composition

**Decision:** remaining scope.

No A.007 evidence key was changed in this unit. A Profile observation that depends on a
recoverable WireGuard group still needs D.002 generation in its currentness context so an
ownership transfer invalidates prior evidence even when `LogicalPathId`, `wg0`, and ifindex
remain unchanged.

## Evidence

- alpha wiring/status primitive: `e37defdae2a7f3684895f3c9b0064de06aec5098`;
- focused helper/status tests + trace: `0ece364b5f1d2fee2926b66788692683f53d40d0`;
- stale-status review fix: `ac8969d706d9127308df28f1eb3ea5f5515cc57f`;
- run `45588860316`, unit job `139117569301` — **PASS**;
- actual-main lineage run `45588860717` — **PASS**.

## Remaining frontier

Implement R8.R6 by carrying the applicable D.002 generation into A.007 observation/evidence
currentness, prove that a confirmed ownership change invalidates prior Profile evidence behind
the same logical path/interface generation, and then reassess closure of R8/R8.R1.
