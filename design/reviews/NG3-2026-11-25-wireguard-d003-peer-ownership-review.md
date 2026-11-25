# NG3 D.003 WireGuard peer ownership review — 2026-11-25

**Review unit:** production D.003 `WireGuardPeerOwnershipEnforcer`  
**Source reviewed:** `dbb0d80381e875b7092684eebecba5dafd69c4f3`  
**Requirement:** `VPNG-U001-R1.R3.R8`  
**Architecture:** D.001, D.002, D.003  
**Stable evidence:** `EV-00100`

## Scope

This review checks only the lower exact `AllowedIPs` ownership Enforcer selected by D.003:
fresh ownership observation, complete desired-state application, interface-generation safety,
fresh postcondition confirmation and separation from D.002 peer-selection semantics.

## Findings

### F1 — D.003 remains a Direct Enforcer and does not acquire selection policy

**Decision:** accepted  
**Resolution:** clean

The production component receives a complete desired peer state. It does not inspect peer
preference order, probe outcomes, Profile semantics or historical ownership to choose an owner.
Its state is externally represented by input/output values and fresh WireGuard observation.

### F2 — stale D.001 interface generation cannot be mutated

**Decision:** accepted  
**Resolution:** clean

Every observation first fresh-observes D.001 ownership and requires the exact
`InterfaceIdentity` supplied by the caller. If the current owned base interface does not match,
convergence fails before issuing `wg set`.

### F3 — peer inventory is exact rather than best-effort

**Decision:** accepted  
**Resolution:** clean

Fresh `wg show ... dump` observation rejects duplicate, missing or unexpected peers. D.003
therefore cannot report a desired owner state as confirmed while silently ignoring another
current WireGuard peer.

### F4 — mutation is complete-state and confirmation-driven

**Decision:** accepted  
**Resolution:** clean

A mismatch produces one complete `wg set` invocation covering every managed peer. Command
success is not accepted as proof. A fresh exact observation is authoritative; conversely, a
command-side exception does not manufacture failure when the exact postcondition is freshly
confirmed.

### F5 — kernel evidence matches the selected D.003 boundary

**Decision:** accepted  
**Resolution:** clean

The dedicated integration creates the real D.001-owned `wg0`, confirms peer A as the sole
shared-prefix owner, transfers the complete state to peer B, verifies that both permanent
peer-specific probe prefixes remain, and verifies that the `wg0` interface generation does not
change.

## Verification

GitHub Actions run `45552662807` on the reviewed source:

- `unit` job `138997218110` — PASS;
- `linux-wireguard-peer-ownership` job `138997218400` — PASS.

The kernel job emitted:

- `D003_WG_OWNER_A_EXACT=PASS`;
- `D003_WG_FULL_STATE_TRANSFER=PASS`;
- `D003_WG_NO_INTERFACE_RESTART=PASS`;
- `D003_WG_RESULT=PASS`.

## Verdict

**PASS.** D.003 is fully materialized for its component-local contribution to
`VPNG-U001-R1.R3.R8`. D.002 still owns technical peer observation, selection and
peer-realization generation; this review does not close R8 as a whole.
