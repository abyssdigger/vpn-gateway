# VPN-GATE NG1 — Architecture Draft 1

Status: **first architecture draft**.

NG1 is a next-generation design, not an incremental RC3 revision. The base abstraction changes from a host-integrated VPN gateway to a self-contained virtual VPN router appliance.

## 1. Components

NG1 is built around two concepts:

- **ROU** — a self-contained virtual VPN router running inside its own Linux network namespace.
- **BOU** — a host-side firewall/routing policy layer around ROU.

ROU is the primary NG1 component.

BOU is deliberately replaceable: any firewall/router able to correctly handle the two external ROU interfaces may fulfill the role. A native VPN-GATE BOU is planned later, optimized for **PEACEFUL** and **AGGRESSIVE** modes.

BOU evolved conceptually from the earlier RC2/RC3 boundary-controller / boundaryd idea. In NG1 the old boundary layer is no longer part of the router core; it becomes an independent host-side firewall/router concern.

## 2. ROU as a self-contained appliance

ROU is a virtual router embedded in a Linux host but isolated from the host network stack.

ROU owns:

- its network namespace;
- both veth pairs;
- its external interfaces;
- their internal peers;
- loopback inside the namespace;
- namespace-local IPv4 sysctls;
- routing state and RPDB inside the namespace;
- firewall and NAT inside the namespace;
- VPN tunnel interfaces;
- profile state;
- lifecycle of ROU-managed VPN processes.

The host main namespace is not part of the internal ROU routing domain.

### 2.1 External interfaces

Default external interface names:

    rouvpn0    payload/data plane
    rouwan0    VPN transport/underlay plane

Both names are configurable. Core logic must use semantic roles rather than hard-coded names.

Conceptually:

                        MAIN NETWORK NAMESPACE

                  payload                  transport
                     |                         |
                  rouvpn0                  rouwan0
                     |                         |
                  === veth ================= veth ===
                     |                         |
                   host0                    uplink0

                        ROU NETWORK NAMESPACE
                             |
                             +-- profile routing
                             +-- firewall / NAT
                             +-- wg0 / wg1 / vpns0 / ...

### 2.2 Payload interface

**rouvpn0** is the default external payload interface.

All user routed traffic entering or leaving ROU uses this interface.

ROU does not know which host-side sources are trusted, how the host selected ROU as a next hop, which host firewall rule admitted a packet, or which host routing-policy decision led to the payload interface.

Host-side admission and steering belong to BOU or another external firewall/router.

### 2.3 Transport interface

**rouwan0** is the default external VPN underlay/transport interface.

It provides connectivity for the VPN transports themselves:

    WG client -> remote WG server
    OpenConnect client -> remote VPN server

    remote WG client -> local WG listener
    remote OC client -> local ocserv

Payload and VPN underlay are deliberately separated.

## 3. ROU lifecycle

ROU is a complete appliance with its own lifecycle.

Minimum administrative interface:

    rou up <instance>
    rou down <instance>
    rou show <instance>

### 3.1 rou up

rou up must be able to create a ROU instance from nothing.

At minimum it:

1. validates bootstrap and router configuration;
2. creates the network namespace;
3. creates rouvpn0 <-> host0;
4. creates rouwan0 <-> uplink0;
5. configures boundary addressing;
6. brings up loopback;
7. configures required namespace-local sysctls;
8. installs initial fail-closed internal state;
9. creates/starts the supervised ROU runtime;
10. observes VPN interfaces;
11. materializes profile routing/firewall state;
12. performs final verification.

Successful rou up means the appliance exists and its internal safety invariants are verified. It does not mean the host is already routing payload traffic to rouvpn0.

### 3.2 rou down

rou down safely removes the appliance:

1. close internal forwarding;
2. stop ROU-managed transport/router processes;
3. remove dynamic internal state;
4. stop the supervised runtime;
5. remove veth pairs;
6. remove the network namespace;
7. verify absence of owned runtime state.

ROU must not remove host-side BOU/firewall/routing state.

### 3.3 rou show

rou show is a read-only administrative view. It should eventually expose at least:

- lifecycle state;
- namespace identity;
- payload and transport interface pairs;
- configuration generation/hash;
- profiles and directions;
- profile routing tables;
- bindings, capacities and metrics;
- active/admitted/overflow concrete interfaces;
- VPN transport state;
- routing/firewall verification;
- underlay state;
- last reconciliation result.

