# VPN-GATE NG1 — Architecture Draft 2

Status: **Draft 2 — first production-capable domain/runtime model agreed; human-facing configuration syntax pending.**

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

### 2.4 Device transport publication

ROU may publish TCP/UDP transport endpoints for a Device.

Publication allows a stable internal VPN configuration to remain unchanged while the host-facing port is changed in ROU configuration.

Conceptual compact syntax:

    5678/udp>7890
    44443/tcp>44443
    44443/udp>44443
    4700:4900/udp>55200:55400

A mapping means:

    host-facing ROU transport port/protocol
        -> internal transport endpoint associated with the Device

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

## 6. Static domain model

ROU receives one normalized **ActiveConfig**. Human-facing file syntax and parsing are
outside the runtime model and are defined separately.

ActiveConfig contains two primary domain collections:

    ActiveConfig
    ├── Devices[]
    └── Profiles[]

A Device describes an external networking/VPN device that ROU may bind to itself. A
Profile describes a network-service requirement and the ordered Devices that may satisfy
it.

Device configuration and Profile configuration are deliberately separate. Device
configuration contains device/transport knowledge; Profile configuration contains network
policy. Runtime interface details never belong in Profile configuration.

A future reload path may introduce **CandidateConfig**. CandidateConfig becomes
ActiveConfig only after the new configuration has been safely materialized and verified.

## 7. Device model

Conceptually:

    Device:
        name
        enabled
        interface_match
        interface_quota
        publications[]
        traffic_envelope

name is the stable identifier referenced by Profiles.

enabled is an administrative state owned by the Device side. A disabled Device is not
bound, monitored, published or otherwise processed by ROU. An enabled Profile may refer to
a disabled Device; this is normal operational state, not a configuration warning or error.

A minimally valid disabled Device therefore needs only:

    name
    enabled = false

The remaining Device fields are not deeply validated while the Device is disabled.

An enabled Device is bound to ROU only when at least one enabled Profile references it.
An enabled Device referenced by no enabled Profile remains inert.

### 7.1 Interface discovery

interface_match is an internally typed selector:

    EXACT
    PREFIX

It identifies runtime interfaces belonging to the Device. Selector namespaces of active
Devices must not overlap: one concrete runtime interface must not ambiguously belong to
multiple Devices.

DeviceEngine discovers runtime interfaces mapping to enabled Devices required by at least
one enabled Profile.

Runtime interface identity is:

    (ifname, ifindex)

Same-name/new-ifindex is a fresh runtime interface.

Tunnel-local IP addresses, peer addresses and transport internals are Device concerns.
Traffic routing uses direct-device routes and does not require tunnel peer IPs.

### 7.2 Interface quota

interface_quota is the maximum number of simultaneously observed matching interfaces that
ROU is prepared to bind for the Device. It is a ROU quota, not a statement about the
physical or protocol maximum supported by the Device.

DeviceEngine observes all matching interfaces for diagnosis but exports no more than
interface_quota as bound interfaces. Existing bound survivors are not displaced by newly
observed over-quota interfaces.

The sum of Device interface_quota values used by each enabled Profile must fit that
Profile's normal metric space. A static metric-space overflow is a configuration error.

### 7.3 Device availability

A bound interface may carry normalized availability information independent of kernel
link presence:

    UNKNOWN
    AVAILABLE
    UNAVAILABLE

This exists specifically for cases such as WireGuard, where an interface may remain
present and administratively healthy while the remote side is unreachable.

How remote availability is determined is a future feature and may be Device-specific.
Publication state, transport-specific observations and other raw evidence remain internal
to DeviceEngine; downstream components receive only normalized availability.

Availability does not break the bound-interface lifetime.

### 7.4 Device traffic envelope

Device configuration may constrain traffic that is permitted through the tunnel itself,
including remote endpoints/networks and protocol/service restrictions.

This is a Device-side hard envelope, not BOU policy. BOU cannot enforce policy on traffic
after VPN decapsulation inside the ROU namespace.

A Profile may use only traffic semantics compatible with the Device envelope. Exact
human-facing syntax is deferred to the configuration design.

