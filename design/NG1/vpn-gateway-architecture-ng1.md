# VPN-GATE NG1 — Architecture Draft 5

Status: **Draft 5 — production configuration surfaces resolved; explicit NAT, publication, traffic-envelope and instance/bootstrap contracts are normative.**

Companion documents:

- `design/NG1/rou-concept.md`
- `design/NG1/rou-config.md`
- `design/NG1/NG1-2026-11-11-config-brainstorm-brief.md`
- `design/NG1/NG1-2026-11-11-production-config-resolution.md`

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
        -> selected bound Device interface

Return payload from a bound Device interface is routed back through host0/rouvpn0 according to profile direction and routing policy.

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

Schema-version-1 publication mapping notation (also used by the human-facing TOML grammar):

    5678/udp>7890
    44443/tcp>44443
    44443/udp>44443
    4700:4900/udp>55200:55400

A mapping means:

    host-facing ROU transport port/protocol
        -> internal transport endpoint associated with the Device

For equal external/internal ports the right side is optional shorthand in schema version 1;
for example `44443/tcp` is equivalent to `44443/tcp>44443`.

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
4. configures link addressing and brings up loopback;
5. configures required namespace-local sysctls;
6. installs and verifies initial fail-closed internal state;
7. creates/starts the supervised ROU runtime and configured transport publications;
8. observes VPN interfaces;
9. materializes Profile routing/firewall/NAT state;
10. performs fresh complete verification;
11. only after successful verification permits payload forwarding.

Successful rou up means the appliance exists and its internal safety invariants are verified. It does not mean the host is already routing payload traffic to rouvpn0.

### 3.1.1 Device process startup

The first production model deliberately separates ROU appliance lifecycle from ordinary
Device process lifecycle.

The normative sequence is:

1. `rou up` creates the namespace/link, establishes fail-closed routing/filtering state,
   starts the supervised ROU runtime and verifies the appliance boundary;
2. VPN transports are started independently **inside the already existing ROU namespace**,
   by administrator-managed service units or a future DeviceManager;
3. DeviceEngine observes the resulting runtime interfaces through its normal fresh-snapshot
   path;
4. only verified bound interfaces become TrafficEngine inputs.

A missing VPN process or missing interface is not a ROU startup failure. The affected
Device simply has no usable binding and Profiles using it remain fail-closed.

An administrator may use an instance-specific service or an equivalent
`ip netns exec <rou-netns> ...` launch. Future DeviceManager automation does not change
the observation-before-use rule.

### 3.2 rou down

rou down safely removes the appliance:

1. close internal forwarding;
2. stop the supervised ROU runtime and any Device processes explicitly owned by an installed DeviceManager;
3. remove dynamic internal state;
4. remove veth pairs;
5. remove the network namespace;
6. verify absence of owned runtime state.

ROU must not remove host-side BOU/firewall/routing state.

Device process management is independent during normal operation, but the network
namespace is ROU-owned. Teardown must not leave residual Device processes keeping the
namespace alive indefinitely: successful `rou down` requires verified removal of the
owned namespace and its contained processes/resources after the normal graceful-stop
opportunity.

### 3.3 rou show

rou show is a read-only administrative view. It should eventually expose at least:

- lifecycle state;
- namespace identity;
- rouvpn0/host0 interface pair;
- published transport endpoints;
- configuration generation/hash;
- profiles and directions;
- profile routing tables;
- Devices, expected-interface selectors and their quotas;
- bound/over-quota concrete interfaces and normalized availability;
- Profile-local metric assignments;
- VPN transport state where observable;
- routing/firewall verification;
- underlay state;
- last reconciliation result.

A future read-only Unix socket may provide observability, but it is not part of the safety-critical control plane.

### 3.4 Publication supervision

Publication relay state is supervised ROU-owned state, not a detached helper.

A production implementation may use in-process workers or child processes, but every
configured publication must:

- start/reconcile with the active Device and ROU instance;
- make unexpected listener/relay loss observable;
- be restarted/recreated or reported unavailable rather than failing silently;
- stop before final appliance teardown.

The ROU supervisor owns this lifecycle even though the published socket itself lives in
the host namespace.

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

Router configuration defines **what remote prefixes the appliance serves, which Devices
may carry them and what Device-side traffic policy applies**.

The long-lived runtime should be supervised by systemd, for example
`rouvpn@<instance>.service`, and log to journald.

### 4.1 Link-addressing contract

The `rouvpn0 <-> host0` addressing belongs to bootstrap/instance configuration.

It is administrator-selected or explicitly generated at bootstrap time and is stable
across ordinary restarts of that ROU instance. Changing it is an explicit bootstrap
configuration change, never incidental runtime allocation.

ROU verifies the configured addresses before enabling payload forwarding. BOU/manual host
routing may refer to `rouvpn0` and/or its configured next hop. Device/Profile config does
not contain these infrastructure addresses.

### 4.2 Namespace forwarding prerequisites

The first production payload model is IPv4-only.

ROU owns and verifies at least these namespace prerequisites:

- `net.ipv4.ip_forward=0` while constructing or protectively repairing owned transit
  state;
- forwarding may become `1` only after complete desired transit state is verified;
- strict reverse-path filtering must not invalidate policy-routed/asymmetric VPN traffic:
  ROU-owned payload interfaces use an explicitly safe `rp_filter` policy (disabled by
  default for this model; a proven equivalent loose policy may be substituted later);
- `net.ipv4.fib_multipath_hash_policy` is ROU-owned and verified rather than inherited
  silently from the host/kernel default. The concrete production value is gated by the
  dedicated target-kernel ECMP prerequisite experiment; until then no availability
  detector may make the ECMP fallback tier operationally effective;
- a newly appearing Device interface is not admitted for payload forwarding until required
  per-interface sysctl state is verified;