A future read-only Unix socket may provide observability, but it is not part of the safety-critical control plane.

## 4. Bootstrap and runtime isolation

ROU should be isolated from the rest of Linux beyond the network namespace where practical.

The privileged bootstrap creates the appliance. The long-lived runtime should be heavily sandboxed.

Desired isolation layers include:

- network namespace;
- mount namespace;
- PID namespace where practical;
- IPC namespace;
- restricted UTS/hostname view;
- minimal /dev;
- dedicated cgroup/slice;
- reduced capability bounding set;
- systemd filesystem protections;
- syscall/address-family restrictions where compatible with configured VPN transports.

The sandbox must be configurable because WireGuard, OpenConnect, ocserv and future transports may require different capabilities, devices or syscalls.

Bootstrap configuration defines **how the appliance is isolated and launched**.

Router configuration defines **what the appliance routes and how profiles behave**.

The long-lived runtime should be supervised by systemd, for example rouvpn@<instance>.service, and log to journald.

## 5. Internal routing domains

ROU separates underlay routing from payload routing.

### 5.1 Namespace main table

The namespace main table is primarily the VPN transport/underlay routing domain.

Typical meaning:

    default -> uplink0

Locally created VPN transport traffic uses this path.

Profile payload routing must not depend on the namespace main default.

### 5.2 Per-profile routing tables

Every enabled profile owns its own routing table.

A profile table contains:

- routes through admitted bindings;
- per-destination fail-closed blackholes;
- a terminal fail-closed route.

ROU owns the complete table. Foreign state inside a profile table is not part of the supported model.

## 6. Profile model

Conceptually:

    Profile:
        enabled
        routes[]
        bindings[]
        direction
        routing_table
        metric_step
        metric_capacity

A profile defines one logical VPN connectivity domain.

Future profile policy may additionally include protocol, port and service filtering.

## 7. Profile routes and default route

routes[] defines the destinations served by the profile.

A profile may serve ordinary prefixes such as 10.0.0.0/8 and 192.168.0.0/16, or 0.0.0.0/0.

In NG1, 0.0.0.0/0 is an ordinary destination inside a dedicated profile routing table and acts as the catch-all profile during profile selection.

More-specific profile selection must precede the catch-all.

## 8. Profile direction

Direction is a **per-profile** property.

Conceptual values:

- OUTBOUND — new flows may start from host0 toward VPN; return traffic is allowed.
- INBOUND — new flows may start from VPN toward host0; return traffic is allowed.
- BIDIRECTIONAL — new flows may start in either direction.
- DISABLED — no new connectivity in either direction.

Exact handling of established conntrack state during policy changes is deferred.

## 9. BindingSpec

Conceptually:

    BindingSpec:
        interface
        network
        capacity
        launch_command    # optional future feature

interface is either an exact interface name or a trailing-prefix selector.

network is the applicability trust boundary.

A concrete interface is eligible only if:

1. its name matches the selector;
2. it owns at least one local IPv4 address belonging to that BindingSpec network.

## 10. Binding priority and metric pools

The order of bindings[] defines profile priority independently of selector type.

For example:

    wg0
    vpns+ capacity=2
    wg1

means that wg0 outranks every admitted vpns+ interface, and every admitted vpns+ interface outranks wg1.

EXACT and PREFIX do not form separate priority classes.

Conceptual defaults remain:

    FIRST_UNICAST_METRIC = 10
    metric_step = 10
    BLACKHOLE_METRIC = 65536

An exact BindingSpec has implicit capacity 1.

A prefix BindingSpec with positive capacity receives a deterministic reserved metric pool in its declared position.

capacity means the maximum number of simultaneously admitted concrete interfaces for which ROU guarantees that BindingSpec's deterministic priority range. It is not a lifetime allocation limit.

If eligible interfaces exceed capacity, excess interfaces remain OVERFLOW/unadmitted rather than invalidating the whole profile.

A prefix BindingSpec with capacity=-1 does not receive a dedicated deterministic priority range. All such BindingSpecs share one dynamic tail pool and must appear after deterministic-capacity BindingSpecs. Stable priority among shared-tail bindings is intentionally not guaranteed.