## 8. Device transport publication

A Device may publish zero or more TCP/UDP transport endpoints.

Conceptually a publication maps:

    host-side ROU port/protocol
        -> internal Device transport listener inside the ROU namespace

Publication belongs to Device binding, not to Profile routing. It is a ROU-owned host-side
socket/relay resource. What the host or BOU permits, blocks or further publishes outside
that socket is outside ROU responsibility.

For UDP, publication must preserve independent per-peer return-path associations. TCP
publication is connection-oriented relay.

A Device not required by any enabled Profile has no publication sockets.

## 9. Profile model

Conceptually:

    Profile:
        enabled
        direction
        destinations[]
        device_order[]

Profile describes a network-service requirement. It contains no runtime interface names,
ifindex values, tunnel addresses, peer addresses, metrics or Device discovery rules.

enabled and direction are separate properties with separate meanings.

direction values are:

- OUTBOUND — new flows may start from host0 toward VPN; return traffic is allowed.
- INBOUND — new flows may start from VPN toward host0; return traffic is allowed.
- BIDIRECTIONAL — new flows may start in either direction.

Disabled Profiles are not deeply validated or materialized. They may be retained as
incomplete future configuration.

## 10. Destinations and profile dispatch

destinations[] is the non-empty set of IPv4 destination prefixes served by the Profile.

The term destination is intentionally distinct from kernel route: a destination expresses
network policy; routes are runtime materialization.

For enabled Profiles:

- only IPv4 CIDR is accepted;
- host bits are forbidden rather than silently canonicalized;
- 0.0.0.0/0 and /32 are both valid;
- duplicate destinations are forbidden globally across all enabled Profiles, including
  duplicates within one Profile;
- overlap between different prefix lengths is allowed.

ROU builds global dispatch entries from all:

    (destination, Profile)

and serializes them deterministically by:

    prefix length descending
    network address ascending

Thus /32 entries naturally precede /0 without making Profile file order semantically
significant.

Each enabled Profile owns one routing table. Every active Profile table contains a
terminal fail-closed:

    blackhole default

Per-destination blackholes are no longer part of the production model; terminal blackhole
default is sufficient to prevent fall-through from a dispatched Profile table.

## 11. Profile Device order and metric allocation

device_order[] is an ordered list of Device identifiers and contains no additional
Profile-local Device parameters.

A Device may be shared by any number of enabled Profiles. Its use is explicit in each
Profile through device_order[].

All bound interfaces of an earlier Device are preferred to all bound interfaces of a
later Device within that Profile.

Metric allocation is internal to ROU:

    FIRST_NORMAL_METRIC = 1
    METRIC_STEP = 1

For each enabled Profile, every Device receives a Profile-local metric range whose width is
Device.interface_quota. Ranges are allocated in device_order order.

Because every Profile has its own routing table, metric namespaces are independent between
Profiles. The same bound interface may therefore have different metrics in different
Profiles.

Metric assignment belongs to:

    (Profile, ifname, ifindex)

not to Device or interface globally.

The assignment is stable for the whole continuous period in which the same runtime
interface remains bound and the Profile continues to use that Device. Availability changes
do not change its normal slot. A removed assignment is not reusable until the removal has
been verified and committed.

## 12. Unavailable-path fallback

Availability is planner input.

Any AVAILABLE path uses its stable normal metric. A path declared UNAVAILABLE must be
demoted below every normal path regardless of Device order.

The agreed model reserves one common:

    UNAVAILABLE_METRIC

for the fallback tier. Multiple unavailable paths for one destination are expected to be
materialized as one equal-cost direct-device multipath route at that metric.

The architectural semantics are accepted, but the exact Linux FIB mechanism remains
**pending live verification**. A dedicated real-life experiment must verify direct-dev
multipath across actual VPN interfaces, interface disappearance/return and relevant
conntrack/NAT behavior before this implementation becomes normative.

UNKNOWN availability does not itself terminate a bound-interface lifetime. Exact policy
for future availability detectors is intentionally deferred.

## 13. DeviceEngine

