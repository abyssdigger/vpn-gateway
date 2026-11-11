# VPN-GATE NG1 — Architecture Draft 1

Status: **Draft 1 with executable ROU v0 ready for live gate (EXP-012)**.

Companion concept: `design/NG1/rou-concept.md`.

NG1 is a next-generation design, not an incremental RC3 revision. The base abstraction changes from a host-integrated VPN gateway to a self-contained virtual VPN router appliance.

## 1. Components

NG1 is built around two concepts:

- **ROU** — a self-contained virtual VPN router running inside its own Linux network namespace.
- **BOU** — a host-side firewall/routing policy layer around ROU.

ROU is the primary NG1 component.

BOU is deliberately replaceable: any firewall/router able to correctly handle the external ROU interface may fulfill the role. A native VPN-GATE BOU is planned later, optimized for **PEACEFUL** and **AGGRESSIVE** modes.

BOU evolved conceptually from the earlier RC2/RC3 boundary-controller / boundaryd idea. In NG1 the old boundary layer is no longer part of the router core; it becomes an independent host-side firewall/router concern.

## 2. ROU as a self-contained appliance

ROU is a virtual router embedded in a Linux host but isolated from the host network stack.

ROU owns:

- its network namespace;
- its host-facing veth pair;
- its external interface;
- its internal peer;
- loopback inside the namespace;
- namespace-local IPv4 sysctls;
- routing state and RPDB inside the namespace;
- firewall and NAT inside the namespace;
- VPN tunnel interfaces;
- profile state;
- lifecycle of ROU-managed VPN processes;
- host-side TCP/UDP publication sockets explicitly declared by ROU configuration;
- relay state connecting those published sockets to internal transport endpoints.

The host main namespace is not part of the internal ROU routing domain.

### 2.1 External interface

ROU exposes one conventional L3 interface to the host.

Default external interface name:

    rouvpn0

The name is configurable. Core logic must use the semantic role rather than a hard-coded name.

Conceptually:

                        MAIN NETWORK NAMESPACE
                                 |
                              rouvpn0
                                 |
                              === veth ===
                                 |
                               host0

                        ROU NETWORK NAMESPACE
                             |
                             +-- local VPN transport listeners/clients
                             +-- profile routing
                             +-- firewall / NAT
                             +-- wg0 / wg1 / vpns0 / ...

The same interface carries three classes of traffic using ordinary Linux IP semantics:

1. **Forwarded payload** entering through host0 and dispatched into profile routing.
2. **Inbound VPN transport** addressed to a local ROU endpoint and delivered by the local table to a VPN listener or ROU transport relay.
3. **Locally generated VPN transport** emitted by a VPN client/process inside ROU and routed through the namespace main table via host0.

No dedicated transport/underlay interface is required.

### 2.2 Payload path

Payload entering through rouvpn0/host0 with a non-local destination follows the forwarding path:

    host/LAN
        -> rouvpn0
        -> host0
        -> profile selection
        -> profile routing table
        -> admitted VPN binding

Return payload from a VPN binding is routed back through host0/rouvpn0 according to profile direction and routing policy.

ROU does not know which host-side sources are trusted, how the host selected ROU as a next hop, which host firewall rule admitted a packet, or which host routing-policy decision led to rouvpn0.

Host-side admission and steering belong to BOU or another external firewall/router.

### 2.3 VPN transport path

VPN transport shares rouvpn0/host0 but does not use profile payload routing.

Inbound transport addressed to a local ROU endpoint is delivered locally before profile dispatch.

Locally generated VPN transport uses the ROU namespace main table, typically with a default route via host0.

This deliberately mirrors conventional Linux VPN operation: one ordinary network interface may carry both routed payload and the outer VPN transport.

### 2.4 Binding transport publication

ROU may publish TCP/UDP transport endpoints for a BindingSpec.

Publication allows a stable internal VPN configuration to remain unchanged while the host-facing port is changed in ROU configuration.

Conceptual compact syntax:

    5678/udp>7890
    44443/tcp>44443
    44443/udp>44443
    4700:4900/udp>55200:55400