- IPv6 is disabled on ROU-owned payload interfaces in the first production model,
  including `disable_ipv6=1` where supported/required; merely disabling IPv6 forwarding
  is not sufficient because link-local/local IPv6 traffic would otherwise exist outside
  the IPv4 Profile/firewall contract.

Failure to establish or verify required namespace sysctls is fail-closed.

## 5. Internal routing domains

ROU separates underlay/local-delivery routing from Profile payload routing.

### 5.1 Namespace main table

The namespace main table is primarily the VPN transport/underlay routing domain and the
ordinary Device-to-host forwarding path.

Typical meaning:

    default -> host0

It is used by:

- locally generated VPN transport traffic;
- payload entering from a bound Device and accepted toward the host side.

It must **not** become an accidental fallback for forwarded payload entering from
`host0`.

### 5.2 Per-Profile routing tables

Every enabled Profile owns its own routing table.

A Profile table contains:

- routes through bound Device interfaces selected for that Profile;
- availability fallback materialization where applicable;
- one terminal fail-closed `blackhole default` route.

ROU owns the complete table. Foreign state inside a Profile table is not part of the
supported model.

### 5.3 Host-side dispatch and RPDB catch-all

`destinations[]` denotes the Profile's **remote/VPN-side prefixes**.

Forwarded host-side payload is dispatched conceptually as:

    iif host0, to <remote-prefix> -> lookup <Profile table>

Rules are ordered by longest remote prefix first, then network address.

After all Profile dispatch rules, ROU owns a terminal host-ingress fail-closed action:

    iif host0 -> blackhole/unreachable

or a kernel-equivalent action with the same semantics.

Therefore a host packet intentionally or accidentally sent to `rouvpn0` without a
matching enabled Profile cannot fall through to the main `default -> host0` and loop
back to the host.

Local delivery to ROU itself remains governed by the higher-priority local table and is
not blocked by this forwarded-payload guard. This bypass is intentional: traffic from
`host0` addressed to a ROU-owned local address (for example a transport listener/relay
endpoint) must remain eligible for INPUT/local delivery and must not be captured by the
forwarded-payload terminal action. Locally generated VPN transport has no `iif host0` and
also continues to use the main table.

Packets entering from Device interfaces are not sent through the host0 destination
dispatch chain. Once admitted by ROU transit policy, they may use the main route toward
`host0`.

### 5.4 Two distinct firewall/policy layers

NG1 has **two different filtering concepts**. They must not be conflated.

#### A. Profile-direction guard — generated by ROU

`Profile.direction` defines which side may initiate a flow involving that Profile's
remote prefixes.

This is stateful ROU transit policy, not administrator-authored tunnel ACL.

Conntrack-equivalent semantics are normative:

- the ROU-owned FORWARD policy is `DROP`;
- `INVALID` is rejected first;
- `ESTABLISHED,RELATED` acceptance exists only for each currently bound interface `I`
  in the ordered pairs `I -> host0` and `host0 -> I`;
- no state-based ACCEPT exists for Device-to-Device transit, over-quota/unbound
  interfaces, or selector matches that are not verified bindings;
- `NEW` is accepted only from the side(s) allowed by the Profile direction;
- no generated ACCEPT exists merely because an interface or route exists.

The values mean:

- **OUTBOUND** — host side may initiate `NEW` toward the remote prefixes;
- **INBOUND** — remote side may initiate `NEW` through a bound Device toward the host
  side;
- **BIDIRECTIONAL** — either side may initiate `NEW`.

Materialization of NEW-flow policy is **explicit**, not omission-based. For every enabled
`(Profile, Device)` pair and every Profile remote prefix, the generated direction guard
contains a NEW-flow verdict for each relevant direction:

- host -> Device: `ACCEPT` for OUTBOUND/BIDIRECTIONAL, otherwise explicit `DROP`;
- Device -> host: `ACCEPT` for INBOUND/BIDIRECTIONAL, otherwise explicit `DROP`.

Generated NEW-flow rules are ordered by remote-prefix length descending, then network
address, consistently with Profile dispatch/classification. Omitting an ACCEPT rule is
**not** a sufficient representation of a non-allowing direction because a broader
overlapping Profile on the same Device could otherwise accept traffic classified to a
more-specific denying Profile.

Profile classification is directional:

- host -> Device: match the packet **destination** against Profile remote prefixes;
- Device -> host: first restrict the candidate set to enabled Profiles that reference the
  Device owning the packet's bound ingress interface, then perform longest-prefix matching
  of the packet **source** within that filtered set.

Thus Device -> host classification is explicitly **filter-by-Device first, then
longest-prefix match**. A more-specific prefix belonging only to another Device must not
shadow a less-specific valid Profile for the actual ingress Device.

Both directions use the same longest-prefix ordering within their respective eligible
candidate sets.

This ordering must also be preserved in the generated explicit NEW verdict rules. For
example, with both Profiles on `oc-main`:

    Profile restricted:
        direction = OUTBOUND
        destinations = 10.20.0.0/16
        device_order = [oc-main]

    Profile broad:
        direction = BIDIRECTIONAL
        destinations = 10.0.0.0/8
        device_order = [oc-main]

Device -> host `NEW` from `10.20.5.5` is classified as `restricted` and must hit an
explicit `10.20.0.0/16 DROP` before the broader `10.0.0.0/8 ACCEPT`. The symmetric
host -> Device case uses the same rule-ordering principle. This prevents overlap from
turning a more-specific deny into fail-open behavior.

This matters when one Device is shared:

    Profile corp:
        direction = OUTBOUND
        destinations = 10.0.0.0/8
        device_order = [oc-main]

    Profile support:
        direction = BIDIRECTIONAL
        destinations = 192.168.50.0/24
        device_order = [oc-main]

Both may use the same concrete `vpns00`, yet:

- host -> 10.1.2.3 NEW is classified as corp and accepted;
- 10.1.2.3 -> host NEW through `vpns00` is corp and rejected;
- host -> 192.168.50.10 NEW is support and accepted;
- 192.168.50.10 -> host NEW through `vpns00` is support and accepted.

