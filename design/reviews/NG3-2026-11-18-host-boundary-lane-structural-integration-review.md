# NG3 structural integration review — host-boundary behavior-lane routes

## Decision

Conditional on adopting EXP-064 after resolving VPNG-U004-R4.R6.R1.R6.R1, host-boundary behavior lanes require one new route role inside existing Profile payload tables, but they must not be represented as synthetic VPN LogicalPathId routes.

The current structural routing model has only two effective route roles: terminal guard (blackhole) and VPN logical-path unicast route. ManagedRouteSpec currently encodes that assumption by requiring every unicast route to carry a LogicalPathId. structural_routing_inventory.py likewise treats every reserved unicast route using path_route_protocol as a VPN path route.

A behavior-lane default is neither of those.

## Required structural extension

The next implementation block must add a third explicit route role: GUARD / VPN_PATH / HOST_BOUNDARY_LANE, or an equivalent typed representation. The important invariant is role identity, not the enum spelling.

### HOST_BOUNDARY_LANE route semantics

A lane route has: owner Profile/table; destination 0.0.0.0/0; current verified inner behavior-lane endpoint; lane host-side gateway; VPN-GATE-owned protocol/metric identity; no LogicalPathId; and no availability/preference membership semantics.

It is materialized only for an inbound/bidirectional Profile that has a current eligible VPN path in the accepted Release-1 topology and a current verified endpoint for its normalized HostBoundaryBehaviorLane. Zero-path Profiles keep only the terminal guard and do not get a live lane default.

## Route ordering inside a Profile table

Remote Profile destinations keep VPN path routes. The ordinary-side fallback is the HOST_BOUNDARY_LANE default. The terminal guard remains the final default with terminal metric. The lane default must outrank the terminal guard while never replacing more-specific remote destination routes.

## Ingress table selection

The existing stack return-affinity classifier already establishes the Profile association and stores its connection mark. For Profiles with an active behavior-lane route, the same classification stage may additionally copy that Profile mark to the current packet inside the managed namespace. The existing higher-precedence affinity RPDB rule then selects the Profile table.

This stack-local packet mark is not a boundary carrier: it is consumed only for routing inside the managed stack; no host rule may depend on it; EXP-063 proves that cross-netns packet-mark continuity must not be assumed.

## Structural-owner consequences

The following modules require coordinated extension in one guarded block: payload_routing_desired.py, structural_routing_inventory.py, payload_routing_compare.py, linux_structural_routing.py, structural plan/transaction tests, and stack_return_affinity.py/Linux rendering.

The extension must remain inside the existing ForwardingGate=DISABLED structural transaction. There must be no interval where ingress marking can select a Profile table whose behavior-lane default has not yet been confirmed.

## Activation ordering constraint

Safe ordering: managed behavior-lane infrastructure verified -> host behavior owner verified restrictive/ready -> ForwardingGate disabled -> Profile lane routes plus managed policy converge -> inbound Profile table selection becomes active only with exact route generation -> full structural postcondition -> ForwardingGate may enable.

If current structural phase ordering cannot express the lane-route-before-ingress-selection dependency, the planner must be extended explicitly rather than relying on command ordering.

## What is already closed

This review does not reopen user-facing +snat semantics, +route-return semantics, the Release-1 inbound single-path constraint, stack established-flow Profile affinity, fixed four-class host behavior normalization, or managed-domain ownership of additional explicit boundary pairs.

## Requirement decision gate

Before this structural implementation may become production architecture, VPNG-U004-R4.R6.R1.R6.R1 must be reviewed explicitly. Its Purpose is satisfied by carrying the Profile-derived host behavior class, but its current Statement literally requires an unambiguous packet association with the selected Profile across the explicit host boundary. EXP-064 does not provide that literal identity on the host side.

## Remaining implementation gate

If the requirement is revised/clarified to permit behavior-equivalent continuity, production gateway NAT remains unready until the structural route role and the coupled inbound table-selection activation are implemented and evidenced together.