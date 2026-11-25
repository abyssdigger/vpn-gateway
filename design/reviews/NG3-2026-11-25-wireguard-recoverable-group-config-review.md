# NG3 WireGuard recoverable-group configuration review — 2026-11-25

**Review unit:** canonical configuration identity for generalized WireGuard recovery  
**Requirements:** `VPNG-U001-R1.R3.R8*`  
**Research:** `design/NG3/research/NG3-2026-11-25-wireguard-group-config-identity.md`  
**Architecture:** A.002, D.002  
**Reviewed head:** `ebf8f75cc0a8338b088e47d84667c00c6a54a2c2`

## Verdict

**PASS — a separate recoverable-network-group configuration object is unnecessary for the
currently accepted R8 scope.**

The canonical group identity is derived from an existing Profile membership in a managed
WireGuard Device: `(profile_id, device_id)`. The group payload bundle is
`Profile.destinations`. This removes a duplicate source of network prefixes while retaining
independent peer ownership for different Profiles on the same `wg0`.

## Findings and dispositions

### F1 — an independent group prefix list would duplicate Profile policy

**Decision:** reject the duplicate object.

A Profile already has stable identity, payload destinations, Device membership and optional
availability description. Repeating those destinations under a new WireGuard group would
require consistency rules between two user-facing declarations of the same remote networks.

For current R8, each `(Profile, managed WireGuard Device)` membership is therefore one
recoverable group. Multiple destinations in one Profile move together; independently recovered
sets are represented by different Profiles. Cross-Profile atomic recovery is not introduced
without a requirement that needs it.

### F2 — existing Profile overlap semantics already close R8.R2.C1

**Decision:** accepted.

Exact destination-prefix duplication between enabled Profiles is already rejected. Different
prefix lengths are accepted only with deterministic most-specific classification. Derived
WireGuard groups inherit that same nesting, matching longest-prefix `AllowedIPs` selection.

A.002's contribution to `R8.R2.C1` is therefore corrected to `full`; a second group-prefix
overlap validator is neither required nor desirable.

### F3 — group-specific peer policy belongs to the Profile/Device membership

**Decision:** accepted.

The managed Device's peer declaration remains the authoritative peer set and default order.
Omitting an override means all peers in declaration order, all ordinary.

The selected canonical extension is optional membership detail:

```toml
[profile.corp.device_membership.wg-main]
peer_order = ["edge-a", "edge-b:reserve"]
```

The table is valid only for a Device already present exactly once in the Profile's
`device_order`; it cannot create membership. `peer_order` is a non-empty ordered subset of
that managed WireGuard Device's peer IDs. `:reserve` is local to this Profile/WireGuard group
and has the already accepted sticky/reserve meaning. Unknown peer IDs, duplicate IDs and
unknown suffixes are errors.

This table is not a generic option bag; no other fields are accepted by the current design.

### F4 — the Profile availability description can supply the optional group endpoint without a second knob

**Decision:** accepted with a strict qualification boundary.

For a managed WireGuard membership, the resolved Profile availability description can also be
used as D.002 group-end-to-end description only when it is the supported ICMP form, its target
is inside `Profile.destinations`, and the target is not a permanent peer `probe_target`.

This is **description reuse only**. A.007 Profile availability and D.002 group health retain
different semantic owner identities, readiness decisions and generations even if C.001 can
share/deduplicate physical lower state.

If the Profile has no active check or its selected target does not qualify, that WireGuard
group simply has no group endpoint; peer-failure recovery still applies.

### F5 — current parser is intentionally not promoted to generalized compliance

**Decision:** accepted.

`ManagedWireGuardConfig.shared_prefixes` remains a one-group prototype projection. The
current parser does not yet accept `profile.*.device_membership.*.peer_order` or emit typed
per-Profile WireGuard group policies, so A.002 remains `partial` for generalized R8.

Because no binding release exists, the eventual implementation may replace this pre-binding
normalized shape directly rather than retain a compatibility alias solely for development
history.

### F6 — runtime composition must still preserve evidence boundaries

**Decision:** explicit remaining gap.

Reusing the same availability description does not determine scheduling/order between internal
D.002 group recovery and A.007 Profile-level path adaptation. Runtime composition must keep
old-owner evidence stale across D.002 generation changes and must not turn one lower
`reply/no_reply/local_error` value into a merged peer/group/Profile verdict.

This is part of the already open D.002/A.007/C.001 runtime composition work, not a reason to
duplicate configuration.

## Evidence

- Design source `fc872c61e843e1ff52a529d87db4a038531c9ba4`.
- Overlap/traceability correction
  `ebf8f75cc0a8338b088e47d84667c00c6a54a2c2`.
- NG3 Python run `45562442221`, unit job `139029223706`: **PASS**.
- Actual-main lineage run `45562442401`: **PASS**.
- No production parser/runtime code was changed in this design unit.

## Next implementation boundary

Implement A.002 normalization for `device_membership.<device>.peer_order` and typed
per-Profile managed-WireGuard group policies. That implementation should remove the temporary
single `shared_prefixes` normalization rather than layering generalized groups on top of it.
D.002 runtime should be rewritten only against the typed generalized input.