So the reviewer concern “firewall cannot know Profile on a shared Device” is only true
for an interface-only rule set. ROU's **generated direction guard** classifies the Profile
from remote prefix + traffic direction + Device membership.

Return steering differs by flow-initiation direction.

For OUTBOUND, no architecture-mandated conntrack mark is required:

- Device -> host return traffic is accepted only on the same currently bound
  Device-interface/host0 pair and follows main `default -> host0`;
- host -> Device traffic is destination-dispatched back to the Profile table.

For INBOUND/BIDIRECTIONAL, destination dispatch alone cannot preserve the tunnel that
admitted the remote-initiated flow when more than one egress interface is possible.
Therefore schema version 1 admits an enabled remote-initiated Profile only when:

    capacity(Profile) == 1

where capacity is the sum of `interface_quota` for enabled Devices in that Profile's
`device_order`. Disabled Device references do not count. A configuration transition
that would make the capacity greater than one is rejected before kernel mutation.

In addition, every active Device referenced by an INBOUND/BIDIRECTIONAL Profile must have
a `traffic_envelope` with terminal `default = "drop"`. The Profile constrains the
remote source prefix; the restrictive Device envelope is the mandatory administrator
boundary that explicitly states which host-side destinations/protocols/ports may be
reached by remote-initiated traffic.

Capacity greater than one is a future flow-pinning extension, not part of schema version
1. It requires dedicated kernel evidence for connmark restore before routing, fwmark RPDB
return steering, retired-mark blackhole behavior, rp_filter interaction and conntrack
cleanup. Until that extension is proven, no implementation may silently relax the
capacity-one rule.

Residual tuple matching across two bound interfaces is consequently excluded for
remote-initiated schema-v1 Profiles by the capacity-one rule.

#### B. Device traffic envelope — authored by the administrator

`Device.traffic_envelope` is the coarse operational firewall of the tunnel itself.

It answers a different question: **what traffic is permitted through this Device at all,
regardless of which Profile selected it?**

Examples:

- on `dev-01`, accept new remote-side traffic only from one trusted remote network while
  another site is considered compromised;
- on `dev-02`, temporarily block outbound TCP destination port 8007 while investigating
  suspicious Proxmox traffic.

The same envelope applies to every bound interface of the Device and to every Profile
sharing that Device.

The host/BOU cannot reliably replace this policy: before encapsulation it may not know
which Device will be selected, while after decapsulation the relevant tunnel context exists
only inside ROU.

The Profile-direction guard and Device envelope are cumulative. A packet must satisfy both.
The Device envelope may restrict Profile traffic further; it can never widen a Profile
direction, binding-state or fail-closed decision.

When materialized as ordered firewall rules, **Device-envelope DROP/reject rules precede
generated Profile-direction ACCEPT rules** for the same transit path. This ordering is
normative: a restrictive Device envelope must never be bypassed by an earlier generated
direction ACCEPT.


### 5.4.1 ROU-local INPUT and OUTPUT policy

ROU owns local firewall policy as well as transit FORWARD policy.

`INPUT` is default `DROP`. It accepts only:

- loopback;
- `ESTABLISHED,RELATED` traffic for ROU-local connections;
- from `host0`, `NEW` traffic to the configured internal publication endpoints
  (ROU-local address + protocol + internal port/range).

Traffic arriving from any Device interface toward a ROU-local address is dropped,
including traffic targeting a Device's own transport listener/publication endpoint. This
is defense-in-depth and does not block the publication relay: the host-side relay reaches
the internal listener through `host0`.

`OUTPUT` is default `DROP`. Schema version 1 accepts only:

- loopback;
- `ESTABLISHED,RELATED` ROU-local traffic;
- locally initiated traffic whose egress is `host0`.

No locally generated OUTPUT is implicitly accepted through Device interfaces. The first
production schema deliberately leaves the underlay destination unrestricted once egress is
`host0`; future DeviceManager transport configuration may narrow NEW underlay traffic to
explicit transport endpoints without changing routing semantics.

### 5.5 Unbound and over-quota interface isolation

A matching interface that is over-quota or otherwise unbound is observable only.

It receives:

- no Profile route;
- no generated payload ACCEPT state;
- no Device envelope ACCEPT state merely because the interface exists.

Inbound payload from such an interface is rejected by the owned transit policy. Its
existence cannot create an alternate forwarding path.

**Backend proof boundary.** The normalized identity is `(ifname,ifindex)`, but the current
Python iptables-legacy materializer matches interfaces by reusable name. Consequently, a
same-name/new-ifindex generation that appears before the controller observes the old
generation's disappearance may transiently match old name-based rules. Observed
same-name/new-ifindex replacement is treated as structural drift and repaired under the
global barrier, but that does not prove absence of the pre-observation window.

Strict production isolation for dynamically reusable interface names is therefore gated by
EXP-017. The preferred resolution is an ifindex-aware firewall materialization (for
example nftables numeric `meta iif/oif`) or an equivalently strong proven lifecycle
serialization. This gate does not weaken the domain invariant; it identifies the remaining
backend evidence required to enforce it without a timing window.

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

The human-facing ID grammar intentionally permits a leading digit. IDs are opaque strings:
implementations must not reinterpret them as numbers, shell identifiers or raw/unescaped
systemd unit fragments.

## 7. Device model

Conceptually:

    Device:
        name
        enabled
        expected_interfaces: list[ExpectedInterface]
        publications[]
        traffic_envelope

    ExpectedInterface:
        match: InterfaceMatch
        interface_quota

    InterfaceMatch:
        EXACT(name)
        PREFIX(prefix)

name is the stable identifier referenced by Profiles.

enabled is an administrative state owned by the Device side. A disabled Device is not
bound, monitored, published or otherwise processed by ROU. An enabled Profile may refer to
a disabled Device; this is normal operational state, not a configuration warning or error.