A mapping means:

    host-facing ROU transport port/protocol
        -> internal transport endpoint associated with the binding

For equal external/internal ports the right side may later be made optional as shorthand.

For ranges:

- bounds are inclusive;
- external and internal ranges must contain the same number of ports;
- mapping is positional.

For example:

    4700:4900/udp>55200:55400

maps 4700 to 55200, 4701 to 55201, and so on.

The publication mechanism is transport-level TCP/UDP relay functionality owned by ROU, not BOU. It is independent of the VPN protocol itself.

The published socket exists in the host main namespace because it must receive traffic addressed to the host. It is nevertheless an explicitly owned ROU resource and follows the ROU instance lifecycle. The VPN process and its internal listener remain inside the ROU namespace.

For UDP, the relay must preserve per-peer return-path association so that replies from an internal VPN listener are returned through the corresponding published host-side endpoint. For TCP, publication is connection-oriented relay.

This lets a support VPN be configured once on an internal port while the externally visible ROU publication changes independently.

Publication is not payload routing and does not make the host main namespace part of the ROU routing domain. It is a narrow transport facade owned by ROU.


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
4. configures link addressing;
5. prepares configured transport publications and their host-side sockets;
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
- rouvpn0/host0 interface pair;
- published transport endpoints;
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

    default -> host0

Locally created VPN transport traffic uses this path and exits through rouvpn0 into the host network stack.

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
        publish[]         # optional TCP/UDP transport publication
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

VPN underlay traffic exits through host0/rouvpn0 as ordinary locally generated ROU traffic. Any further host-side routing or NAT is an external host/BOU concern and does not belong to profile payload NAT.

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

BOU is the optional host-side firewall/router layer around the ordinary external ROU interface.

The name and concept evolved from the earlier boundaryd / boundary-controller design.

In NG1, BOU is no longer responsible for constructing ROU. ROU is self-contained and creates its own namespace, veth pairs and supervised runtime.

BOU sees rouvpn0 as an ordinary L3 interface and applies host policy around it.

BOU may provide source/admission filtering, host-side steering, anti-leak routing policy, containment, and ordinary host-side routing/NAT for ROU-originated transport traffic.

Publication of a binding's TCP/UDP transport endpoint belongs to ROU itself. BOU may still restrict access to that published host-side port like any other firewall.

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

Their runtime interface is ordinary kernel networking state represented by rouvpn0 and the host-side sockets/endpoints ROU explicitly publishes.

ROU controls its own namespace plus only the explicitly owned host-side resources required to instantiate the appliance: rouvpn0 and configured publication sockets/relay state. It does not own general host routing or firewall policy.

BOU observes and controls host-side policy around rouvpn0, published endpoints, and the host network environment.

Future Unix sockets may expose read-only status, diagnostics and event history for administrators, but they are not part of the safety-critical control plane.

## 19. Transport publication evidence

Transport publication has passed two implementation prerequisites: EXP-010 and EXP-011.

The experiment intentionally does not require WireGuard. It must prove the generic chain:

    host input
        -> ROU published UDP socket
        -> ROU relay
        -> listener inside a separate ROU network namespace
        -> output derived from received input
        -> host-visible sink

A second observable response may return through the relay to the original client.

The experiment separates two questions:

1. whether the relay/listener signaling logic works at all;
2. whether the same logic crosses a real Linux network-namespace boundary through rouvpn0/host0.

Only the second proves the NG1 namespace topology. A sandbox lacking network-namespace privileges may validate the first without claiming the experiment complete.

EXP-010 completed that namespace proof with a generic UDP listener.

EXP-011 then replaced the dummy listener with a real ocserv/OpenConnect endpoint while
preserving the existing external endpoint `44443/tcp+udp`. The host-side publication
relay forwarded both TCP/TLS/CSTP and UDP/DTLS to ocserv inside the private ROU namespace.
The client explicitly reported both CSTP and DTLS connected, and the ocserv-created
`vpnsXX` interfaces existed only inside the ROU namespace.

