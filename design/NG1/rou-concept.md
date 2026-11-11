# VPN-GATE NG1 — ROU concept

Status: **working concept; ROU v0 live-verified and first production-capable domain/runtime model agreed.**

This document captures the top-level NG1 model before implementation details are frozen in the architecture.

## 1. ROU is a virtual VPN router appliance

ROU is a self-contained virtual router embedded in a Linux host.

It owns a dedicated Linux network namespace containing:

- VPN tunnel interfaces;
- VPN client/server processes;
- profile routing tables and RPDB state;
- profile firewall/NAT state;
- the namespace side of its host-facing link.

ROU exposes one ordinary L3 interface to the host, default name:

    rouvpn0

Inside the ROU namespace its peer is conceptually:

    host0

The host sees ROU in the same way it would see an ordinary downstream router.

## 2. One host-facing interface

ROU does not need separate payload and VPN-underlay interfaces.

The same rouvpn0/host0 link carries three ordinary Linux traffic classes:

1. forwarded payload from the host/LAN toward bound Device interfaces;
2. locally generated VPN transport from ROU toward remote VPN peers;
3. transport traffic delivered to ROU-managed published TCP/UDP endpoints.

Linux local delivery, forwarding and routing already distinguish these paths.

Conceptually:

                        MAIN NETWORK NAMESPACE
                                 |
                              rouvpn0
                                 |
                              === veth ===
                                 |
                               host0
                                 |
                        ROU NETWORK NAMESPACE
                          /       |       \
                         /        |        \
               local transport  profiles   Device interfaces
                  endpoints      routing    wg0/vpns0/...

## 3. Payload path

Traffic that the host chooses to send through ROU is routed to rouvpn0.

Inside ROU:

    rouvpn0
        -> host0
        -> forwarded packet
        -> profile selection
        -> profile routing table
        -> selected bound Device interface

Return payload from a bound Device interface follows ROU routing back through host0/rouvpn0 and then ordinary host routing.

ROU does not decide which host/LAN sources are allowed to use it. That is a host-side policy concern.

## 4. VPN transport path

VPN transports remain entirely inside the ROU namespace.

For a VPN client, outer transport is locally generated traffic:

    VPN process
        -> ROU main routing table
        -> host0
        -> rouvpn0
        -> host routing/NAT
        -> remote VPN peer

This is the same model as a conventional Linux VPN host: the tunnel interface handles inner payload while the outer transport follows ordinary routing.

## 5. Transport publication

Server-side VPN transports need a stable way to receive connections from the host network without coupling their internal configuration to host-facing port choices.

ROU therefore provides **transport publication**.

A publication maps a host-side TCP/UDP endpoint owned by ROU to an internal transport endpoint inside the ROU namespace.

Conceptual mapping notation only (the TOML publication grammar is still open):

    5678/udp>7890
    44443/tcp>44443
    44443/udp>44443
    4700:4900/udp>55200:55400

Meaning:

    published host-side port/protocol
        -> internal ROU transport port

Range mapping is positional and requires equal cardinality.

Example:

    4700:4900/udp>55200:55400

means:

    4700 -> 55200
    4701 -> 55201
    ...
    4900 -> 55400

A future human-facing syntax may choose a shorthand for equal external/internal ports; that syntax is intentionally not fixed here.

## 6. Publication is relay, not BOU DNAT

The host-side published socket belongs to the ROU lifecycle.

It is not a BOU rule and does not require BOU to rewrite the VPN configuration.

Conceptually for UDP:

    remote peer
        -> <host-address>:5678
        -> ROU published UDP socket :5678
        -> ROU relay
        -> host0 / namespace boundary
        -> internal UDP listener :7890
        -> VPN transport

For TCP the same abstraction is connection-oriented.

For UDP the relay must retain enough peer association to return internal replies to the correct external peer through the correct published endpoint.

The exact relay implementation, buffering, timeout and scaling policy are implementation details to be established experimentally.

## 7. Stable support-VPN configuration

The internal VPN configuration is deliberately stable.

For example WireGuard may be configured once to listen internally on UDP 7890.

Changing the host-facing publication from 5678 to 60000 changes only ROU configuration:

    5678/udp>7890

becomes:

    60000/udp>7890

The WireGuard configuration does not change.

The same principle applies to ocserv/OpenConnect and future TCP/UDP based transports.

ROU understands TCP/UDP publication, not the application protocol carried inside it.

## 8. Devices, Profiles and binding to ROU

The production model separates Device description from network policy.

A **Device** describes an external networking/VPN device: an ordered set of expected
runtime-interface selectors with per-selector quotas, transport publication, and
Device-side traffic constraints.

A **Profile** describes a network need:

    Profile:
        enabled
        direction
        destinations[]
        device_order[]

A Device may be shared by multiple Profiles. Profile configuration contains no runtime
interface names, tunnel addresses or metrics.

A Device is bound to ROU only when it is enabled and referenced by at least one enabled
Profile. DeviceEngine discovers only the configured `expected_interfaces` of such Devices
and maintains the resulting Device-to-ROU bindings. `expected_interfaces` is ordered; each
entry is EXACT with quota 1 or PREFIX with an explicit positive quota. TrafficEngine
consumes only normalized bound-interface state and materializes Profile routing.

Publication belongs to Device binding, not to Profile routing.

## 9. BOU

BOU is optional host-side integration.

Its purpose is to provide a ready-made firewall/routing policy matching the ROU configuration:

- source/admission filtering;
- host-side steering to rouvpn0;
- anti-leak containment;
- host-side routing/NAT for ROU-originated transport;
- firewall policy around published transport sockets.

BOU does not create ROU, does not own ROU transport publication, and does not need to understand VPN protocols.

An administrator may replace BOU with ordinary iptables/nftables/UFW/firewalld/routing configuration.

## 10. Lifecycle boundary

ROU owns:

- its network namespace;
- rouvpn0/host0;
- internal routing/firewall/NAT;
- Device binding/discovery state;
- published TCP/UDP sockets and relay state.

VPN transport processes and tunnel interfaces reside inside the ROU namespace. In the
first production model their lifecycle may still be managed externally. A future
DeviceManager may start, stop, health-check and reconfigure Devices without changing the
DeviceEngine/TrafficEngine ownership boundary.

ROU does not own:

- general host routing;
- host firewall policy;
- source admission policy outside the appliance;
- arbitrary host NAT;
- unrelated host interfaces.

This keeps ROU self-contained without turning it into the host firewall.

## 11. Implementation status

Transport publication is proven by EXP-010 and EXP-011.

ROU v0 under:

    design/NG1/code/python/rou_v0/

then completed EXP-012 with `OVERALL=PASS`, proving the hard-coded lifecycle/integrity
boundary against real ocserv/OpenConnect clients.

The next-generation production model is now defined around:

- Device / Profile separation;
- DeviceEngine / TrafficEngine / PlannerEngine;
- ActiveConfig and fresh EnvironmentSnapshot observation;
- DeviceBindingState and TrafficRuntimeState with independent commit boundaries;
- strict destinations and ordered Profile device references;
- ordered Device expected-interface selectors, per-selector quotas and Profile-local stable metric assignments;
- normalized availability where UNKNOWN/AVAILABLE stay in the normal tier and positive UNAVAILABLE moves to a lower fallback tier;
- metric ordering normal < UNAVAILABLE_METRIC < BLACKHOLE_METRIC, including /0 Profiles.

The initial human-facing TOML configuration contract is recorded in
`design/NG1/rou-config.md`. Direct-device multipath for the common unavailable fallback
metric remains a dedicated live-test requirement.