A minimally valid disabled Device therefore needs only its identifier and:

    enabled = false

The remaining Device fields are not deeply validated while the Device is disabled.

An enabled Device is bound to ROU only when at least one enabled Profile references it.
An enabled Device referenced by no enabled Profile remains inert: DeviceEngine does not
discover its interfaces, create publications or maintain Device runtime state.

### 7.1 Expected interfaces and discovery

expected_interfaces is an **ordered** list of interface expectations. Each
ExpectedInterface combines a typed match with the maximum number of simultaneously matched
runtime interfaces ROU is prepared to bind for that expectation.

The two match types are:

    EXACT
    PREFIX

An EXACT expectation has interface_quota = 1.

A PREFIX expectation has an explicitly configured positive interface_quota. The quota is a
ROU admission quota for that selector, not a statement about how many interfaces the
underlying VPN implementation could theoretically create.

The order of expected_interfaces is semantically significant. It defines priority ranges
inside the Device: all interfaces admitted through an earlier expectation outrank all
interfaces admitted through a later expectation.

Selector namespaces must be pairwise disjoint:

- within one Device;
- between all enabled Devices that are required by at least one enabled Profile.

One concrete runtime interface must therefore map to at most one active ExpectedInterface.

DeviceEngine discovers runtime interfaces mapping to enabled Devices required by at least
one enabled Profile.

Runtime interface identity is:

    (ifname, ifindex)

Same-name/new-ifindex is a fresh runtime interface.

Tunnel-local IP addresses, peer addresses and transport internals are Device concerns.
Traffic routing uses direct-device routes and does not require tunnel peer IPs.

### 7.2 Quota and admission

For one ExpectedInterface, DeviceEngine may bind no more than
ExpectedInterface.interface_quota matching runtime interfaces.

DeviceEngine may observe additional matching interfaces for diagnostics, but over-quota
interfaces are not bound and never reach TrafficEngine. A newly observed interface never
evicts a bound survivor merely because it would sort earlier by name or appear later in
the environment snapshot.

If a bound interface disappears and the disappearance is verified and committed, a
previously over-quota matching interface may occupy the freed quota on a later reconcile.

Promotion is deterministic without reordering survivors. DeviceBindingState preserves the
first-observed candidate order. Newly observed candidates append in fresh kernel-snapshot
order; candidates first observed in the same logical event use ifindex only as the
tie-break. No lexical ifname sort is introduced. After restart, currently observed
candidates form a fresh initial observation set under the same rule.

For allocation purposes the aggregate Device quota is derived as:

    Device.interface_quota =
        sum(ExpectedInterface.interface_quota)

This aggregate is not separately configured.

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

`traffic_envelope` is the administrator-authored firewall policy of a Device/tunnel, as
distinguished explicitly from the generated Profile-direction guard in §5.4.

The minimum capability surface is:

- Device-relative direction: **from-device** / **to-device**;
- source IPv4 prefix match;
- destination IPv4 prefix match;
- protocol match at least for TCP, UDP and ICMP;
- TCP/UDP source/destination port match where applicable;
- explicit allow/drop action;
- explicit/default terminal policy.

Draft 5 fixes the schema-version-1 TOML grammar in the reviewed production configuration
contract. The envelope is optional. If present, it contains ordered first-match rules and
an explicit terminal default. Rule matches may constrain Device-relative direction,
source/destination IPv4 prefixes, protocol and TCP/UDP source/destination ports.

Envelope `allow` materializes as RETURN to the generated Profile guard, never as FORWARD
ACCEPT. Envelope `drop` materializes as DROP. The envelope is traversed before
ESTABLISHED/RELATED and generated NEW verdicts, so it can restrict existing flows while
never widening Profile.direction.

A Profile may use a Device only under this hard envelope. Sharing a Device does not create
a per-Profile copy of the administrator firewall; the same Device policy applies to all of
its bound interfaces and Profiles.

Every enabled Device also explicitly selects schema-v1 payload NAT mode `none` or
`masquerade`. NAT is Device-scoped. MASQUERADE is emitted only on currently bound
interfaces and only for remote prefixes of enabled Profiles that reference that Device.
There is no implicit NAT default and explicit SNAT is not part of schema version 1.

## 8. Device transport publication

A Device may publish zero or more TCP/UDP transport endpoints.

Schema version 1 uses the reviewed mapping grammar:

    <external-port-or-range>/<tcp|udp>[><internal-port-or-range>]

Omitting the internal side means equal external/internal ports. Range bounds are inclusive
and external/internal cardinality must match.

Conceptually a publication maps:

    host-side ROU port/protocol
        -> internal Device transport listener inside the ROU namespace

Publication belongs to Device binding, not to Profile routing. It is a ROU-owned host-side
socket/relay resource. What the host or BOU permits, blocks or further publishes outside
that socket is outside ROU responsibility.

For UDP, publication must preserve independent per-peer return-path associations. TCP
publication is connection-oriented relay.

ROU local INPUT is default-DROP. Publication admits only host0-originated traffic to the
configured internal local address/protocol/port endpoints needed by the relay/listener
path. Publication never implies blanket INPUT permission and never permits Device-interface
traffic to ROU-local listeners.

Publication workers/sockets follow the supervision contract in §3.4.

A Device not required by any enabled Profile has no publication sockets.

Across active Devices, same-protocol external endpoint ranges are disjoint. Internal target
ranges on the common host0 IPv4 address are also disjoint across different active Devices;
multiple external aliases may intentionally target the same internal endpoint within one
Device. The host-side publication bind IPv4 address belongs to instance configuration.

## 9. Profile model

Conceptually:

    Profile:
        name
        enabled
        direction
        destinations[]
        device_order[]

name is the stable Profile identifier derived from the human-facing TOML table key.

