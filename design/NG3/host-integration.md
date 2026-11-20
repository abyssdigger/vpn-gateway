# VPN-GATE NG3 — ordinary-host integration contract

**Applies to:** Release 1 manual host routing (`host_routing = "manual"`) and equivalent
administrator-managed integration.

**Normative requirements:**
- `VPNG0001-R2`
- `VPNG0001-R2.R1`
- `VPNG0001-R2.R1.R1`

This document describes what the ordinary host must provide to hand traffic to and receive
traffic from the managed VPN-GATE boundary. It does not transfer ownership of ordinary-host
routing, firewall or NAT to VPN-GATE.

## 1. Stable boundary facts

The managed network domain exposes one ordinary-side L3 endpoint on the host. In the current
Release-1 routed-veth realization this endpoint is addressless and the managed side answers
neighbor resolution through the selected Proxy-ARP boundary mechanism.

The administrator may choose any ordinary-host routing policy that produces the required
delivery. VPN-GATE does not require a particular host routing table, RPDB priority scheme or
route manager when `host_routing = "manual"`.

For the current alpha deployment the concrete facts are:

```text
host managed-boundary endpoint: vnga-host0
stack service address:          198.19.255.2/32
```

Packaging may later expose different concrete names/addresses, but it must publish the same
semantic facts needed below.

## 2. Remote Profile destinations

For ordinary-side traffic that should enter VPN-GATE, the host routing arrangement must
deliver the relevant remote destination prefixes to the managed host endpoint.

For a normal non-full-tunnel prefix the direct Linux form is:

```sh
ip -4 route add <remote-prefix> dev <managed-host-endpoint>
```

Example for the current alpha:

```sh
ip -4 route add 10.30.0.0/16 dev vnga-host0
```

The same reachability is required for replies to VPN-originated traffic when the remote source
address is preserved.

An administrator may instead implement equivalent policy routing. The route need not be in
`main`; the observable requirement is that traffic selected by the administrator reaches
the managed endpoint.

## 3. Profile SNAT identity reachability

When an inbound/bidirectional Profile uses `+snat`, ordinary-side peers see the configured
Profile SNAT identity as the remote source. Replies to that identity must be returned to the
managed boundary.

On the current addressless routed boundary, the proven Linux form is:

```sh
ip -4 route add <snat-identity>/32 \
    via <stack-service-address> dev <managed-host-endpoint> onlink
```

Current-alpha example:

```sh
ip -4 route add 198.19.255.10/32 \
    via 198.19.255.2 dev vnga-host0 onlink
```

EXP-075 provides the lower evidence for this gateway-backed /32 form.

## 4. Full-tunnel host routing

A Profile destination `0.0.0.0/0` means that traffic actually handed to VPN-GATE may be
classified as full-tunnel traffic. In manual mode the administrator still decides which
ordinary-host traffic is handed to the boundary.

A literal host default route through the managed endpoint is possible:

```sh
ip -4 route replace default dev <managed-host-endpoint>
```

but it is safe only when the administrator has separately preserved all host reachability
that must remain outside VPN-GATE, including VPN transport underlay endpoints, management
paths and required connected/static networks.

Administrators who need ordinary non-default routes to keep precedence may use their own RPDB
policy or use the Release-1 peaceful helper instead. VPN-GATE core does not impose one
manual-host full-tunnel policy.

## 5. Host-local traffic versus gateway traffic

A process running on the host can use routes through the managed endpoint without enabling
global host IPv4 forwarding. Such packets are locally generated/received host traffic.

If the ordinary host is also used as a router for another LAN/network, the administrator must
provide the ordinary host prerequisites for that role, including as applicable:

- `net.ipv4.ip_forward=1`;
- host FORWARD/INPUT/OUTPUT firewall permission;
- ordinary-side NAT chosen by the administrator;
- routes on adjacent ordinary networks back through this host.

VPN-GATE does not enable global host forwarding and does not own unrelated ordinary-host
firewall/NAT policy merely because `host_routing = "manual"` is used.

## 6. Ownership and failure boundary

With `host_routing = "manual"` VPN-GATE creates no peaceful-helper route/rule contribution.
Missing, conflicting or later-changed administrator routing is therefore a host integration
condition, not corruption of core managed forwarding state.

The managed-domain safety boundary remains independent: once traffic reaches the explicit
ordinary-side managed boundary, VPN-GATE applies its own Profile/path/firewall/NAT policy and
its own fail-closed semantics.

The administrator must diagnose ordinary-host routing separately from managed-domain policy.
Current status exposes the configured `host_routing` mode so the two cases are distinguishable.