Therefore same-port real-protocol transport publication is an established NG1 primitive,
not an open prerequisite. Arbitrary external/internal port translation for protocols that
advertise transport endpoints remains protocol-specific and is not implied by EXP-011.

The EXP-011 proof relay intentionally supported only one UDP peer association. This is
sufficient for the topology/protocol proof but not for production: a general ROU UDP relay
must maintain independent per-peer association state.

## 20. First executable ROU prototype boundary

The first executable ROU implementation is intentionally narrower than the full NG1
configuration model. It is a lifecycle and integrity prototype, not the first generic
configuration release.

ROU v0 may hard-code:

- one ROU instance and namespace;
- one host-facing veth pair;
- one OUTBOUND profile;
- one OpenConnect/ocserv prefix binding;
- the binding network and capacity;
- one protected test destination;
- one profile routing table and RPDB rule;
- one TCP and one UDP publication on the same external/internal ocserv port;
- the existing known-good ocserv configuration as the source for a derived runtime config.

The purpose is to prove the complete appliance control loop before adding a broad parser.

ROU v0 must distinguish two classes of change:

1. **normal binding lifecycle** — eligible `vpnsXX` interfaces may appear, disappear and
   reappear as clients connect and disconnect;
2. **structural owned-state drift** — unexpected mutation of ROU-owned profile routing,
   RPDB, firewall/NAT or appliance infrastructure.

For the first implementation, any change requiring structural reprojection uses a
protective forwarding barrier:

    set net.ipv4.ip_forward=0
        -> project complete owned state
        -> verify complete owned state
        -> set net.ipv4.ip_forward=1

This deliberately trades transient availability for a small and strong safety model while
the control loop is being validated.

A disappearing VPN binding is not itself corruption. Reconciliation recalculates admitted
bindings and fail-closed profile state from a fresh namespace snapshot. If no usable
binding remains, the profile table retains its blackholes and forwarding to that profile
remains fail-closed.

Initial live gates for ROU v0 are:

- clean creation from no namespace/veth;
- real ocserv startup and client reconnection through publication;
- correct materialization of the VPN interface inside the namespace;
- normal preferred-binding disappearance and survivor behavior;
- zero-binding fail-closed behavior;
- recovery after injected owned route/RPDB/firewall drift;
- detection of structural appliance drift that cannot be safely repaired in place;
- graceful shutdown and complete removal of owned host/netns resources.

General configuration parsing, multiple profiles, arbitrary selectors/transports, warm
capacity and BOU integration are explicitly deferred until these lifecycle gates pass.

### 20.1 Implemented ROU v0

The executable reference implementation is:

    design/NG1/code/python/rou_v0/

It is a clean NG1 implementation rather than an adaptation of the RC3 daemon. RC2/RC3
were used as evidence for already-proven kernel behavior and failure modes.

The implementation currently hard-codes the v0 lab boundary defined above and includes:

- namespace/veth creation and destruction;
- derived ocserv runtime configuration and process lifecycle inside the ROU namespace;
- host-side TCP publication relay;
- host-side UDP publication with independent per-external-peer associations;
- fresh-snapshot discovery of concrete `vpns+` interfaces by `(ifname, ifindex)`;
- capacity-2 metric allocation with survivor stability and delayed metric reuse across a
  verified REMOVE commit;
- a dedicated profile routing table with direct-dev unicast routes, protected blackhole and
  terminal blackhole default;
- an `iif host0` RPDB dispatch rule;
- OUTBOUND-only filter semantics and per-binding MASQUERADE;
- complete owned-state reconciliation under the forwarding barrier;
- semantic route/RPDB verification using `ip -j`;
- canonical filter/NAT verification using `iptables-legacy-save`;
- fatal isolation/cleanup on non-repairable appliance-infrastructure loss;
- read-only JSON status plus a single-instance runtime lock.

The EXP-011 one-peer UDP limitation is therefore not carried into v0: each external UDP
peer has its own connected internal UDP socket and return-path association.

### 20.2 Verification boundary

Rootless checks completed before the first live run:

