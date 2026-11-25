# NG3 generalized R8 requirement closure review — 2026-11-25

**Review unit:** final architecture closure of generalized managed-WireGuard recoverable-group behavior  
**Baseline:** `6d7e1137cfcdf42a444e59fef3ee983c68928b6b`  
**Requirement family:** `VPNG-U001-R1.R3.R8*`  
**Architecture:** A.002, A.004, A.007, C.001, C.008, D.002, D.003  
**Evidence basis:** `EV-00140`, `EV-00150`, `EV-00180`, `EV-00190`,
`EV-00200`, `EV-00210`, `EV-00230`, `EV-00240`, `EV-00280`

## Scope

Re-review the complete R8 family after the final R8.R6 generation-currentness work and the
post-closure component-materialization audit. The question is whether any current R8 node still
lacks an accepted architecture decision, not whether another component can be invented around
the already working behavior.

## Findings and dispositions

### F1 — the generalized multi-group product contract is fully represented

**Decision:** accepted.

A.002 derives one recoverable group per enabled `(Profile, managed WireGuard Device)`
membership from the existing `Profile.destinations` source, with an optional explicit
group-local ordered peer subset and reserve role. D.002 consumes that typed contract directly
and can hold different current owners for different groups on the same `wg0`.

This satisfies R8 and R8.R2 without creating a duplicate user-owned prefix list.

### F2 — R8.R2.C1 has an accepted limiting realization

**Decision:** accepted.

A.002 is explicitly constrained by R8.R2.C1. The configuration boundary rejects ambiguous
effective group-prefix ownership rather than asking D.002/D.003 to guess a desired
`AllowedIPs` state. Existing Profile exact-prefix rejection and deterministic most-specific
classification remain the single overlap semantics.

No second overlap policy is required for current closure.

### F3 — peer suitability remains distinct from group/Profile availability

**Decision:** accepted.

R8.R1 is materialized by stable per-peer in-tunnel probe targets and peer-scoped evidence.
A positive peer result does not itself prove group or Profile reachability. C.001/C.008 and
D.002 preserve distinct semantic owners even when physical ICMP machinery is shared.

### F4 — both technical-peer failover and optional group endpoint validation are complete

**Decision:** accepted.

For R8.R3, confirmed technical failure of the current peer can reselect only the affected
groups among their allowed peers even when no group endpoint is configured.

For R8.R3.R1, endpoint-bearing groups follow the accepted order:
fresh technical peer confirmation -> exact D.003 candidate ownership -> fresh group endpoint
check. Confirmed endpoint failure rejects only that group candidate; local execution error is
not converted into remote unavailability.

### F5 — ordinary stickiness and reserve failback are group-local and complete

**Decision:** accepted.

R8.R4 is materialized in D.002: a healthy ordinary current owner remains sticky when a more
preferred ordinary peer recovers, while a reserve owner may fail back to a more preferred
fresh-confirmed ordinary candidate. Reserve is membership-local, not a global peer property.

### F6 — ownership changes are exact, confirmed and fail closed

**Decision:** accepted.

R8.R5 is materialized by D.002 + D.003. Ownership publication follows fresh confirmation of
the complete peer -> `AllowedIPs` state. If no allowed candidate is confirmed suitable, the
group converges to no-owner and its mutable payload prefixes are removed instead of remaining
on a known-bad peer.

`EV-00190` proves simultaneous split ownership of independent group bundles while permanent
peer probe /32s remain present and the shared WireGuard ifindex does not change.

### F7 — R8.R6 stale-evidence invalidation is materially complete

**Decision:** accepted.

`EV-00280` and the accepted R8.R6 runtime review establish the normal ordering

`C.001 prepare -> D.002 reconcile/generation -> A.007 fresh observation -> A.004 priority`.

A D.002 ownership-generation change invalidates dependent A.007 evidence even when
`LogicalPathId`, interface name and ifindex are unchanged. Confirmed no-owner is a valid
current generation; an applicable but unconfirmed D.002 dependency blocks only dependent
remote evidence.

### F8 — no component-local R8 materialization gap remains

**Decision:** accepted.

The post-R8.R6 materialization-status review corrected the last stale A.004/C.001
`partial` annotations. Current R8-family component obligations are `full`; the only
remaining architecture `partial` edge belongs to an unrelated requirement.

The current R8 nodes have no active decomposition blocker, unrealizability link, broken
solution link or rejected closure.

## Requirement disposition

The following current nodes move from `open` to `closed` without Statement changes:

- `VPNG-U001-R1.R3.R8`;
- `VPNG-U001-R1.R3.R8.R1`;
- `VPNG-U001-R1.R3.R8.R2`;
- `VPNG-U001-R1.R3.R8.R2.C1`;
- `VPNG-U001-R1.R3.R8.R3`;
- `VPNG-U001-R1.R3.R8.R3.R1`;
- `VPNG-U001-R1.R3.R8.R4`;
- `VPNG-U001-R1.R3.R8.R5`;
- `VPNG-U001-R1.R3.R8.R6`.

All retain `decomposition: complete`.

## Verdict

**PASS — generalized managed-WireGuard recoverable-group behavior has sufficient accepted
architecture and evidence for closure across the complete R8 family.**
