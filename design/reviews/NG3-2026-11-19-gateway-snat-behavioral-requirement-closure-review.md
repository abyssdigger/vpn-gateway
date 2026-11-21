# NG3 gateway-SNAT behavioral requirement closure review

**Date:** 2026-11-19  
**Cycle:** `ng3-design-cycle-20261119-alpha-release-blockers-35m`

## Scope

Revalidation of `VPNG0004-R4.R6.R1.R6.R1` after replacing the old
implementation-specific cross-boundary Profile-identity wording with the accepted observable
gateway-SNAT isolation behavior.

## Requirement ancestry

The revised child remains within `VPNG0004-R4.R6.R1.R6`:

- parent requires VPN-GATE-owned ordinary-side gateway NAT contributions to remain restricted
  to traffic for which that function is required;
- child requires the restriction to remain correct when multiple Profiles share the host
  boundary, including overlapping remote prefixes or different ingress VPN paths.

The child no longer requires an internal carrier or literal Profile identity to cross the
boundary. It requires only the observable result: `+snat` traffic may be translated and
non-`+snat` traffic must not be translated by that feature.

## Existing closure candidate

The existing four-class host-boundary behavior architecture already represents exactly the
host-side consequences selected inside managed policy:

```text
STATEFUL_NO_NAT
STATEFUL_NAT
ROUTE_NO_NAT
ROUTE_NAT
```

Multiple Profiles with the same required host-side behavior may share one class; Profiles
with different NAT applicability necessarily select different classes.

EXP-064 is PASS and proves the behavior-lane carrier across all four combinations, including
overlapping remote prefixes, forwarded gateway NAT, reverse NAT, route-return/stateful-return,
host-local no-NAT and unrelated-host isolation.

## Disposition

- EXP-064 disposition: `selected`;
- stale conditional architecture language tied to literal cross-boundary Profile identity:
  removed;
- `VPNG0004-R4.R6.R1.R6.R1`: re-closed.

No user-facing config or product capability changed. The review removes an accidental
implementation constraint from the requirement and adopts the already-proven mechanism that
satisfies the actual behavioral invariant.

## Remaining implementation gate

Closure of the requirement does **not** claim alpha `+snat` is materialized.

Still required:

1. authoritative structural representation of host-boundary lane default routes;
2. guarded composition of lane route and initial inbound Profile-table selection;
3. authoritative host behavior owner observation/convergence;
4. lifecycle of all required behavior lanes in alpha startup/reconcile/cleanup;
5. removal of the alpha `+snat` fail-fast only after the above are exact;
6. production-shaped end-to-end evidence.

## Requirement-state inventory

### decomp

Resolved historical links remain:

- `VPNG0005-R5 -> VPNG0005-R5.R6`;
- `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`;
- `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`;
- `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`.

### unreal

none

### broken

none

### rejected_closure

none

## Verdict

**ACCEPT.**

The prior product-semantic blocker is removed. Remaining `+snat` work is implementation and
evidence work under already-accepted semantics.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG0005-R5` -> `VPNG9101-R1.R1`
- `VPNG0005-R5.R6` -> `VPNG9101-R1.R1.R6`

The original IDs in the historical body are intentionally preserved.
