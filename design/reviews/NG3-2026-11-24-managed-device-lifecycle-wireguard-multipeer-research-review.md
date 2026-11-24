# NG3 2026-11-24 — managed Device lifecycle / WireGuard multipeer research review

**Scope:** review the initial research direction for optional VPN-GATE-owned Device lifecycle
and the first WireGuard use case with multiple peers serving one remote subnet.

**Research:** `design/NG3/research/NG3-2026-11-24-managed-device-lifecycle-wireguard-multipeer.md`

## Verdict

**PASS — RESEARCH DIRECTION ACCEPTED; NO REQUIREMENT OR ARCHITECTURE CLOSURE CLAIMED.**

The research is sufficiently constrained to proceed to focused requirement design and a
10-peer WireGuard experiment. Production implementation is not authorized by this verdict.

## Findings and dispositions

### F1 — optional management preserves the existing external Device contract

**Decision:** accepted.  
**Resolution:** fixed as research direction.

The future managed path is explicit. A Device without the new management intent remains
administrator/external-lifecycle owned: VPN-GATE does not create its configuration, adopt its
service or stop it.

The current `VPNPathAdapter` remains the source of truth for the concrete endpoint after either
an external or a VPN-GATE-owned runtime creates it.

### F2 — existing structural Device demand is the correct first on-demand boundary

**Decision:** accepted.  
**Resolution:** fixed as research direction.

The existing condition “enabled Device referenced by at least one enabled Profile” already
defines when the product has structural need for a Device. Reusing that condition avoids
inventing packet-triggered lifecycle semantics.

Traffic-triggered connection and idle shutdown remain a separate future question because they
require first-packet, inbound-traffic and idle-policy semantics.

### F3 — configuration generation and runtime generation must be distinct

**Decision:** accepted.  
**Resolution:** fixed as research direction.

Writing a generated VPN configuration is not proof that it is active. The manager must own a
desired configuration generation and confirm the running generation. Until a protocol-specific
reload contract is proven, stop / verify absence / regenerate / start is the simpler candidate.

### F4 — WireGuard peers behind one wg0 must not become synthetic LogicalPathId values

**Decision:** accepted.  
**Resolution:** fixed.

EXP-086/087 and the current binding model agree on the boundary: all peers behind one `wg0`
share one interface generation. Creating synthetic generic paths would misrepresent
`PathBinding`.

The peers are therefore integration-internal alternatives beneath one ordinary logical path.

### F5 — WireGuard base lifecycle and dynamic AllowedIPs ownership are separate responsibilities

**Decision:** accepted.  
**Resolution:** fixed.

The base configuration may own interface identity and permanent peer facts, including unique
in-tunnel probe /32s. Shared payload prefixes are runtime-owned state and must not be repeated
as permanent configuration on every same-prefix peer.

Normal peer failover therefore changes `AllowedIPs` without restarting `wg0`.

### F6 — peer readiness cannot replace Profile availability

**Decision:** accepted.  
**Resolution:** fixed.

A peer-specific in-tunnel probe proves a useful WireGuard peer property, not reachability of
every Profile destination. Existing Profile-scoped availability remains semantically separate.

Because a peer switch changes the actual realization without changing `LogicalPathId` or
`wg0`, future availability context needs an integration-realization generation so stale
Profile evidence cannot survive a peer switch.

### F7 — first production-shaped experiment should remain narrow

**Decision:** accepted.

The next experiment should use one managed WireGuard Device, one `wg0`, ten peers, ten
permanent probe /32s and one shared payload-prefix group. It should cover initial no-owner
state, ordered failover, restart, failed apply and the transactional properties of multi-peer
`AllowedIPs` updates.

General per-prefix scheduling across multiple Profiles is intentionally not designed before
that lower contract is proven.

### F8 — normative work remains required before implementation

**Decision:** accepted.

The current first-release constraints permit externally owned VPN provisioning/lifecycle but
do not prohibit a later managed path. A new requirement branch is still required for explicit
management opt-in, ownership, lifecycle postconditions, configuration generations, secrets,
structural demand and the WireGuard-specific runtime owner.

## Result

The next safe development unit is requirement/candidate-experiment design, not production
Device Manager code.
