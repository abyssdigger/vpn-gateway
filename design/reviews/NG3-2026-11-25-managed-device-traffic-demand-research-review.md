# NG3 managed Device traffic-demand research review — 2026-11-25

**Review unit:** product/architecture boundary for traffic-triggered managed-Device presence  
**Reviewed research:** `design/NG3/research/NG3-2026-11-25-managed-device-traffic-demand.md`  
**Reviewed source:** `3936334c43794ddfd9497ca8b7d8c7cc8aa2296f`  
**Current closed basis:** `VPNG-U001-R1.R3.R7*`; A.012, D.001, C.004

## Scope

Review whether the research identifies the smallest honest next boundary for connect/disconnect
on actual traffic demand without silently changing the now-closed structural-demand lifecycle,
inventing packet-buffering semantics, or creating a second lifecycle owner.

This review does not accept a new Requirement, configuration grammar, component or kernel
mechanism.

## Findings and dispositions

### F1 — traffic-driven presence is a new demand policy, not unfinished R7 work

**Decision:** accepted.

R7.R3 already defines the complete current baseline: an enabled managed Device referenced by an
enabled Profile is structurally demanded. It explicitly excludes first-packet activation and
idle-time shutdown.

The research therefore correctly treats traffic-driven presence as a later optional capability.
A future normative addition must re-review the affected R7 decomposition/status instead of
silently weakening the closed R7.R3 contract.

### F2 — the lower lifecycle stack is already sufficient

**Decision:** accepted.

The research preserves the existing ownership chain:

`presence demand -> A.012 -> D.001 -> confirmed realization -> C.004 binding`.

Withdrawal likewise reuses the accepted dependency-release gate before D.001 absence. No
technical evidence currently justifies a second Device Manager or a second VPN lifecycle API.

A future traffic/timer participant, if the product semantics require one, should publish demand
rather than actuate the base VPN behind A.012.

### F3 — first-packet handling is correctly exposed as a product choice

**Decision:** accepted.

`trigger-and-drop` and bounded `hold-and-forward` are observably different promises,
especially for UDP. The latter introduces queue bounds, timeout, ordering, cleanup and policy
revalidation responsibilities that are not present in A.012.

No implementation may select one of these implicitly.

### F4 — inbound wake cannot be inferred from ordinary payload demand

**Decision:** accepted.

When the VPN realization does not exist, remote payload is not available inside the managed
domain to act as its own wake trigger. A remote/external wake path would be a separate
capability and may be technology-specific.

The research correctly leaves the first direction scope to the projectholder rather than
pretending existing Profile `direction` already defines sleep/wake behavior.

### F5 — multiple eligible Devices need lifecycle-selection semantics

**Decision:** accepted.

Existing `device_order`, reserve and availability semantics order/qualify paths; they do not
say which absent VPN instances must be created for one traffic trigger. Wake-all,
highest-baseline-only and prefer-already-present are materially different policies.

The research therefore correctly blocks implementation on an explicit choice.

### F6 — idle must be based on product payload semantics, not VPN chatter

**Decision:** accepted.

WireGuard keepalive, peer/group probes and A.007 probes are evidence/control traffic and cannot
be allowed to keep a Device awake merely because they increment interface counters.

The remaining distinction between packet-idle and established-flow pinning is also correctly
left unresolved: current return-affinity semantics do not by themselves define whether the
product may intentionally withdraw an otherwise usable Device after payload silence.

### F7 — shared-Device demand must aggregate before withdrawal

**Decision:** accepted.

Because the lifecycle object is the Device, one Profile cannot withdraw presence while another
applicable source still demands the same Device. The OR-aggregation invariant is required
independently of the eventual configuration surface.

### F8 — configuration grammar and lower mechanism are intentionally deferred

**Decision:** accepted.

Candidate spellings such as `presence = "traffic"` and `idle_timeout` remain illustrative
only. Device-level versus Profile-membership-level policy is a later user-facing design
decision.

Likewise no nft/queue/conntrack mechanism is selected before the product semantics determine
what must be proven. The proposed experiments are correctly conditional:

- any mode must prove a trigger is observable at zero current paths without bypass;
- hold-and-forward needs bounded queue/reinjection evidence;
- flow-pinned idle needs an accepted current-flow truth source.

## Product decisions required before the next normative/implementation unit

The research is complete, but dependent work is blocked on four projectholder decisions:

1. **D1 first outbound packet:** trigger-and-drop or bounded hold-and-forward?
2. **D2 first direction scope:** outbound-capable only, or require a remote/external wake
   contract from the first version?
3. **D3 multiple eligible Devices:** wake all, wake highest-baseline only, or allow an already
   present eligible Device to win over an absent baseline leader?
4. **D4 idle:** packet-idle timeout, or established-flow pinning plus timeout only after flow
   disappearance?

Configuration granularity remains a subsequent user-facing design choice once these behavior
decisions define what must be represented.

## Requirement-state impact

None in this unit. No Requirement/Constraint is opened, modified or closed. There are no new
`decomp`, `unreal`, `broken` or `rejected_closure` links.

## Verdict

**PASS — the research establishes a sufficient boundary for the next managed-Device
traffic-demand decision. Existing A.012/D.001 lifecycle machinery should remain unchanged until
D1–D4 are decided; requirement/configuration/implementation work for this capability is
blocked on those explicit product choices.**
