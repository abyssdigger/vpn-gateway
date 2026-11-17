# NG3 — host-boundary return-routing gate

**Date:** 2026-11-18  
**Cycle:** `ng3-beta-cycle-20261118-host-return-routing-35m`

## Scope

Determine how the ordinary host returns traffic into the managed network domain after a packet
has previously crossed the explicit managed/host boundary.

This gate is intentionally prior to further Profile `+snat` work. Host-side reverse NAT and
plain routed inbound both eventually produce a packet whose destination is the original remote
IPv4 address; the host then needs a deterministic way to send that packet back across the
managed boundary.

## Historical NG3 audit

The need is compatible with the original isolation contract but its lower realization was not
closed.

Already accepted:

- `VPNG0004-R4.R6.R1` puts product-owned routing/policy/data-plane state in an isolated
  managed network domain and requires explicit host/domain boundaries.
- `VPNG0004-R4.R6.R1.R1` forbids arbitrary host routes/rules/firewall state from becoming a
  hidden part of the internal model; host-side mutable state is allowed only when it is an
  explicitly declared boundary area.
- architecture section 1.1 realizes the host/domain boundary as a dedicated veth-style link and
  treats the ordinary host namespace as outside the managed domain.
- the current managed-domain lifecycle owns the boundary veth pair and its two addresses plus
  the namespace default route toward the host. It explicitly does **not** own host payload
  routes/RPDB or host firewall/NAT.
- the ordinary-side gateway-NAT closure review explicitly rejected a generic host-wide route
  editor, but its return-path text assumes that reverse NAT is followed by routing back toward
  the managed boundary without defining who owns that routing state.
- EXP-053 manually installed a host route for the tested remote prefix toward the managed
  boundary. Therefore the experiment already depended on host return routing even though no
  production owner/contract existed.

No earlier NG3 review found in this audit defines a complete owned host-side return-routing
capability.

## Typical VPN comparison

Typical L3 VPN implementations do materialize routing state for remote protected prefixes.

- WireGuard/`wg-quick` uses ordinary routes for specific `AllowedIPs`. For a full-tunnel
  `0.0.0.0/0`, its documented Linux approach uses a separate routing table, policy rules and
  an fwmark exclusion for the WireGuard transport instead of blindly replacing the ambient
  default route.
- strongSwan commonly installs remote traffic-selector routes into a dedicated table (220 by
  default). Its route-based VPN documentation treats `0.0.0.0/0` as a special loop-avoidance
  case and documents mark-based exclusion or an explicit/throw route for the IKE/ESP peer.
- ocserv exposes server-side route add/delete hooks for client-advertised `iroute` networks;
  its client-facing `route = default` is likewise an explicit full-tunnel policy rather than
  an incidental main-table replacement.

References:

- https://www.wireguard.com/netns/
- https://docs.strongswan.org/docs/latest/howtos/introduction.html
- https://docs.strongswan.org/docs/latest/features/routeBasedVpn.html
- https://ocserv.gitlab.io/www/manual.html

## Problem statement

The naive realization is:

```text
for every enabled remote prefix:
    host route <remote-prefix> -> managed boundary
```

That is operationally familiar, but it leaks Profile topology into the ordinary host routing
state and makes `0.0.0.0/0` particularly dangerous: a host default route toward the managed
boundary can loop managed-originated underlay traffic back into the managed domain or capture
unrelated host traffic.

The boundary contract therefore needs to answer separately:

1. what information is allowed to escape the managed domain;
2. which host-side objects are owned by VPN-GATE;
3. which packets are eligible for return steering;
4. how `0.0.0.0/0` avoids recursion/capture;
5. how host-local replies and forwarded ordinary-LAN replies behave;
6. how absence/stale state fails closed without adopting ambient host routes.

## Candidate lower realizations

### A. Prefix publication

Publish remote prefixes into an explicitly owned host routing table/RPDB scope and route them
toward the managed boundary.

Advantages: conventional, stateless, easy to observe.

Risk: host-visible topology; `/0` and host-originated traffic require explicit exclusion or
policy semantics.

### B. Boundary-flow return steering

On the ordinary host, record that a connection entered from the managed boundary, then steer
the reverse direction back to that boundary using host-local conntrack metadata plus an owned
policy-routing table.

Advantages: remote prefixes need not be published into host routing state; `/0` does not
intrinsically mean replacing the host default route.

Risks requiring evidence: forwarded and host-local reply behavior, routing re-evaluation after
restoring a mark, non-TCP/UDP conntrack coverage, collision/ownership of marks and stale-state
cleanup.

This metadata is entirely host-local. It is not the rejected EXP-053 attempt to carry a packet
mark across network namespaces.

## Evidence gate

Before changing requirements or architecture, compare A and B with a disposable Linux
experiment covering:

- one routed inbound flow through the managed boundary and back;
- one host-side SNAT flow with reverse NAT and return to the managed boundary;
- host-local termination and reply;
- unrelated host traffic negative control;
- a remote prefix equivalent to `0.0.0.0/0` without routing the managed-originated underlay
  packet back into the boundary.

No production owner or mechanism is accepted by this document.