A Profile describes how a set of **remote/VPN-side prefixes** is served and which side may
initiate flows involving those remote prefixes. It contains no runtime interface names,
ifindex values, tunnel addresses, peer addresses, metrics or Device discovery rules.

`enabled` and `direction` are independent properties.

`direction` has stateful transit meaning:

- **OUTBOUND** — host side may initiate NEW flows toward remote prefixes;
- **INBOUND** — remote side may initiate NEW flows through a bound Device toward the host;
- **BIDIRECTIONAL** — either side may initiate NEW flows.

Return traffic for an admitted flow is allowed in either direction, subject also to the
Device envelope.

The same remote-prefix set is matched as destination on host -> Device traffic and as
source on Device -> host traffic. This is why BIDIRECTIONAL is not “routing without an
iif constraint”: it is a precise two-sided initiation policy over one remote-prefix set.

Disabled Profiles are not deeply validated or materialized. They may be retained as
incomplete future configuration.

## 10. Destinations and profile dispatch

destinations[] is the non-empty set of remote/VPN-side IPv4 prefixes served by the Profile.

The field name reflects the ordinary host -> VPN routing view. For Device -> host NEW-flow
classification, the same prefixes are matched as remote **source** prefixes, per §5.4.

The term is intentionally distinct from kernel route: it expresses remote-prefix policy;
routes are runtime materialization.

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

    blackhole default metric BLACKHOLE_METRIC

Per-destination blackholes are no longer part of the production model; terminal blackhole
default is sufficient to prevent fall-through from a dispatched Profile table. For a
Profile containing 0.0.0.0/0, this blackhole has the same prefix length as normal/default
payload routes, so BLACKHOLE_METRIC is part of the normative priority contract.

## 11. Profile Device order and metric allocation

device_order[] is an ordered list of Device identifiers and contains no additional
Profile-local Device parameters.

A Device may be shared by any number of enabled Profiles. Its use is explicit in each
Profile through device_order[].

Metric priority has two static levels:

    Profile.device_order[]
        -> Device.expected_interfaces[]

All bound interfaces of an earlier Device outrank all bound interfaces of a later Device
within that Profile. Inside one Device, all interfaces admitted through an earlier
ExpectedInterface outrank all interfaces admitted through a later ExpectedInterface.

Metric allocation is internal to ROU:

    FIRST_NORMAL_METRIC = 1
    METRIC_STEP = 1

For every route metric used by an active Profile table, the required ordering is:

    normal metric < UNAVAILABLE_METRIC < BLACKHOLE_METRIC

The exact numeric tail constants are implementation/platform constants, but the ordering
is normative. Normal metric-space validation must reserve both tail values.

Only **active Devices** participate in current metric allocation: an active Device is an
enabled Device referenced by at least one enabled Profile. A known disabled Device remains
in device_order as configuration policy but receives no current metric range and consumes
no current metric space. If no enabled/bound Device remains usable for a Profile, that
Profile remains valid but operationally fail-closed.

For each enabled Profile, each active referenced Device receives a Profile-local metric
range whose width is the derived Device.interface_quota. That Device range is subdivided,
in expected_interfaces order, into fixed ranges sized by each
ExpectedInterface.interface_quota.

Within one PREFIX expectation range, a bound survivor keeps its assigned slot for its
continuous bound lifetime. A new interface receives a currently free slot in that range;
existing survivors are never reordered merely because another interface appears or
disappears.

Because every Profile has its own routing table, metric namespaces are independent between
Profiles. The same bound interface may therefore have different metrics in different
Profiles.

Metric assignment belongs to:

    (Profile, ifname, ifindex)

not to Device or interface globally.

The assignment remains stable for the whole continuous period in which the same runtime
interface remains bound and the Profile continues to use that Device. Availability changes
do not change its normal slot. A removed assignment is not reusable until the removal has
been verified and committed.

For every enabled Profile, bootstrap must verify that the sum of the derived aggregate
quotas of all **active** Devices in device_order fits the available normal metric space
after reserving UNAVAILABLE_METRIC and BLACKHOLE_METRIC.

If a previously disabled Device is enabled by a future CandidateConfig, metric ranges may
be re-projected as part of that verified configuration transition. No stable-metric
promise spans a configuration change that alters the active Device set or its ordered
quota layout.

## 12. Unavailable-path fallback

Availability is planner input.

AVAILABLE and UNKNOWN paths remain in the normal routing tier and use their stable normal
metric. UNKNOWN means only that DeviceEngine has no positive availability determination;
it does not mean proven health.

Only a path positively classified UNAVAILABLE is demoted below every normal path
regardless of Device order.

The agreed model reserves one common:

    UNAVAILABLE_METRIC

for the fallback tier.

**EXP-013 completed with Phase A PASS and Phase B PASS.** The production materialization
model is therefore fixed as a persistent shadow fallback:

- every bound interface used by a Profile is continuously represented in the Profile's
  fallback route at UNAVAILABLE_METRIC;
- UNKNOWN and AVAILABLE paths additionally have their stable normal route;
- transition to UNAVAILABLE removes only that path's normal route;
- transition from UNAVAILABLE back to UNKNOWN/AVAILABLE restores its normal route at the
  same stable normal metric;
- one fallback member is represented as a direct-device route;
- two or more fallback members are represented as one equal-cost direct-device multipath
  route at UNAVAILABLE_METRIC;
- the terminal blackhole remains below the fallback tier, including for 0.0.0.0/0.

The equal-cost fallback is **ECMP/hash selection, not sequential failover**. EXP-013 B4
confirmed with real OpenConnect payload that if the selected fallback member is
functionally dead while its interface remains present, Linux does not retry the same flow
through another healthy equal-cost member. This is intentional last-resort semantics and
must not be described as ordered failover.

EXP-013 A3 confirmed that disappearance of one member interface causes Linux to remove the
whole direct-device multipath route rather than shrink it to surviving members.
TrafficEngine therefore rebuilds fallback membership from a fresh binding snapshot after
such a change.

