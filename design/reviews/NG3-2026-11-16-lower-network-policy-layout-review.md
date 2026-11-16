# VPN-GATE NG3 — Shared Lower Network-Policy Ownership/Layout Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-lower-policy-layout-40m`

## Trigger

The preceding cycle deliberately stopped before choosing table IDs, route protocol markers,
RPDB priorities or metric namespaces inside the pure-priority backend.

Those values are shared lower network-policy resources and cannot be allocated correctly by
a route-priority helper in isolation.

## Requirement gate

The accepted requirements constrain the layout directly:

- zero-path Profiles remain structural/fail-closed domains;
- unknown/unconfirmed lower state cannot be treated as effective policy;
- cleanup/recovery must be based on proved owned state;
- unrelated host/network state must not become implicit product state;
- payload and probe desired policy are distinct owners even when one Adapter realizes both;
- implementation details must remain below stable internal contracts and out of user config.

No new user-visible requirement is needed.

## Selected ownership model

Semantic lower owners are:

```text
PayloadPolicyOwner(profile_id)
ProbePolicyOwner(profile_id, logical_path_id)
```

Kernel numbers are allocations **for** those owners, not their identity.

Payload routing allocates one internal table per enabled Profile. The table persists as a
fail-closed domain even when current path membership is zero.

Probe owner identity exists independently, but a probe table is allocated only if the
selected physical probe mechanism needs one.

## Selected resource layout

The lower platform contract supplies disjoint resource pools for:

- payload route tables;
- probe route tables when needed;
- payload RPDB priorities;
- probe RPDB priorities.

Route protocols are role markers for managed ordinary-path versus managed terminal/guard
routes. Their exact numeric values remain platform constants to be live-gated.

Per-Profile metric allocation supplies ordered preference slots, scratch space and a terminal
guard tier. Availability only permutes path ownership of existing preference slots.

Packet filtering/NAT uses one dedicated VPN-GATE nftables namespace with separate semantic
payload/probe owner scopes.

## Cleanup model

A reserved numeric range is not itself proof of ownership.

Cleanup must combine:

- reserved resource scope;
- exact expected role/shape;
- semantic allocation context where available.

Unexpected objects inside reserved spaces are ownership conflicts and therefore fail closed.

This is necessary because the managed namespace may also contain administrator-provisioned
VPN endpoint state that VPN-GATE does not own.

## Configuration transitions

Numeric allocations need not be stable across a structural configuration change.

A deterministic rank-based allocator is acceptable and avoids persistent allocation
journals. When owner membership/rank changes, the transition is structural and must use the
restrictive barrier/reconciliation path.

Pure-priority convergence is valid only while the physical realization/allocation remains
unchanged.

## Historical evidence disposition

NG1/RC2/RC3 provide useful evidence for:

- per-Profile routing tables;
- destination-specific RPDB dispatch;
- terminal blackhole fail-closed routing;
- route protocol inventory/cleanup;
- Linux metric ordering.

Their old numeric constants are **not** imported normatively. NG3 will select concrete Linux
pools only after a platform-layout evidence unit proves the chosen ranges/commands.

## Rejected alternatives

### User-configured table/protocol/priority values

Rejected. They are implementation mechanics and would leak lower Linux representation into
product policy without a requirement.

### Stable hashed IDs from Profile strings

Rejected for now. Collision handling/persistence creates complexity that is unnecessary
because no requirement promises stable numeric resource IDs across structural config
changes.

### One global routing table for all Profiles

Rejected for the current design. Per-Profile tables keep zero-path fail-closed domains,
Profile-local path order and cleanup boundaries explicit and avoid coupling overlapping
Profile destinations into one mutable metric namespace.

### One kernel table per probe subject unconditionally

Rejected. Probe owner identity is required, but physical table allocation is demand-driven
by the selected probe mechanism.

## Next review unit

Implement a pure deterministic allocator **over an injected platform resource-space
contract**, without yet selecting production numeric constants.

That allocator should prove:

- disjoint owner allocation;
- deterministic ordering;
- capacity rejection before mutation;
- payload dispatch priority ordering;
- per-Profile metric-space derivation;
- stale-allocation cleanup enumerability from reserved ranges.

Concrete Linux numeric ranges remain a subsequent privileged evidence unit.

## Verdict

**PASS — shared lower ownership/allocation model accepted.**
