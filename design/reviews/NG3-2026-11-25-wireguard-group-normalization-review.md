# NG3 WireGuard group normalization review — 2026-11-25

**Review unit:** A.002 implementation of Profile-derived recoverable groups  
**Reviewed source:** `aa26d7845435c12b164070e97377eab2693923af`  
**Requirements:** `VPNG-U001-R1.R3.R8*`  
**Evidence:** `EV-00140`

## Verdict

**PASS — A.002 now fully materializes the accepted generalized R8 configuration boundary.**

`parse_current_config` emits typed groups keyed by `(profile_id, device_id)`, derives their
prefixes from the single existing Profile source, supports the canonical group-local
`peer_order`/reserve policy, and reuses a Profile availability description only when it is a
valid in-group ICMP target distinct from permanent peer probe targets.

## Review findings

- **No duplicate network-policy source:** group prefixes remain derived from
  `Profile.destinations`; no recoverable-group prefix list was introduced.
- **Membership source remains singular:** `device_membership.<device>` may refine only a
  Device already present in `device_order`; it cannot create membership.
- **Peer policy is strict:** default is all configured peers ordinary in declaration order;
  explicit order is a non-empty subset; unknown/duplicate peers and unsupported suffixes fail
  before runtime.
- **Description reuse does not merge evidence:** A.007 and D.002 still require distinct
  semantic owners/generations/readiness even when the same ICMP description qualifies for both.
- **Overlap remains deterministic:** existing Profile exact-prefix rejection and
  most-specific nesting are reused rather than duplicated.
- **Transitional debt is explicit:** `ManagedWireGuardConfig.shared_prefixes` remains only
  because current D.002 still consumes the old one-group shape. It is not a compatibility
  contract and should be removed when D.002 is generalized.

## Evidence

GitHub Actions run `45562870491`, unit job `139030635335`: **PASS**.  
Actual-main lineage run `45562870549`: **PASS**.

## Remaining boundary

D.002 does not yet consume `CurrentConfig.wireguard_groups`; C.001 group-probe owner/scoped
readiness and runtime A.007 invalidation/composition remain open. No D.002 status is promoted
by this review.