This ordinary binding lifecycle transition does **not** require the global protective
forwarding barrier. Surviving normal routes remain, and while the shadow fallback is
absent/rebuilt the terminal Profile fail-close plus terminal host0 RPDB action prevent
fall-through to main. The transition may cause a brief Profile-local outage but not a
fail-open path.

Likewise, ordinary binding appearance and normalized availability transitions are
incremental reconciliation events and do not require global `ip_forward=0`.

The global protective barrier is reserved for structural/unknown owned-state drift, crash
recovery from unverified state, and policy transitions that cannot be proven safe as an
incremental update.

Example for one destination with three bound interfaces, all UNKNOWN:

    metric 1      -> direct route via member A
    metric 2      -> direct route via member B
    metric 3      -> direct route via member C
    metric 65535  -> one shadow ECMP fallback with members A+B+C
    metric 65536  -> terminal blackhole

The same persistent shadow fallback exists while the paths are AVAILABLE; an UNAVAILABLE
classification removes only that member's normal-tier route and leaves its shadow
membership unchanged.

UNKNOWN availability does not terminate a bound-interface lifetime and does not demote a
path.

The fallback mechanism is implemented in the first production code intentionally, while
the **trigger** that positively classifies a bound interface as UNAVAILABLE is deliberately
deferred to future DeviceManager/Device-specific detector work. Until such a detector is
implemented, ordinary bound interfaces remain UNKNOWN unless an explicit test/provider
injects stronger evidence. Future detectors may move an interface between UNKNOWN,
AVAILABLE and UNAVAILABLE without changing its normal metric assignment.

## 13. DeviceEngine

**DeviceEngine** owns the ROU-side mechanisms that make existing Devices usable:

- determine which enabled Devices are required by enabled Profiles;
- bind/unbind those Devices to ROU;
- discover and monitor their runtime interfaces;
- enforce each ExpectedInterface.interface_quota and preserve survivor admission;
- maintain DeviceBindingState;
- maintain publication sockets/relay;
- normalize Device-specific evidence into bound-interface availability;
- publish an immutable DeviceBindingSnapshot to downstream logic.

DeviceEngine does not manage the Device itself. In particular the first production model
does not require it to start, stop, restart, configure or repair a VPN transport.

DeviceEngine may update its binding state because of ordinary system/environment changes
or, in the future, changes caused by DeviceManager. It does not depend on DeviceManager.

## 14. TrafficEngine

**TrafficEngine** consumes Profile policy and bound Device interfaces. It owns:

- Profile-local path construction;
- stable Profile/interface metric assignments;
- per-Profile routing tables;
- host0 RPDB destination dispatch and terminal host-ingress fail-closed action;
- generated stateful Profile-direction transit policy;
- Device `traffic_envelope` materialization;
- payload NAT policy where configured/required;
- fail-closed Profile routing.

The two filtering layers are intentionally separate:

1. **Profile-direction guard** — generated mechanically by ROU from Profile direction,
   remote prefixes and bound Device membership.
2. **Device traffic envelope** — administrator-authored tunnel firewall shared across all
   Profiles using that Device.

For a shared Device, the generated guard identifies the Profile by remote prefix and
traffic direction; the Device envelope remains Device-scoped.

Only currently bound interfaces participate in payload ACCEPT state. Matching but
over-quota/unbound interfaces cannot become transit merely because they exist.

TrafficEngine does not discover Device interfaces itself and does not consume raw
Device-specific transport/publication state.

ROU firewalling does not replace host-side BOU admission control. BOU governs which host
sources may use ROU and how host routing reaches it; TrafficEngine governs payload after it
has entered the appliance.

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

Publication of a Device's TCP/UDP transport endpoint belongs to ROU itself. BOU may still restrict access to that published host-side port like any other firewall.

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

## 19.1 Production protective-barrier scope

Production reconciliation distinguishes **ordinary lifecycle transition** from
**structural/unknown drift**.

Ordinary lifecycle transitions include verified binding appearance/disappearance and
normalized availability changes. They are repaired incrementally with RPDB dispatch
retained.

Lifecycle route mutation is a semantic diff, **not a full Profile-table flush**. The
terminal blackhole default in every affected Profile table must remain continuously
installed while stale normal/fallback routes are deleted and missing routes are added.
This is required because Profiles may overlap: if a more-specific Profile table were
temporarily empty, RPDB lookup could continue to a later broader Profile rule and cross a
policy boundary. Preserving the table-local terminal blackhole prevents that fall-through.

For an additive/new binding, mutation order is route projection -> NAT projection ->
FORWARD admission. Admission is last so a Device requiring MASQUERADE cannot transmit a
newly admitted payload packet before its NAT rule exists. Removal starts by deleting stale
routes, after which stale interface-specific filter/NAT rules are harmless until their
atomic table replacements.

Filter/NAT owned tables are atomically replaced from fresh binding state. These ordinary
transitions do not require global `ip_forward=0`.

Structural/unknown drift includes unexpected owned RPDB state, foreign/unrepresentable
state in owned routing domains, firewall/NAT drift not attributable to a verified binding
transition, appliance-infrastructure loss, crash recovery from unverified state, and
policy transitions whose incremental safety cannot be proven. These use the global
protective barrier:

    ip_forward=0
        -> project complete owned state
        -> apply/repair
        -> fresh observe
        -> verify complete desired state
        -> durable commit
        -> ip_forward=1

This global barrier is intentionally conservative for unknown state, not a normal response
to every Device connection/disconnection.

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

### 21.1 ROU v0 -> production migration boundary

ROU v0 is executable evidence, not the production object model.

**Reuse/prove forward from v0:**

- namespace/veth lifecycle and teardown containment;
- publication relay behavior, including independent UDP peer associations;
- fresh observation and verification-before-commit;
- protective forwarding barrier for structural reprojection;
- direct-device routing observations;
- canonical firewall/NAT inspection techniques;
- fatal containment after unrecoverable appliance-infrastructure loss.