**DeviceEngine** owns the ROU-side mechanisms that make existing Devices usable:

- determine which enabled Devices are required by enabled Profiles;
- bind/unbind those Devices to ROU;
- discover and monitor their runtime interfaces;
- enforce interface_quota;
- maintain DeviceBindingState;
- maintain publication sockets/relay;
- normalize Device-specific evidence into bound-interface availability;
- publish an immutable DeviceBindingSnapshot to downstream logic.

DeviceEngine does not manage the Device itself. In particular the first production model
does not require it to start, stop, restart, configure or repair a VPN transport.

DeviceEngine may update its binding state because of ordinary system/environment changes
or, in the future, changes caused by DeviceManager. It does not depend on DeviceManager.

## 14. TrafficEngine

**TrafficEngine** consumes network policy and bound Device interfaces. It owns:

- Profile-local path construction;
- stable Profile/interface metric assignments;
- per-Profile routing tables;
- RPDB destination dispatch;
- payload firewall/NAT policy;
- fail-closed Profile routing.

TrafficEngine does not discover Device interfaces itself and does not consume raw
Device-specific transport/publication state.

ROU firewalling does not replace host-side BOU admission control. BOU governs who may use
the ROU external interface; TrafficEngine governs payload semantics after traffic has
entered ROU.

## 15. PlannerEngine and runtime state

**PlannerEngine** coordinates desired runtime state without collapsing ownership boundaries
between DeviceEngine and TrafficEngine.

The main runtime concepts are:

    ActiveConfig
    EnvironmentSnapshot
    DeviceBindingState
    DeviceBindingSnapshot
    TrafficRuntimeState
    DesiredState
    TransitionPlan

EnvironmentSnapshot is a fresh observation of relevant real state. It may include kernel,
process, socket, sysctl and other runtime facts; it is intentionally broader than a kernel
snapshot.

Events are wakeups only. Decisions are made from fresh observations.

DeviceBindingState is DeviceEngine's committed history needed to preserve survivor binding
and quota semantics. DeviceBindingSnapshot is the normalized immutable view exported from
DeviceEngine.

TrafficRuntimeState stores historical allocations that cannot be reconstructed safely from
one observation alone, principally stable:

    (Profile, ifname, ifindex) -> normal metric slot

PlannerEngine combines ActiveConfig, current normalized Device state, TrafficRuntimeState
and fresh environment observations to derive complete DesiredState and an ordered
TransitionPlan.

DesiredState describes what complete owned state must exist. TransitionPlan describes how
to reach it safely.

The commit rule is:

    observe
      -> plan
      -> apply
      -> fresh observe
      -> verify complete desired state
      -> commit

Apply success is not commit. Historical allocations are changed only after verification.

DeviceEngine has an analogous independent observe/apply/verify/commit boundary for the
state it owns.

## 16. Engine conventions and future DeviceManager

The first production-capable runtime has three named processing components:

    PlannerEngine
    DeviceEngine
    TrafficEngine

Detailed DEBUG logging is required for **all Engines**. Debug output should expose inputs,
relevant configuration projection, previous committed state, decision path, desired result,
transition/apply/verification results and commit outcome while never logging credentials,
private keys, passwords or other secrets.

Each Engine defines a short subject-area prefix for related runtime and diagnostic
artifacts:

    PlannerEngine -> planner-*
    DeviceEngine  -> device-*
    TrafficEngine -> traffic-*

The artifact need not be an implementation object owned by the Engine; the prefix denotes
the subject/ownership namespace.

### 16.1 Future DeviceManager

A future **DeviceManager** may change the actual state of Devices:

- start / stop / restart;
- health and recovery actions;
- generate Device configuration;
- reconfigure a Device.

DeviceManager is independent of DeviceEngine. PlannerEngine may request Device actions;
DeviceEngine then observes the resulting environment normally. A command to start or
reconfigure a Device never substitutes for observation that a usable interface actually
appeared.

### 16.2 Future warm reservation

Warm/hot reservation is a future Profile capability expressing how many preferred usable
paths a Profile wants to keep ready.