Within a reserved prefix pool or shared tail:

- an admitted survivor keeps its metric;
- a new interface gets the next available slot;
- the cursor wraps inside its pool;
- holes need not be eagerly filled;
- same-name/new-ifindex is a fresh binding instance;
- overflow never evicts a survivor;
- a removed binding's metric remains reserved until verified removal commits.

## 11. Fail-closed profile routing

Each protected destination retains its own explicit blackhole route.

This explicitly represents zero-path state, distinguishes an unavailable managed route from an accidentally missing route, strengthens verification, and improves diagnostics.

Additionally, every profile table has a terminal fail-closed route, conceptually blackhole default.

A packet already dispatched into a profile routing table must never fall through into the namespace main table.

## 12. Profile selection and RPDB

Forwarded payload entering through host0 is dispatched to profile routing tables through the namespace RPDB.

ROU fully owns that RPDB; it does not need to coexist with unrelated host policy-routing state.

Destination-specific profile selection precedes a possible 0.0.0.0/0 catch-all profile.

Routing-table IDs and rule priorities are allocated deterministically at startup and remain stable for the lifetime of the instance.

Because the namespace is owned by ROU, compact low IDs/priorities can be used rather than reserving large host-global ranges.

The exact allocation scheme remains to be finalized experimentally.

## 13. Firewall and NAT inside ROU

ROU firewalling does not perform host-side admission control.

It enforces internal appliance semantics:

- profile direction;
- use of admitted bindings only;
- isolation of overflow/unadmitted interfaces;
- return traffic;
- profile isolation;
- fail-closed behavior when usable paths disappear.

Future per-profile policy may add protocol/port/service restrictions.

Payload NAT belongs to ROU where required by a VPN transport/profile.

VPN underlay NAT is a separate host-boundary concern and does not belong to profile payload NAT.

## 14. VPN transport ownership

All VPN transport processes should run inside the ROU namespace.

This includes WireGuard configuration/runtime, OpenConnect clients, ocserv and future VPN implementations.

NG1 deliberately avoids a special WireGuard ownership model where the UDP socket remains outside while the interface moves inside.

Preferred invariant:

> VPN transport process and the tunnel interfaces it creates belong to the ROU namespace.

## 15. Managed bindings — future direction

The initial ROU may only observe externally created VPN interfaces.

The architecture must nevertheless allow BindingSpec to gain an optional process-launch definition.

If launch_command is absent, ROU only observes the binding.

If present, ROU may own the lifecycle of the VPN transport that materializes the binding.

Process lifecycle and binding admission remain separate concepts: process started does not mean binding admitted. A created interface still must pass normal selector/network/capacity/verification rules.

### 15.1 Warm-capacity operation

Managed bindings make it possible to support cold standby, hot standby and arbitrary warm capacity.

For example, with five possible VPN paths a profile may request that the two highest-priority usable managed bindings remain alive.

If one live path disappears, ROU can start the next eligible managed binding, wait for its interface, verify it and admit it.

On failback ROU can restore the preferred path and then restore configured warm capacity, optionally stopping excess lower-priority transports.

The routing semantics do not change depending on whether a binding was created externally or launched by ROU.

## 16. Reference implementation strategy

The first ROU implementation is Python, but it should be treated as an executable reference specification for a future production core in a systems language.

Priorities:

- strict typed domain model;
- pure projection/planning functions where practical;
- deterministic behavior;
- minimal hidden mutable state;
- explicit observe / desired / plan / apply / verify / commit stages;
- fake kernel backend;
- rootless planner tests;
- extensive regression tests;
- golden tests for desired kernel state.

The later production implementation should reproduce the same semantics against the same behavioral tests.

## 17. BOU concept

BOU is the host-side firewall/router layer around the two ordinary external ROU interfaces.

The name and concept evolved from the earlier boundaryd / boundary-controller design.

In NG1, BOU is no longer responsible for constructing ROU. ROU is self-contained and creates its own namespace, veth pairs and supervised runtime.

BOU only sees two host interfaces and applies host policy around them.

For the payload interface BOU may provide source/admission filtering, host-side steering, anti-leak routing policy and containment.

For the transport interface BOU may provide underlay egress, publication of inbound VPN listeners, host-side NAT where necessary and transport firewalling.

