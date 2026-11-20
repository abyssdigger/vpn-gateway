# VPN-GATE NG3 — Structural Routing Desired-State / Activation Boundary Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-lower-policy-layout-40m`

> **Historical requirement note (2026-11-20):** this review was performed while
> `VPNG0004-R4.R1.R1` existed in the then-current tree with the meaning that a zero-path
> Profile remained fail-closed instead of falling through ambient routing. That node was later
> removed as redundant and mis-scoped: Profile persistence is covered by
> `VPNG0001-R1.R2.R4.R4.R2`, concrete-path membership by `VPNG0002-R2.R2.R2`, and the
> prohibition on forwarding managed traffic outside accepted policy by `VPNG0004-R4`.
> The reference below to `VPNG0004-R4.R1.R1` is a historical review fact, not a current
> requirement link.

## Trigger

After closing the pure-priority chain, the next apparent step was to implement physical
Profile terminal guards and RPDB dispatch independently.

That split is unsafe for a structural policy change.

## Finding — RPDB activation is coupled to filtering/NAT readiness

A newly installed RPDB rule makes its Profile table reachable immediately.

If routing is activated before the new Profile-direction guard / Device envelope / NAT
postconditions are ready, traffic can traverse a mixed policy that was not permitted by the
old or new complete policy.

Therefore a physical RPDB switch is not an independent route-only transaction.

## Requirement gate

This follows directly from:

- `VPNG0004-R4.R3.R2` — structural changes may restrict forwarding but must not open a
  state forbidden by old/new policy;
- `VPNG0004-R4.R2` — unconfirmed critical lower state is not treated as active;
- `VPNG0004-R4.R5` — partial mutation requires fresh authoritative recovery;
- `VPNG0004-R4.R1.R1` — zero-path Profile destinations remain fail-closed rather than
  falling through ambient routing.

No new requirement is needed.

## Decision

Separate **desired-state construction** from **physical activation**.

The next executable unit may purely build the complete structural routing projection:

- terminal blackhole default for every enabled Profile table;
- ordinary path routes for every current destination/path realization;
- host-boundary destination dispatch rules;
- zero-path table/guard/dispatch state with no ordinary paths.

It must not apply RPDB rules.

## Structural transaction ordering

Physical structural execution will be accepted only behind this boundary:

```text
observe
 -> verify restrictive barrier
 -> prepare guarded routing tables
 -> prepare nft filtering/NAT
 -> switch/verify RPDB dispatch
 -> verify complete routing+nft desired state
 -> release barrier
 -> final verify
 -> cleanup stale state
```

A prepared route table is allowed to exist before activation only while no new dispatch rule
makes it reachable.

## Rejected alternative

### Implement route/RPDB now and add nft later

Rejected. It would make the development order observable as an unsafe intermediate system
design.

The pure desired projection can be built/tested now without creating that coupling.

## Next implementation unit

Add immutable lower desired routing types and a pure builder from:

- `PayloadProfileRequest`;
- current `NetworkPolicyLayout`;
- verified current `RoutePriorityPathRoute` realizations;
- current managed host-boundary `InterfaceIdentity`.

The output must be complete enough that a later structural Executor can compare authoritative
actual routes/rules against one desired value before mutation.

## Verdict

**PASS — route/RPDB physical activation remains gated on the shared structural barrier; pure
desired-state projection may proceed.**