**Rewrite/generalize for production:**

- hard-coded binding/capacity -> Device/ExpectedInterface;
- one OUTBOUND Profile -> multiple Profiles with stateful direction semantics;
- fixed route metrics -> two-level Profile-local metric ranges;
- v0 filter shortcuts -> generated Profile guard + Device envelope;
- hard-coded configuration -> validated ActiveConfig;
- one transport instance -> generic Device binding/publication state.

### 21.2 Production testing strategy

Production evidence is layered:

1. rootless unit tests for config/domain/selector/quota/rule/metric/transition projection;
2. privileged disposable-netns integration tests for RPDB, routes, sysctls, firewall/NAT
   and namespace lifecycle without a real VPN;
3. target-kernel experiments for uncertain Linux behavior — EXP-013 has closed the
   unavailable common-metric materialization gate;
4. real-VPN live gates for protocol/end-to-end behavior that dummy interfaces cannot prove.

Rootless CI runs on every PR/push. Kernel/live gates remain explicit experiment procedures
and are rerun when code first relies on the behavior they prove or target kernel/network
tool assumptions materially change.

### 21.3 Scale and representability

The first production model does not invent small arbitrary limits for Profiles, Devices or
bindings.

Configuration is accepted only if it is representable in finite owned resource spaces,
including:

- normal metric space below the unavailable/blackhole tail;
- routing-table/RPDB-priority space;
- selector/interface namespace constraints;
- implementation resource limits for publications and firewall rules.

Non-representable configuration is rejected before mutation; it is never silently
truncated.

Performance/stress limits beyond representability are measured from implementation tests
and documented from evidence rather than guessed as architecture constants.

### 21.4 Coexistence with host VPNs

ROU does not special-case unrelated VPN software in the host namespace.

The host routing domain decides how ROU's outer VPN transport reaches the network; it may
itself traverse another host VPN if host policy says so. Conversely, payload reaches ROU
only when host routing/BOU sends it to `rouvpn0`.

ROU does not seize or rewrite unrelated host VPN routes.

## 22. NG1 production-model invariants