- Python bytecode compilation;
- unit tests covering binding projection, capacity/overflow, delayed metric reuse,
  same-name/new-ifindex identity, fail-closed route/firewall projection and bootstrap
  handling of an absent profile table;
- two-peer UDP relay smoke;
- shell syntax validation of the live harness.

EXP-012 then completed the full live lifecycle/integrity gate on the dedicated Debian 13
test VM with `OVERALL=PASS`.

The successful live run proved:

- clean namespace/veth creation and teardown;
- real ocserv startup inside ROU;
- simultaneous DTLS for both real OpenConnect clients through independent UDP peer
  associations;
- two-path profile materialization and real payload forwarding;
- preferred-binding disappearance with survivor metric preservation and payload failover;
- fresh binding return without survivor churn;
- explicit zero-path fail-closed routing;
- route and firewall drift repair under an observable `ip_forward=0` barrier;
- fatal isolation/teardown after structural `host0` loss.

Three defects discovered during the live gate were corrected without weakening the
hypotheses: bootstrap flushing of a not-yet-created profile table, ocserv sec-mod
chroot-visible runtime socket placement, and an H8 harness command that initially targeted
the wrong routing table.

EXP-012 therefore closes the hard-coded ROU v0 verification boundary. Generic
configuration/domain-model work may proceed from this implementation while preserving the
verified lifecycle, fail-closed, allocation and integrity semantics.

## 21. Inheritance from RC2/RC3

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

## 22. Initial NG1 invariants

1. ROU owns its network namespace.
2. ROU creates and removes its own namespace/veth infrastructure.
3. ROU exposes one conventional host-facing L3 interface.
4. The default external interface name is rouvpn0 and is configurable.
5. Payload and VPN transport share rouvpn0 using ordinary Linux local/forwarded routing semantics.
6. No dedicated transport/underlay interface is required.
7. All VPN transport processes and tunnel interfaces live inside the ROU namespace.
8. Inbound VPN transport is delivered to local ROU endpoints before profile payload dispatch.
9. Locally generated VPN transport uses namespace main routing via host0.
10. Forwarded payload entering through host0 is selected into profile routing tables.
11. ROU may publish binding-specific TCP/UDP transport endpoints through host-side relay sockets.
12. Published host-side sockets are explicit ROU-owned lifecycle resources even though they exist in the main namespace.
13. VPN listeners/processes themselves remain inside the ROU namespace.
14. Binding transport publication belongs to ROU, not BOU.
15. Every enabled profile owns a dedicated routing table.
16. Profile tables are fail-closed routing domains.
17. Every protected destination retains an explicit blackhole.
18. Every profile table has a terminal fail-closed route.
19. Profile direction is per-profile policy.
20. Binding priority follows bindings[] order independently of selector type.
21. Deterministic prefix bindings reserve capacity-sized metric pools.
22. capacity=-1 prefix bindings share a tail pool without guaranteed mutual priority.
23. Capacity overflow isolates only excess concrete interfaces; it does not automatically invalidate the whole profile.
24. Managed binding lifecycle must not alter BindingSpec routing semantics.
25. ROU may later maintain configurable live/warm binding capacity.
26. BOU is outside ROU routing semantics and may be replaced by another firewall/router.
27. PEACEFUL protects the remote VPN side from unauthorized transit through ROU.
28. AGGRESSIVE additionally protects VPN-managed traffic from leaking around ROU.
29. ROU and BOU require no safety-critical runtime RPC.
30. RC2/RC3 are reusable evidence/design sources, but not normative NG1 topology.
31. Same-port TCP/TLS/CSTP and UDP/DTLS publication through a private ROU namespace is experimentally proven by EXP-011.
32. A production UDP publication relay must maintain independent per-peer association state.
33. ROU-owned structural state may be repaired under a forwarding barrier; forwarding is restored only after verification.
34. Normal VPN binding disappearance is a lifecycle event, not structural corruption.
35. With zero admitted bindings, profile routing remains explicitly fail-closed rather than falling through to namespace main routing.
