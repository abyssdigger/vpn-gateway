# NG3 shared probe-plane readiness boundary — 2026-11-25

## Question

After C.001 gained a distinct `WireGuardPeerProbeOwner` and D.002 gained a confirmed peer
executor, can alpha simply merge A.007 and D.002 probe desired state and call the existing
`verify_probe_execution_precondition` separately for each subset?

## Current lower behavior

No.

`compare_probe_routing()` observes every route in the reserved probe table pool and every
rule in the reserved probe-priority pool. Any observed physical object absent from the desired
argument is classified as stale.

`compare_probe_local()` similarly observes every nft rule carrying the probe-local owner
marker. It compares a physical union because semantic owner identity is intentionally not
encoded in nft. Any physical rule absent from the desired argument is stale.

Therefore, after both A.007 and D.002 are legitimately present, passing only the A.007 subset
to either comparator makes D.002 sibling state look stale, and vice versa.

## Selected boundary

The runtime composition needs three distinct concepts:

1. **Full accepted probe union.** All current A.007 and D.002 semantic owners participate in
   one deterministic resource allocation and one full lower desired union. Mutation/cleanup
   operates against this union so one consumer never deletes a sibling's legitimate state.
2. **Fresh physical snapshot.** One authoritative routing+nft+interface observation is taken
   after/between bounded convergence attempts.
3. **Owner-scoped readiness projection.** A consumer verifies only its semantic subset, but the
   verifier also receives the full accepted union. Physical objects belonging only to another
   accepted sibling are permitted rather than stale. A physical rule shared by multiple owners
   may satisfy each owner. An observed probe-owned object that belongs to no object in the full
   accepted union remains a real conflict and is not hidden as sibling state.

This separation means a missing or unconfirmed D.002-owned rule does not by itself have to
disable a fully exact A.007 owner. Conversely, an unattributed conflict in the shared owned
probe namespace remains fail-closed because no semantic owner can safely claim it.

## Consequence for current APIs

The current `ProbeExecutionPrecondition` value remains useful, and
`WireGuardPeerProbeExecutor` already consumes an exact key from such a value. The missing
piece is the comparison/projection layer that constructs scoped preconditions from
`(fresh snapshot, full accepted union, requested owner subset)`.

The existing `verify_probe_execution_precondition(snapshot, desired, platform)` must not be
reused on a subset once sibling owners exist; its current whole-scope semantics are correct
for the pre-D.002 availability-only plane.

## Next implementation unit

Implement and unit-review owner-aware scoped comparison/readiness first, without alpha wiring.
Only then build a combined A.007+D.002 probe-plane assembly and change the Linux availability
cycle/runtime composition. This ordering keeps the existing Release-1 A.007 behavior intact
until sibling-owner exactness is mechanically representable.