1. ROU owns its private network namespace and host-facing veth infrastructure.
2. ROU exposes one conventional host-facing L3 interface; payload and VPN transport share it using ordinary Linux routing semantics.
3. VPN transport listeners/processes and tunnel interfaces live inside the ROU namespace.
4. BOU remains an independent host-side admission/routing concern; ROU and BOU require no safety-critical runtime RPC.
5. ROU bootstrap owns stable instance link addressing and required namespace IPv4 sysctls.
6. The first production payload model is IPv4-only and forwarding is enabled only after required owned state is verified.
7. ActiveConfig contains Devices and Profiles; the human-facing TOML file is parsed into that runtime model.
8. Device describes an external networking/VPN resource; Profile describes remote-prefix service and flow-initiation policy.
9. Device and Profile each have a stable opaque identifier and independent enabled state; leading-digit IDs are intentionally permitted.
10. A disabled Device or Profile may be minimally described by its identifier plus enabled=false and is not deeply validated.
11. An enabled Profile may reference a known disabled Device without error or warning.
12. An unknown Device reference from an enabled Profile is a configuration error.
13. An enabled Device is active/bound only if referenced by at least one enabled Profile.
14. DeviceEngine discovers interfaces only for active Devices.
15. Concrete runtime interface identity is (ifname, ifindex); same-name/new-ifindex is a fresh interface.
16. Device.expected_interfaces is ordered and contains ExpectedInterface entries.
17. Every ExpectedInterface has an EXACT or PREFIX match and an interface_quota.
18. EXACT expectations have interface_quota=1; PREFIX expectations require an explicit positive quota.
19. Active ExpectedInterface selector namespaces are pairwise disjoint within a Device and across active Devices.
20. Device.interface_quota is derived as the sum of ExpectedInterface quotas.
21. Bound survivors are never reordered by newcomers; over-quota promotion follows committed first-observed order with kernel-snapshot order and ifindex tie-break for simultaneous fresh candidates.
22. Over-quota/unbound matching interfaces are observable but receive no payload route or payload ACCEPT state.
23. Device publication belongs to Device binding and ROU, not Profile routing or BOU, and publication workers are supervised ROU-owned state.
24. Device-specific raw transport evidence does not cross into TrafficEngine; DeviceEngine exports normalized interface availability.
25. Bound-interface availability supports UNKNOWN, AVAILABLE and UNAVAILABLE independently of interface presence.
26. UNKNOWN and AVAILABLE use the normal routing tier; only positive UNAVAILABLE classification causes fallback demotion.
27. Profile contains name, enabled, direction, destinations[] and device_order[]; runtime interface details are absent from Profile config.
28. destinations[] denotes strict canonical remote/VPN-side IPv4 prefixes; host-bit correction is never implicit.
29. Duplicate remote prefixes are forbidden globally across enabled Profiles; overlap at different prefix lengths is allowed.
30. Host -> Device Profile dispatch matches remote destination prefix; Device -> host NEW-flow classification first filters enabled Profiles by ingress-Device membership and then longest-prefix matches the remote source within that filtered set.
31. Host-side RPDB dispatch is longest-prefix-first and ends with a terminal iif-host0 fail-closed action so unmatched forwarded host traffic cannot fall through to main default.
32. ROU-owned FORWARD is default-DROP; INVALID is rejected first; ESTABLISHED/RELATED ACCEPT exists only for currently bound interface<->host0 pairs; and an explicit ACCEPT-or-DROP NEW verdict is materialized for every enabled (Profile, Device, remote-prefix) pair in each relevant direction.
33. Device traffic_envelope is separate administrator-authored Device/tunnel firewall policy; it applies to all Profiles sharing that Device.
34. Generated Profile direction and Device envelope are cumulative; neither may widen the other, restrictive Device-envelope rules precede generated direction verdicts, and explicit NEW direction verdicts are longest-prefix-first so a broader Profile cannot override a more-specific deny.
35. Each enabled Profile owns one fail-closed routing table with one terminal blackhole default.
36. Per-destination blackholes are not part of the production model.
37. device_order[] contains only Device identifiers and defines Profile-local Device preference.
38. A Device may be shared by multiple Profiles; its interfaces may receive different metrics in each Profile.
39. Metric priority is Profile.device_order first, then Device.expected_interfaces order.
40. Metric allocation begins at 1 with step 1 and is internal to ROU.
41. Only active Devices consume current Profile-local metric ranges; disabled Device references consume no current metric space.
42. Each active Profile-local Device metric range is sized by derived Device.interface_quota and subdivided by ExpectedInterface quotas.
43. Every normal metric is strictly lower than UNAVAILABLE_METRIC, which is strictly lower than BLACKHOLE_METRIC.
44. Metric-space validation reserves UNAVAILABLE_METRIC and BLACKHOLE_METRIC before admitting normal quota ranges.
45. Metric assignment belongs to (Profile, ifname, ifindex) and remains stable for the continuous bound lifetime within one ActiveConfig generation.
46. Availability changes do not change the normal metric slot.
47. Removed metric assignments are not reusable before verified commit of removal.
48. UNAVAILABLE paths share one final fallback metric; EXP-013 proved persistent shadow direct-device fallback materialization, with one member as a direct route and multiple members as equal-cost ECMP multipath.
49. DeviceEngine owns Device binding/discovery/quota/publication state; TrafficEngine owns Profile routing, generated direction guard, Device envelope materialization, firewall/NAT and fail-closed transit state.
50. PlannerEngine coordinates desired state and transitions without merging Engine ownership domains.
51. Runtime decisions use fresh EnvironmentSnapshot observations; events are wakeups only.
52. Apply success is not commit; fresh observation and complete verification precede committed-state changes.
53. Device processes normally start independently inside the already existing ROU namespace; DeviceEngine never equates process-start success with a usable binding.
54. Detailed DEBUG decision logging is required for all Engines and must never expose secrets.
55. Runtime/diagnostic artifacts use subject-area prefixes planner-*, device-* and traffic-*.
56. Future DeviceManager may change Device lifecycle/configuration but is independent of DeviceEngine.
57. Future warm reservation is Profile demand aggregated globally across shared Devices.
58. RC2/RC3 and ROU v0/EXP-012 remain evidence and implementation-history sources; superseded BindingSpec/capacity terminology is not normative for production NG1.
59. The first production payload model disables IPv6 on ROU-owned payload interfaces rather than relying only on disabled IPv6 forwarding.
60. Higher-priority local-table delivery of host0 traffic addressed to ROU-owned local endpoints is intentional and is not an escape from the forwarded-payload fail-closed guard.
61. NEW-flow direction policy is never omission-only: each enabled (Profile, Device, remote-prefix) pair materializes an explicit ACCEPT or DROP verdict for each relevant direction, ordered longest-prefix-first.
62. Ordinary binding appearance/disappearance and normalized availability changes are incremental lifecycle transitions and do not require the global protective barrier; structural/unknown owned-state drift and unverified recovery do.
63. Router and instance human-facing TOML require schema_version=1; unknown or missing versions are rejected.
64. Every enabled Device explicitly selects payload NAT mode none or masquerade; NAT is Device-scoped and MASQUERADE is restricted to bound interfaces plus remote prefixes of enabled Profiles referencing that Device.
65. Device publications use the schema-v1 ext-port-or-range/protocol[>internal-port-or-range] grammar; active external endpoints may not overlap for one protocol, and internal endpoints may not overlap across different active Devices.
66. Device traffic_envelope is optional; when present it has ordered first-match rules and an explicit terminal default. Envelope allow materializes as RETURN rather than ACCEPT so it cannot widen generated Profile policy.
67. Traffic-envelope traversal precedes ESTABLISHED/RELATED and generated NEW verdicts for the relevant bound Device interface, allowing Device restrictions to terminate existing flows.
68. Instance schema version 1 fixes the internal peer name to host0, requires explicit stable IPv4 link addresses plus publication bind address, and uses absolute router-config/state-file paths.
69. Instance identifiers use the same opaque [a-z0-9][a-z0-9-]* grammar as Device/Profile IDs.
70. INBOUND/BIDIRECTIONAL Profiles are valid in schema version 1 only when active interface capacity is exactly one and every active referenced Device has a traffic_envelope with default=drop.
71. Capacity greater than one for remote-initiated Profiles requires a separately proven flow-pinning extension; destination dispatch alone is insufficient return steering.
72. ROU-owned INPUT is default-DROP and admits only loopback, local ESTABLISHED/RELATED, and host0 to configured internal publication endpoints; Device interfaces have no implicit ROU-local access.
73. ROU-owned OUTPUT is default-DROP and admits only loopback, local ESTABLISHED/RELATED, and locally generated traffic whose egress is host0.
74. The persistent shadow fallback is implemented before its production availability trigger; positive UNAVAILABLE classification is intentionally deferred to future DeviceManager/Device-specific detector work.
75. net.ipv4.fib_multipath_hash_policy is an observed/owned namespace prerequisite and may not be silently inherited when ECMP fallback can become effective.
76. Incremental lifecycle route repair never flushes a Profile table or removes its terminal blackhole; the blackhole remains continuously installed so a temporarily missing more-specific route cannot fall through to a broader overlapping Profile rule.
77. With the current iptables interface-name backend, same-name/new-ifindex replacement is treated as structural/unknown drift and uses the global barrier because old name-based rules could otherwise match the fresh interface generation before verification.
78. Incremental binding admission installs route state first, required NAT second, and generated FORWARD admission last; a newly routable MASQUERADE Device is never intentionally admitted before translation state exists.
