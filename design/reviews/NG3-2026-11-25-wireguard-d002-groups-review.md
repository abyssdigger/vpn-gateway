# NG3 generalized D.002 WireGuard group Manager review — 2026-11-25

**Review unit:** D.002 migration from one global selected peer to typed recoverable groups  
**Reviewed implementation head:** `c93b98e256ac56eb74056d111f97ab46620da9cd`  
**Requirements:** `VPNG-U001-R1.R3.R8*`  
**Evidence:** `EV-00150`

## Verdict

**PASS — D.002 core now implements independent Profile-derived recoverable-group ownership
against the accepted typed A.002 contract.**

The old one-group selected-peer state is gone from the Manager API. One D.002 realization can
simultaneously assign different Profile groups to different peers and construct one complete
D.003 desired `AllowedIPs` state.

## Findings and dispositions

### F1 — group selection must not recreate a second prefix source

**Decision:** accepted.

D.002 receives `ManagedWireGuardGroupConfig`; group prefixes are already derived by A.002
from `Profile.destinations`. The transitional `ManagedWireGuardConfig.shared_prefixes`
bridge was removed from the config type/parser/tests and the D.003 integration helper now reads
the typed group contract.

### F2 — peer health may be shared, group ownership may not

**Decision:** accepted.

One reconciliation caches a fresh technical observation per peer and may reuse it when several
groups evaluate the same peer. The selected owner remains group-specific. The tests prove two
groups can choose different peers while each physical peer is probed at most once in that
reconciliation.

### F3 — ordinary stickiness and reserve failback are correctly group-local

**Decision:** accepted.

A fresh positive check of an ordinary current owner retains that owner without probing
preferred standby peers. A usable reserve owner may be displaced by a more-preferred
fresh-confirmed ordinary membership. The reserve bit is read from the group membership, not
the global peer definition.

### F4 — peer failure has independent group scope

**Decision:** accepted.

When a current peer is confirmed unavailable, only groups currently depending on it need
reselection. Another group can keep its different current owner. If no allowed peer is
fresh-confirmed suitable for one group, that group becomes no-owner while other groups can
remain confirmed; D.003 removes only the unowned group's mutable payload prefixes.

### F5 — uncertainty does not masquerade as failover evidence

**Decision:** accepted.

A `local_error` on the current owner invalidates the current D.002 generation and prevents a
D.003 mutation for that reconciliation. Alternative candidates are selected only on explicit
`REPLY`; a local execution problem is never converted to `NO_REPLY`.

### F6 — optional group endpoint must not be silently ignored

**Decision:** accepted as an explicit remaining gap.

A typed group carrying an optional end-to-end availability description is currently rejected
before probe or ownership mutation. D.002 therefore does not claim R8.R3.R1 materialization
until a distinct group-probe semantic owner, C.001 readiness projection and executor exist.

### F7 — defensive typed boundary validation

**Decision:** accepted / fixed by `c93b98e256ac56eb74056d111f97ab46620da9cd`.

Malformed group membership entries are type-checked before their fields are read, and payload
prefix entries are checked before ownership projection. Normal A.002 output was unaffected.

## Evidence

- Generalized core: `c8f8be1610d8b3e688b9b6a8c0509bf172a9ef5b`.
- One-group bridge retirement: `870b3f52ffc5adbe125eb72506ac76838e8e08ce`.
- Defensive validation fix / reviewed head:
  `c93b98e256ac56eb74056d111f97ab46620da9cd`.
- Final NG3 Python run `45571166454`, unit job `139058000826`: **PASS**.
- Actual-main lineage for the reviewed branch: **PASS**.

## Remaining boundary

D.002 remains partial overall. Next required lower unit is the already designed C.001
owner-scoped readiness comparison; after that, add a distinct group-endpoint probe owner and
executor, then compose D.002 with alpha triggers/status and invalidate dependent A.007 evidence
on D.002 generation changes. D.003 also still needs focused kernel evidence for simultaneous
split ownership of multiple group bundles before its generalized R8 edge returns to `full`.