### 17.1 PEACEFUL mode

PEACEFUL is aimed primarily at workstation/laptop-style deployment.

Its primary security contract is:

> unauthorized host/network sources must not be able to use ROU as transit into the remote VPN side.

PEACEFUL does not promise to own or dominate the host's general outbound routing.

### 17.2 AGGRESSIVE mode

AGGRESSIVE is aimed primarily at dedicated gateway/server/appliance deployment.

It includes PEACEFUL ingress protection and adds an anti-leak contract:

> traffic configured as VPN-managed must either traverse ROU or be blocked.

BOU should prefer dominance over destruction: harmless lower-priority foreign state may remain. If foreign state can win, BOU should first try to install stronger owned routing/firewall state. Reclaim/deletion is a stronger fallback, not the default objective.

A native VPN-GATE BOU is planned, but its implementation language is intentionally unconstrained.

## 18. Independence of ROU and BOU

ROU and BOU do not require runtime RPC to operate safely.

Their runtime interface is kernel networking state represented by the two external ROU interfaces.

ROU observes and controls only its own namespace.

BOU observes and controls host-side state around the two external interfaces.

Future Unix sockets may expose read-only status, diagnostics and event history for administrators, but they are not part of the safety-critical control plane.

## 19. Inheritance from RC2/RC3

NG1 changes topology and ownership, but it does **not** discard the engineering work already completed in RC2 and RC3.

RC2/RC3 contain substantial reusable material:

- live experiments against real Linux routing, iptables, WireGuard and OpenConnect behavior;
- fail-closed experiments and recovery observations;
- route/metric and blackhole behavior;
- interface disappearance/reappearance and ifindex identity lessons;
- reconciliation and fresh-snapshot design;
- ADD/REMOVE transition ordering;
- verification-before-commit rules;
- ownership and drift-repair lessons;
- IPv4/IPv6 prerequisite checks;
- configuration parsing/validation patterns;
- selector and binding-domain work;
- profile status and availability semantics;
- extensive Python reference code and regression tests;
- independent architecture/code reviews and the decisions made from them.

This material is a **design and experiment library**, not obsolete history.

NG1 work should explicitly mine RC2/RC3 before inventing or re-testing behavior that was already established.

At the same time RC3 is not normative for NG1. Any RC3 rule depending on the old host-integrated topology, shared host routing namespace, old firewall ownership or other superseded assumptions must be re-evaluated before reuse.

In short:

> NG1 reuses proven observations, invariants and implementation techniques from RC2/RC3 while deliberately replacing their top-level topology and ownership model.

Primary source material includes the existing experiment log under design/vpn-gateway-experiments.md, the RC2/RC3 architecture documents, reviews and the RC3 Python implementation.

## 20. Initial NG1 invariants

1. ROU owns its network namespace.
2. ROU creates and removes its own namespace/veth infrastructure.
3. ROU exposes two conceptually distinct external interfaces: payload and transport.
4. Default external names are rouvpn0 and rouwan0; both are configurable.
5. Payload and VPN underlay never share the same logical interface role.
6. All VPN transport processes and tunnel interfaces live inside the ROU namespace.
7. Namespace main routing serves underlay; payload routing is profile-based.
8. Every enabled profile owns a dedicated routing table.
9. Profile tables are fail-closed routing domains.
10. Every protected destination retains an explicit blackhole.
11. Every profile table has a terminal fail-closed route.
12. Profile direction is per-profile policy.
13. Binding priority follows bindings[] order independently of selector type.
14. Deterministic prefix bindings reserve capacity-sized metric pools.
15. capacity=-1 prefix bindings share a tail pool without guaranteed mutual priority.
16. Capacity overflow isolates only excess concrete interfaces; it does not automatically invalidate the whole profile.
17. Managed binding lifecycle must not alter BindingSpec routing semantics.
18. ROU may later maintain configurable live/warm binding capacity.
19. BOU is outside ROU routing semantics and may be replaced by another firewall/router.
20. PEACEFUL protects the remote VPN side from unauthorized transit through ROU.
21. AGGRESSIVE additionally protects VPN-managed traffic from leaking around ROU.
22. ROU and BOU require no safety-critical runtime RPC.
23. RC2/RC3 are reusable evidence/design sources, but not normative NG1 topology.