PlannerEngine must aggregate demand across all Profiles sharing Devices before asking a
future DeviceManager to create or remove Device capacity. One Profile ceasing to need a
path must not cause a Device/interface still required by another Profile to be removed.

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

## 22. NG1 production-model invariants

1. ROU owns its private network namespace and host-facing veth infrastructure.
2. ROU exposes one conventional host-facing L3 interface; payload and VPN transport share it using ordinary Linux routing semantics.
3. All VPN transport listeners/processes and tunnel interfaces live inside the ROU namespace.
4. BOU remains an independent host-side admission/routing concern; ROU and BOU require no safety-critical runtime RPC.
5. ActiveConfig contains Devices and Profiles; human-facing file syntax is outside the runtime model.
6. Device describes how ROU can use an external networking/VPN device; Profile describes network-service policy.
7. Device and Profile each have independent enabled state.
8. A disabled Device may be minimally described by name plus enabled=false and is not deeply validated.
9. An enabled Profile may reference a known disabled Device without error or warning.
10. An unknown Device reference is a configuration error.
11. An enabled Device is bound only if referenced by at least one enabled Profile.
12. DeviceEngine discovers interfaces only for enabled Devices required by enabled Profiles.
13. Concrete runtime interface identity is (ifname, ifindex); same-name/new-ifindex is a fresh interface.
14. Active Device selector namespaces do not overlap.
15. Device.interface_quota is the maximum number of matching interfaces ROU binds for that Device.
16. Over-quota interfaces remain observable for diagnosis but are not exported to TrafficEngine as bound interfaces.
17. Device publication belongs to Device binding and ROU, not to Profile routing or BOU.
18. Device-specific raw publication/transport evidence does not cross into TrafficEngine; DeviceEngine exports normalized interface availability.
19. Bound-interface availability supports UNKNOWN, AVAILABLE and UNAVAILABLE independently of interface presence.
20. Profile contains enabled, direction, destinations[] and device_order[]; runtime interface details are absent from Profile configuration.
21. destinations[] contains strict canonical IPv4 network prefixes; host-bit correction is never implicit.
22. Duplicate destinations are forbidden globally across enabled Profiles; overlap across different prefix lengths is allowed.
23. Destination dispatch is deterministically ordered by prefix length descending, then network address ascending.
24. Each enabled Profile owns one fail-closed routing table with terminal blackhole default.
25. Per-destination blackholes are not required by the production model.
26. device_order[] contains only Device identifiers and defines Profile-local Device preference.
27. A Device may be shared by multiple Profiles; its interfaces may receive different metrics in each Profile.
28. Metric allocation begins at 1 with step 1 and is internal to ROU.
29. Each Device receives a Profile-local metric range sized by Device.interface_quota.
30. For every enabled Profile, the sum of referenced Device interface quotas must fit the available normal metric space or configuration is rejected.
31. Metric assignment belongs to (Profile, ifname, ifindex) and remains stable for the continuous bound lifetime.
32. Availability changes do not change the normal metric slot.
33. Removed metric assignments are not reusable before verified commit of the removal.
34. Every AVAILABLE path outranks every UNAVAILABLE path.
35. UNAVAILABLE paths share one final fallback metric; direct-device multipath materialization is pending dedicated live verification.
36. DeviceEngine owns Device binding/discovery/quota/publication state; TrafficEngine owns Profile routing/firewall/NAT state.
37. PlannerEngine coordinates desired state and transitions without merging Engine ownership domains.
38. Runtime decisions are based on fresh EnvironmentSnapshot observations; events are wakeups only.
39. Apply success is not commit; fresh observation and complete verification precede committed-state changes.
40. Detailed DEBUG decision logging is required for all Engines and must never expose secrets.
41. Runtime/diagnostic artifacts use subject-area prefixes planner-*, device-* and traffic-*.
42. Future DeviceManager may change Device lifecycle/configuration but is independent of DeviceEngine.
43. Future warm reservation is Profile demand aggregated globally across shared Devices.
44. RC2/RC3 and ROU v0/EXP-012 remain evidence and implementation-history sources; superseded BindingSpec/capacity terminology is not normative for the production NG1 model.
