# NG3 D.003 split-group WireGuard ownership review — 2026-11-25

**Review unit:** production kernel acceptance of generalized D.003 complete AllowedIPs state  
**Reviewed implementation/evidence head:** `ae1b626a0f52f87b53996872793473e51bc0cc75`  
**Requirement:** `VPNG-U001-R1.R3.R8`  
**Architecture:** D.003  
**Evidence:** `EV-00190`

## Verdict

**PASS — D.003 exact full-state convergence is kernel-proven for simultaneous split ownership
of independent group bundles.**

## Findings and dispositions

### F1 — one-group transfer evidence was insufficient after R8 generalization

**Decision:** accepted / evidence extended.

EV-00100 proved one mutable bundle moving between two peers. The focused integration now adds a
second Profile-derived group and converges a complete state where the two bundles are owned by
different peers at the same time.

### F2 — exact split must not leave duplicate opposite ownership

**Decision:** accepted.

The postcondition checks that the corp prefix is present only on peer A and the storage prefix
only on peer B. This verifies the complete-state semantics rather than merely checking that the
new assignments appeared.

### F3 — permanent peer technical prefixes must survive split ownership

**Decision:** accepted.

Both peer-specific technical probe /32 values remain present in their respective peer
`AllowedIPs` after the split state is applied.

### F4 — group redistribution must not restart the common WireGuard interface

**Decision:** accepted.

The integration records the original managed `wg0` ifindex and confirms that the same ifindex
remains after full transfer and after simultaneous split ownership.

### F5 — no new D.003 policy belongs in the Enforcer

**Decision:** accepted.

The test supplies a complete desired peer -> AllowedIPs state. D.003 still does not know group
preference, reserve roles, endpoint health or candidate-selection history; those remain D.002
responsibilities.

## Evidence

Run `45577901507`, job `139080276853` emitted:

- `D003_WG_OWNER_A_EXACT=PASS`
- `D003_WG_FULL_STATE_TRANSFER=PASS`
- `D003_WG_NO_INTERFACE_RESTART=PASS`
- `D003_WG_SPLIT_GROUP_OWNERSHIP=PASS`
- `D003_WG_RESULT=PASS`

Unit job `139080276823` also passed.

## Remaining boundary

D.003 has no remaining generalized R8 lower-materialization gap identified by this review.
Remaining R8 work is in runtime composition/trigger/status/evidence invalidation above D.003.
