# VPN-GATE NG3 — Architecture Report

**Status:** NG3 architecture, current Release 1 closure with executable reference slices  
**Cycle:** `ng3-design-cycle-20261116-primary-requirements-basis-40m`  
**Requirements:** `design/NG3/requirements.md`  
**Component model:** `design/component-model.md`

This document is an implementation report for accepted NG3 requirements.

It is not a source of new product semantics.

No NG2 component is inherited merely because it existed. Historical NG2 design may be used
as evidence that a mechanism is technically plausible or as a source of failure modes, but
every NG3 architectural element below must be justified again by NG3 requirement IDs.

## Current executable reference evidence

The architecture now has bounded executable reference slices under
`design/NG3/code/python/rou/`.

These slices are implementation/evidence for accepted contracts. They are **not** a claim
that the Release 1 daemon, Linux actuation layer or deployment lifecycle is complete.

Current trace:

| Architecture responsibility / contract | Executable reference | Review evidence |
| --- | --- | --- |
| ConfigurationAdapter structural Device/Profile normalization | `domain.py`, `config.py` | `NG3-2026-11-16-structural-config-code-review.md` |
| authoritative VPNPathAdapter interface-identity observation boundary | `interface_identity.py`, `interface_inventory.py` | `NG3-2026-11-16-interface-inventory-code-review.md` |
| shared current Device binding projection / stable logical slots | `binding.py` | `NG3-2026-11-16-device-binding-projection-code-review.md` |
| PayloadProfileRequest structural projection | `payload_profile.py` | `NG3-2026-11-16-payload-profile-request-code-review.md` |
| PayloadPolicyCalculator NEW-flow Profile classification | `profile_classification.py` | `NG3-2026-11-16-profile-classification-code-review.md` |
| PayloadTrafficManager bounded availability confirmation state | `availability_confirmation.py` | `NG3-2026-11-16-availability-confirmation-code-review.md` |
| AvailabilityPriorityCalculator effective-order transformation | `availability_priority.py` | `NG3-2026-11-16-availability-priority-code-review.md` |
| NetworkPolicyExecutor pure priority-transition planning primitive | `route_priority.py` | `NG3-2026-11-16-route-priority-planner-code-review.md` |
| NetworkPolicyExecutor re-observed partial-state priority convergence | `route_priority_convergence.py` | `NG3-2026-11-16-route-priority-convergence-code-review.md` |
| NetworkPolicyExecutor single-attempt observe/apply/re-observe contract | `route_priority_executor.py` | `NG3-2026-11-16-route-priority-executor-attempt-code-review.md` |
| NetworkPolicyAdapter/Executor owned route-key inventory projection | `route_priority_inventory.py` | `NG3-2026-11-16-route-priority-inventory-code-review.md` |
| NetworkPolicyExecutor bounded physical iproute2 priority backend | `iproute_priority_backend.py` | `NG3-2026-11-16-iproute-priority-backend-code-review.md` |
| Profile-level multi-domain priority coordinator | `route_priority_profile.py` | `NG3-2026-11-16-route-priority-profile-coordinator-review.md` |
| lower Adapter route-priority realization contract | `route_priority_realization.py` | `NG3-2026-11-16-route-priority-realization-contract-review.md` |
| shared lower network-policy deterministic allocation | `network_policy_layout.py` | `NG3-2026-11-16-network-policy-layout-allocator-review.md` |
| accepted NG3 Linux platform resource space | `linux_policy_platform.py` | `EXP-028-result-20261116.md` |
| semantic Profile/allocation -> route-key priority realization | `route_priority_domain_builder.py` | `NG3-2026-11-16-route-priority-domain-builder-review.md` |
| explicit direct-device VPN integration route realization | `direct_device_route.py` | `NG3-2026-11-16-direct-device-route-realizer-review.md` |
| complete payload route/RPDB desired-state projection | `payload_routing_desired.py` | `NG3-2026-11-16-payload-routing-desired-state-review.md` |
| strict whole-reserved route/RPDB structural observation | `structural_routing_inventory.py` | `NG3-2026-11-16-structural-routing-inventory-review.md` |
| pure payload actual-vs-desired structural comparison | `payload_routing_compare.py` | `NG3-2026-11-16-payload-routing-comparison-review.md` |
| managed-netns structural forwarding gate | `forwarding_gate.py`, `linux_forwarding_gate.py` | `NG3-2026-11-16-forwarding-gate-code-review.md`, `EXP-030-result-20261116.md` |
| nft table-level ownership observation | `nft_namespace_inventory.py` | `NG3-2026-11-16-nft-namespace-inventory-code-review.md`, `EXP-031-result-20261116.md` |
| invariant payload nft scaffold comparison | `nft_payload_scaffold.py` | `NG3-2026-11-16-payload-nft-scaffold-code-review.md`, `EXP-032-result-20261116.md` |
| guarded physical payload nft scaffold preparation | `nft_scaffold_executor.py`, `linux_nft_scaffold.py` | `NG3-2026-11-16-nft-scaffold-prepare-code-review.md` |
| normalized Device NAT intent -> payload masquerade desired projection | `device_policy.py`, `payload_nat_desired.py` | `NG3-2026-11-16-payload-nat-desired-code-review.md`, `EXP-033-result-20261116.md` |
| cross-contract pure structural integration | `tests/test_pure_structural_pipeline.py` | `NG3-2026-11-16-pure-structural-pipeline-integration-review.md` |

The implementation intentionally stops before unresolved or separately-gated boundaries:

- final Device NAT/firewall/publication user grammar;
- availability user timing grammar;
- Netlink/poll scheduling and full VPNPathAdapter runtime collection;
- general Linux route/RPDB/nft policy mutation beyond the bounded pure-priority route-key backend;
- ICMP execution/probe-plane production mechanism;
- full lifecycle/deployment assembly.

This mapping implements the traceability intent of `VPNG0007-R7.R6.R1` without promoting
reference code into new product semantics.

# 1. Architecture scope of this pass

**Implements:**
- `VPNG0001`
- `VPNG0002`
- `VPNG0003`
- `VPNG0004`
- `VPNG0005`
- `VPNG0006`
- `VPNG0007`
- `VPNG0001-R1`
- `VPNG0002-R2`
- `VPNG0003-R3`
- `VPNG0004-R4`
- `VPNG0005-R5`
- `VPNG0006-R6`
- `VPNG0007-R7`

The primary project requirements above are closed through the accepted derived requirement trees and the architecture traced below.

This pass attempts architecture only for the requirements that are already sufficiently
defined to justify concrete responsibilities:

- payload policy materialization;
- deterministic path preference;
- availability-driven priority adaptation;
- active availability observation;
- fail-closed network-policy application;
- local drift/retry behavior around owned network policy;
- current component-level state publication.

This architecture intentionally does **not** yet define implementation details that no
accepted requirement makes architectural semantics:

- final external configuration field names / textual syntax;
- automatic VPN-session provisioning/configuration, because `VPNG0001-R1.R3.C1` leaves that
  responsibility to the administrator in the first release;
- concrete per-integration administrator command sequences/documents;
- concrete CLI/API/status presentation formatting;
- concrete event-delivery transport;
- final process/package assembly topology where existing contracts do not require one;
- complete Linux route/table/nft/sysctl representation beyond the accepted safety and
  priority-transition mechanisms;
- WireGuard/OpenConnect-specific provisioning machinery;
- TCP/UDP/HTTP availability checks beyond the accepted first-release ICMP constraint;
- a universal event persistence/replay layer.

These omissions are deliberate implementation freedom, not unresolved requirement semantics.

## 1.1. Managed network isolation boundary ("стакан")

**Implements:**
- `VPNG0004-R4.R6`
- `VPNG0004-R4.R6.R1`
- `VPNG0004-R4.R6.R1.R1`
- `VPNG0004-R4.R6.R1.R2`
- `VPNG0004-R4.R6.R1.R3`
- `VPNG0004-R4.R6.R1.R4`
- `VPNG0004-R4.R2`
- `VPNG0004-R4.R4`
- `VPNG0005-R5.R1`
- `VPNG0005-R5.R4`
- `VPNG0007-R7.R3`
- `VPNG0007-R7.R3.R2`

NG3 selects an isolated managed network domain as the architectural boundary for the router
data plane.

For the Linux implementation direction, the minimal current realization is a dedicated
network namespace containing the VPN-GATE-owned virtual network environment.

The explicit host/domain boundary is realized by dedicated boundary links rather than by
using arbitrary host routes/interfaces as implicit product plumbing. For the current Linux
architecture, a dedicated veth-style link is the minimal default for each required
host/domain attachment because it gives one endpoint inside the managed namespace and one
explicit peer outside it without merging the two routing domains.

Inside this domain belong the network objects whose semantics are owned by VPN-GATE,
including:

- payload routing state;
- filtering/NAT state required by accepted policy;
- managed ingress/egress links;
- VPN data-plane adapters/endpoints used as VPN paths;
- probe data-plane state when probing a path requires it.

The managed-domain contract is:

- **ownership:** mutable routing/policy state used only by VPN-GATE lives inside the managed
  domain unless a boundary object is explicitly declared;
- **host boundary:** host connectivity enters through named/dedicated boundary endpoints,
  not through ambient host networking;
- **VPN path placement:** a VPN path's data-plane endpoint used by managed forwarding is
  present inside the managed domain;
- **observation before use:** runtime code verifies the endpoint is present in the expected
  domain before accepting it for managed forwarding;
- **identity:** logical path identity is bound to one verified current concrete endpoint
  through the accepted VPNPathAdapter/configuration contracts.

This closes the architectural shape of the managed domain while keeping concrete external
field names and protocol-specific endpoint discovery as implementation choices.

The host network namespace is outside this managed domain. Interaction with the host must
occur only through explicit boundary links/contracts.

The purpose of this boundary is not "use netns because NG1 used netns". It is to realize
`VPNG0004-R4.R6`: unrelated host network state must not become implicit product state or be
mutated as a side effect of internal routing changes.

The namespace is therefore an architecture choice. If another mechanism can later satisfy
the same isolation/ownership requirements more simply, the requirement does not protect the
namespace itself.

### Architectural consequence for external VPN channels

**Constrained by:**
- `VPNG0001-R1.R3.C1`
- `VPNG0001-R1.R3.C2`

**Implements:**
- `VPNG0001-R1.R3.C1.R1`
- `VPNG0001-R1.R3.C2.R1`

An administrator-provisioned VPN channel is useful to NG3 only when its data-plane endpoint
is available inside the isolated managed network domain.

The architecture therefore rejects the host-only shape:

```text
host namespace:
    vpn0  <-- VPN endpoint used directly by VPN-GATE routing
```

as the normal managed-path model.

The intended shape is:

```text
host / external provisioning environment
        |
        | explicit onboarding boundary
        v
+----------------------------------+
| NG3 isolated managed network     |
|                                  |
|   vpn data-plane endpoint        |
|          |                       |
|   payload routing/filtering      |
|          |                       |
|   explicit host-side boundary    |
+----------------------------------+
```

This section intentionally does **not** specify whether the VPN endpoint arrives by interface
creation inside the namespace, interface movement, process placement, protocol-specific
setup or another mechanism.

For the current scope, onboarding is architecturally closed with respect to both:

- **where** the data-plane endpoint must exist — inside the managed domain behind an explicit
  host/domain boundary;
- **which logical path it represents** — through the verified logical-path binding contract.

Concrete per-integration commands and external field names remain documentation/interface
implementation work.



## 1.2. Architecture-wide implementation requirements

The structure and maintenance rules of this report itself implement cross-cutting NG3
requirements that do not belong to one runtime component.

**Implements:**
- `VPNG0007-R7.R2`
- `VPNG0007-R7.R3.R3`
- `VPNG0007-R7.R4`
- `VPNG0007-R7.R6.R1`
- `VPNG0007-R7.R6.R2`

Consequences for this architecture:

- responsibilities and contracts are described locally enough for human/AI review;
- stable internal contracts are intended to contain unrelated change;
- independent component scopes are intended to support parallel review/development units;
- every material architectural block links back to the requirement tree;
- any requirement/constraint change requires revalidation of the affected architecture
  before implementation continues.

# 2. Real scenarios used by this design

These scenarios are not additional requirements. They are concrete situations used to test
whether the decomposition is necessary and sufficient.

## S1 — Explicitly managed payload

A configured traffic class is allowed to use a configured set of VPN paths. Unrelated host
traffic must not acquire VPN forwarding merely because those paths exist.

Relevant requirements:
- `VPNG0001-R1.R1`
- `VPNG0002-R2.R1`
- `VPNG0002-R2.R2`
- `VPNG0002-R2.R3`
- `VPNG0002-R2.R4`
- `VPNG0004-R4.R1`

## S2 — Preferred path degrades

Two or more paths are allowed. The preferred path becomes practically unusable while at
least one allowed alternative remains usable. New traffic should prefer the usable
alternative, without changing path membership.

Relevant requirements:
- `VPNG0003-R3.R1`
- `VPNG0003-R3.R2`
- `VPNG0003-R3.R2.R1`
- `VPNG0003-R3.R3`
- `VPNG0003-R3.R4`
- `VPNG0003-R3.R5`
- `VPNG0003-R3.R7`

## S3 — Local presence is not sufficient evidence

A VPN interface/process can remain locally present while the remote path property relevant
to the product scenario is no longer usable. Payload may also be idle, so waiting for a
payload failure is not always useful.

The architecture therefore selects active observation as the first NG3 mechanism for
obtaining evidence required by `VPNG0003-R3.R6`. Active probing is an architectural choice,
not a product promise.

Relevant requirements:
- `VPNG0003-R3.R6`
- `VPNG0003-R3.R6.R3`

## S4 — Old observation finishes late

The observed concrete path context changes while an earlier asynchronous check is still
in-flight. Its later result must not modify current preference.

Relevant requirements:
- `VPNG0003-R3.R6.R1`
- `VPNG0003-R3.R6.R2`

## S5 — Network mutation partially fails

The system begins changing owned network policy and one lower operation fails. The next
decision must be based on freshly observed authoritative state and must not silently expose
unallowed forwarding.

Relevant requirements:
- `VPNG0004-R4.R2`
- `VPNG0004-R4.R3`
- `VPNG0004-R4.R4`
- `VPNG0004-R4.R5`
- `VPNG0005-R5.R2`
- `VPNG0005-R5.R3`

## S6 — One cleanup area fails

Shutdown owns several independent resources. Failure to clean one must not prevent attempts
to clean the others, and the failures must remain visible.

Relevant requirements:
- `VPNG0005-R5.R4`
- `VPNG0005-R5.R5`
- `VPNG0006-R6.R3`

# 3. Architecture summary

```text
normalized payload intent
        |
        | RequestEvent / assembly input
        v
+-----------------------+
| PayloadTrafficManager |<---------------------------+
|        Manager        |                            |
+-----------------------+                            |
        |                                            |
        | uses                                       | availability InfoEvent
        v                                            |
+-----------------------+                            |
| PayloadPolicy         |                            |
| Calculator            |                            |
+-----------------------+                            |
        |                                            |
        +--> AvailabilityPriorityCalculator          |
        |                                            |
        v                                            |
+-----------------------+                            |
| NetworkPolicyAdapter  |                            |
|       Adapter         |                            |
+-----------------------+                            |
        |                                            |
        v                                            |
+-----------------------+                            |
| NetworkPolicyExecutor |                            |
|       Executor        |                            |
+-----------------------+                            |
        |                                            |
        v                                            |
managed network domain                               |
                                                     |
                                           +----------------------+
                                           | AvailabilityProbe    |
                                           | Agent                |
                                           +----------------------+
                                                     |
                                                     | uses
                                                     v
                                           +----------------------+
                                           | ActiveProbeDriver    |
                                           | Driver               |
                                           +----------------------+
                                                     |
                                                     v
                                               external network
```

The event-delivery mechanism is intentionally left abstract. NG3 requires the semantic edge,
not a persistent bus, journal or replay system.

The externally provisioned VPN-channel integration adds one narrow Machinery boundary:

```text
logical VPN path intent
        |
        v
+-----------------------+
| VPNPathAdapter        |
|       Adapter         |
+-----------------------+
        |
        v
observed concrete endpoint
inside managed network domain
```

The Adapter resolves and verifies a binding; it does not provision or configure the VPN
session.

## 3.1. External VPN-channel boundary

**Implements:**
- `VPNG0001-R1.R3`
- `VPNG0001-R1.R3.C1.R1`

**Constrained by:**
- `VPNG0001-R1.R3.C1`

For the first release, VPN-GATE consumes VPN channels that have already been deployed and
basically configured by the administrator.

The architecture therefore does **not** introduce a VPN-session/tunnel provisioning Manager
merely because older generations contained VPN process-management machinery.

The product-side boundary defines enough administrator-facing contract to make an externally
provisioned channel:

- place its data-plane endpoint inside the isolated managed network domain;
- identifiable as a concrete VPN-GATE path;
- observable to the extent required by routing, safety and status requirements;
- usable by payload policy;
- documentable as a repeatable administrator procedure.

The exact representation of that contract remains integration-specific. A Linux interface
move, process placement, interface name, protocol-specific handle or another mechanism may be
selected by a supported integration without changing the accepted product semantics.

## 3.2. Logical VPN path binding

**Implements:**
- `VPNG0001-R1.R3.R1`
- `VPNG0001-R1.R3.R2`
- `VPNG0001-R1.R3.R3`
- `VPNG0004-R4.R6.R1.R4`
- `VPNG0007-R7.R3.R1`
- `VPNG0007-R7.R3.R2`

The architecture separates:

```text
logical path identity
!=
concrete current data-plane endpoint
```

The product-facing path identity is stable for the configuration lifecycle. Runtime endpoint
identity may change when the administrator recreates/replaces the externally provisioned VPN
channel.

The human configuration names Devices, not every logical path.

Logical path identity is derived during Device binding normalization from:

```text
Device ID
+ expected-interface selector position
+ stable slot within selector quota
```

The concrete runtime endpoint is the current binding of that logical identity.

A replacement endpoint may become the current endpoint for the same logical path only after
the new binding has been observed and verified.

### VPNPathAdapter

**Component type:** Adapter

**Implements:**
- `VPNG0001-R1.R3.R1`
- `VPNG0001-R1.R3.R2`
- `VPNG0001-R1.R3.R3`
- `VPNG0001-R1.R3.R4`
- `VPNG0001-R1.R3.R4.R1`
- `VPNG0001-R1.R3.R4.R2`
- `VPNG0001-R1.R3.R4.R3`
- `VPNG0001-R1.R3.R4.R3.R1`
- `VPNG0001-R1.R3.R4.R4`
- `VPNG0004-R4.R6.R1.R4`
- `VPNG0007-R7.R3`
- `VPNG0007-R7.R5`

The Adapter is the boundary between logical VPN-path semantics and the externally
provisioned concrete VPN endpoint.

Conceptual boundary:

```text
observe_device_endpoints(active DeviceBindingIntent set)
    -> observed candidate endpoints in managed domain

verify_path_binding(logical_path_id, concrete endpoint)
    -> matched current endpoint
     | absent
     | ambiguous
     | wrong managed domain
     | structurally unusable
```

The Adapter observes lower-domain facts. It does not decide Profile policy or Device
preference.

A successful result must prove at least:

- the endpoint is inside the managed network domain;
- the endpoint matches the normalized binding intent for the logical path;
- exactly one current endpoint is selected;
- a previously superseded endpoint is not returned as current.

The Adapter does **not**:

- create the VPN session;
- configure protocol credentials;
- choose payload eligibility;
- decide path preference;
- decide availability health;
- invent the user configuration syntax.

The semantic content of `normalized_binding_intent` is defined: it must identify one
current concrete endpoint for one logical path. The exact external selector spelling and
protocol-specific discovery mechanics remain replaceable interface/integration details.

### 3.2.1. Transport endpoint provenance

**Implements:**
- `VPNG0001-R1.R3.R5`
- `VPNG0001-R1.R3.R5.C1.R1`

**Constrained by:**
- `VPNG0001-R1.R3.R5.C1`

Transport endpoint provenance is a bounded optional fact attached to the **current verified
path binding**, not part of stable `LogicalPathId` identity:

```text
current PathBinding
    = LogicalPathId + current InterfaceIdentity(ifname, ifindex)

optional current transport provenance
    = transport endpoint/peer identity
      proven by the accepted integration discovery/onboarding contract
      for exactly that current PathBinding
```

The fact answers a different question from the tunnel's inner/network-layer peer address and
from an availability probe target. A public OpenConnect server address, a WireGuard peer
endpoint, an inner point-to-point address and a Profile-specific ICMP target are not assumed
to be interchangeable.

`VPNPathAdapter` is the technical observation boundary for this provenance because it already
owns observation and verification of the concrete external endpoint. A supported integration
may enrich the current binding observation with transport provenance when its accepted lower
contract provides sufficient evidence. The Adapter must return provenance as absent/unresolved
rather than infer it from an interface prefix, slot number, reused ifname, ambient route or an
unrelated inner peer address.

Provenance validity is scoped to the exact current concrete binding. Replacement of the
concrete endpoint invalidates the old provenance together with the old binding; no separate
global generation counter or provenance history is introduced.

Potential consumers remain separate semantic owners:

- `AvailabilityTargetCalculator` may use confirmed transport provenance when an accepted
  integration-specific target derivation formula requires it;
- a future endpoint-scoped Device firewall policy may resolve a logical/named endpoint through
  confirmed provenance and then materialize the rule against the current concrete path;
- status/diagnostics may display confirmed provenance without becoming its source of truth.

The first release does **not** require this fact for ordinary path binding, routing, explicit
availability targets or other functions whose accepted semantics do not depend on it. A
consumer that requires provenance must fail/diagnose that dependent function when provenance
is unavailable; it must not broaden scope to all paths or guess a peer.

The exact human-facing named-endpoint syntax is deliberately postponed to the later
configuration-format review. No named-endpoint grammar is selected here.

**EXP-039 result:** PASS on privileged Linux CI. A real userspace-held
`IFF_POINTOPOINT` TUN exposed its inner point-to-point address peer, but changing the
userspace transport socket peer left generic `ip -j -d link` and `ip -j addr` observation
unchanged and neither transport address appeared there. Therefore transport endpoint
identity is not an organic generic property of a point-to-point TUN interface.
Integration-specific provenance is required; generic interface discovery must not claim to
recover a transport peer merely from point-to-point interface state.

### 3.2.2. Bound endpoint versus route realization

A verified `PathBinding(logical_path_id, InterfaceIdentity)` proves **which current
endpoint** represents the path. It does not, by itself, prove the complete Linux route
next-hop shape for every possible supported VPN integration.

The lower VPN integration contract therefore additionally produces:

```text
PathBinding
    + integration-specific verified topology/contract
        ->
RoutePriorityPathRoute:
    logical_path_id
    current InterfaceIdentity
    gateway = IPv4 | none
    onlink = true | false
```

The route realization must be consistent with the same current concrete endpoint identity
used by the binding.

The generic NetworkPolicyAdapter must not guess `gateway` or `onlink` from:

- interface name;
- Device ID;
- historical transport type;
- the mere presence of an IPv4 peer address;
- ambient host routes.

A supported integration may expose a simpler realization when evidence/onboarding proves it.

#### Direct-device integration capability

For an integration whose accepted lower contract states that protected destinations are
routed directly through the bound interface, the realization is:

```text
gateway = none
onlink  = false
dev     = current bound InterfaceIdentity.ifname
```

Historical EXP-009 H5 is concrete evidence that this shape works for the tested OpenConnect
point-to-point endpoint. WireGuard remains governed by its own cryptokey-routing
(`AllowedIPs`) contract; a WireGuard onboarding profile may use direct-device realization
only when its external configuration makes the Profile destinations valid for that
interface.

Direct-device is therefore an explicit **integration capability**, not a universal property
of every interface matched by `expected_interfaces`.

If the selected integration cannot produce one unambiguous current route realization for a
bound logical path, that path is not structurally ready for payload route materialization.
The lower policy remains unconfirmed/fail-closed; the Adapter does not invent a gateway.

No new user-facing route field is introduced by this boundary. Route realization belongs to
the supported integration/onboarding contract beneath the Device/Profile policy model.

## 3.3. Declarative configuration boundary

**Implements:**
- `VPNG0001-R1.R2.R1`
- `VPNG0001-R1.R2.R2`
- `VPNG0001-R1.R2.R3`
- `VPNG0001-R1.R2.R4`
- `VPNG0001-R1.R2.R4.R1`
- `VPNG0001-R1.R2.R4.R1.C1`
- `VPNG0001-R1.R2.R4.R2`
- `VPNG0001-R1.R2.R4.R2.R1`
- `VPNG0001-R1.R2.R4.R3`
- `VPNG0001-R1.R2.R4.R4`
- `VPNG0001-R1.R2.R4.R4.R1`
- `VPNG0001-R1.R2.R4.R4.R2`
- `VPNG0001-R1.R2.R4.R4.R3`
- `VPNG0001-R1.R2.R4.R5`
- `VPNG0001-R1.R2.R4.R6`
- `VPNG0001-R1.R2.R4.R6.R1`
- `VPNG0001-R1.R2.R4.R6.R2`
- `VPNG0001-R1.R2.R4.R6.R3`
- `VPNG0001-R1.R2.R4.R6.C1`
- `VPNG0001-R1.R2.R5`
- `VPNG0001-R1.R2.R5.R1`
- `VPNG0001-R1.R2.R5.R2`
- `VPNG0001-R1.R2.R5.R3`
- `VPNG0001-R1.R2.R5.R4`
- `VPNG0001-R1.R3.C1.R1`
- `VPNG0002-R2.R1`
- `VPNG0002-R2.R1.R1`
- `VPNG0002-R2.R1.R2`
- `VPNG0002-R2.R2`
- `VPNG0002-R2.R2.R1`
- `VPNG0002-R2.R2.R2`
- `VPNG0002-R2.R3`
- `VPNG0002-R2.R3.R1`
- `VPNG0002-R2.R3.R2`
- `VPNG0002-R2.R3.R3`
- `VPNG0002-R2.R3.C1`
- `VPNG0002-R2.R3.C1.R1`
- `VPNG0002-R2.R4`
- `VPNG0002-R2.R5`
- `VPNG0002-R2.R5.R1`
- `VPNG0004-R4.R1`
- `VPNG0007-R7.R3.R1`
- `VPNG0007-R7.R3.R2`
- `VPNG0007-R7.R5`

NG3 uses the recovered human-facing Device/Profile configuration model recorded in
`design/NG3/config-model.md`.

Users/admins describe product intent; they do not provide an ordered recipe of Linux
networking operations.

The human model is intentionally two-layered:

```text
Device
    = expected external VPN/network resource

Profile
    = desired network behavior using ordered Devices
```

A Device may be shared by multiple Profiles. Profile configuration contains no runtime route
metrics, kernel rules or concrete lower-network command sequence.

### ConfigurationAdapter

**Component type:** Adapter

The Adapter translates an external configuration representation into validated, normalized
domain intents.

It is Direct Machinery: a successful return means the supplied configuration has been
accepted and normalized; a failed return means no dependent network mutation may begin from
that candidate configuration.

The architecture intentionally avoids a global mutable "runtime configuration object".
Instead, the adapter produces explicit domain contracts needed by accepted requirements.

The human-facing parse result is normalized into explicit domain contracts:

```text
DeviceConfigIntent:
    device_id
    enabled
    expected_interfaces[] = ordered(selector, quota)
    nat_intent
    device_firewall?
    publications?

ProfileConfigIntent:
    profile_id
    enabled
    direction
    destinations[]
    device_order[]
    availability_check?
    ordinary_gateway_nat_intent?

DeviceBindingIntent:
    device_id
    expected_interfaces[]

DevicePolicyIntent:
    device_id
    nat_intent
    device_firewall?
    publications?

PayloadProfileRequest:
    profile_id
    direction
    destinations[]
    ordered_paths[]

AvailabilityCheckConfig:
    profile_id
    mechanism
    target = explicit IPv4 | omitted

AvailabilityProbeIntent:
    availability_subject_id = (profile_id, logical_path_id)
    logical_path_id
    mechanism
    target = concrete IPv4
```

Key normalization rules:

- Device/Profile IDs remain stable opaque user identifiers;
- disabled Device/Profile placeholders do not require active-object semantic completeness;
- active Devices are derived as enabled Devices referenced by at least one enabled Profile;
- `DeviceBindingIntent` retains ordered expected-interface selectors and quotas;
- `ProfileConfigIntent` retains explicit direction, remote destinations and ordered Device
  references; optional ordinary-side gateway NAT remains a separate Profile-scoped semantic
  intent whose exact external spelling is deferred;
- `PayloadProfileRequest` contains the concrete ordered logical paths obtained after binding
  while preserving Profile identity/direction/destinations;
- current concrete logical paths are derived from accepted Device bindings, not written
  directly into Profile config;
- supported user-facing values are parsed strictly and canonically; invalid/ambiguous input is
  rejected rather than silently repaired;
- field order is semantic only where the contract explicitly declares policy order;
- derived implementation values such as aggregate Device quota, ifindex, route metrics and
  table/rule priorities are not required from the user;
- Device NAT intent is explicit; no implicit active-Device NAT default is assumed;
- Device firewall is normalized as an ordered first-match policy that can only narrow Profile
  permission; omitted policy is permissive at the Device layer and explicit policy has
  terminal no-match DROP;
- Device transport publication intent is normalized separately from Profile payload routing;
- exact final external grammar for Device firewall/publication remains an interface-review item and is
  not inferred from historical prototype spellings;
- availability subject identity is exactly `(profile_id, logical_path_id)`;
- the same bound interface/path may therefore have independent availability state in
  different Profiles;
- first-release availability mechanism is ICMP;
- an explicit target is preserved exactly;
- bare ICMP is resolved by `AvailabilityTargetCalculator` from Profile/path/Device/binding
  topology before probe runtime;
- probe runtime always receives one concrete IPv4 target.

The recovered external TOML structure, identifier grammar, expected-interface selector forms
and Profile fields are normative interface behavior in `design/NG3/config-model.md`.

Payload policy, Device binding and availability remain separate normalized contracts even
though they originate from one human configuration.

### Device policy normalization

**Implements:**
- `VPNG0001-R1.R2.R4.R6`
- `VPNG0001-R1.R2.R4.R6.R1`
- `VPNG0001-R1.R2.R4.R6.R2`
- `VPNG0001-R1.R2.R4.R6.R3`
- `VPNG0001-R1.R2.R4.R6.C1`
- `VPNG0002-R2.R1`
- `VPNG0002-R2.R2`
- `VPNG0002-R2.R3`
- `VPNG0004-R4.R1`

The configuration boundary keeps Device transport policy separate from Profile need.

```text
DeviceConfigIntent
    -> DeviceBindingIntent
    -> DevicePolicyIntent
```

NAT semantics currently recovered at product level:

```text
none
    -> no VPN-GATE payload source NAT on this Device/path

masquerade
    -> source NAT through the current concrete path of this Device
```

There is no implicit active-Device NAT default.

Device firewall semantics:

```text
effective payload permission
    = Profile permission
      AND
      ordered Device firewall verdict == ALLOW
```

The Device firewall can remove permission but cannot create destinations, directions or path
eligibility absent from Profile policy. Its normalized rules preserve user order and carry
direction/action plus optional L3/L4 match fields; exact external grammar remains deferred.

Transport publication semantics remain a Device/transport concern. The normalized intent
describes an explicitly owned host-side publication boundary into the managed network domain;
it is not part of Profile routing identity or availability health.

Historical traffic-envelope/publication TOML examples are schema-design evidence only. Until an exact
NG3 grammar is accepted, `ConfigurationAdapter` must reject unsupported guessed forms rather
than emulate old spellings heuristically.

### AvailabilityTargetCalculator

**Component type:** Calculator

**Implements:**
- `VPNG0003-R3.R6.R1`
- `VPNG0003-R3.R6.R3.R1`
- `VPNG0003-R3.R6.R3.R2`
- `VPNG0007-R7.R1`
- `VPNG0007-R7.R3.R1`
- `VPNG0007-R7.R5`

This pure semantic projection owns default-target derivation above probe runtime.

Conceptual contract:

```text
derive_target(
    availability_subject,
    mechanism,
    explicit_target?,
    accepted policy/path/device/binding/peer topology facts
)
    -> concrete IPv4
     | unresolved
     | ambiguous
```

Rules:

- explicit target -> return exactly that IPv4;
- omitted target -> derive the path-specific target mathematically from already available
  semantics of the concrete availability subject;
- never substitute a global public/default IP;
- the same physical interface may produce different targets for different availability
  subjects;
- unresolved or ambiguous derivation rejects/diagnoses that probe intent before runtime
  execution.

The Calculator does not probe the network and does not own runtime observation state.

Device/integration-specific derivation formulas may be implemented behind this contract. They
must be deterministic projections of already accepted topology semantics and must not require
the user to provide an additional target merely to make bare `icmp` work.

Validation must reject at least:

- invalid/duplicate Device or Profile IDs;
- enabled Device without non-empty valid expected-interface selectors;
- ambiguous active expected-interface selectors;
- enabled Profile without direction, destinations or device_order;
- first-release `inbound`/`bidirectional` Profile whose maximum eligible logical-path
  capacity from currently enabled referenced Devices exceeds 1;
- unknown Device references;
- duplicate Device references inside one Profile;
- duplicate exact destination ownership among enabled Profiles;
- invalid/non-strict IPv4 destination CIDRs;
- missing/invalid explicit Device NAT intent where the supported Device capability requires it;
- Device firewall declarations that would expand rather than restrict Profile permission;
- unsupported/ambiguous Device-firewall or publication grammar;
- malformed or unsupported availability-check mechanism/target;
- a target-less probe when subject/topology semantics cannot produce one unambiguous concrete
  normalized target;
- contradictory declarations that cannot produce one deterministic semantic result.

Known disabled Device references are valid and are skipped operationally.

Disabled Device/Profile placeholders bypass active-object deep semantic validation.

A rejected configuration is not partially materialized.

### Administrator onboarding contract

For each supported externally provisioned VPN-channel integration, administrator
documentation must explain:

1. how to provision the external VPN channel according to its own mechanism;
2. what result must exist inside the managed network domain;
3. how to declare the logical `path_id` and binding intent through the product
   configuration boundary;
4. how to determine that VPN-GATE accepted or rejected the binding.

This closes the architecture of `VPNG0001-R1.R3.C1.R1` without choosing the final configuration
file syntax or a specific VPN protocol.

No ConfigManager, live-reload Engine, configuration database or generic plugin registry is
introduced. Those require separate accepted requirements if they become necessary.

## 3.4. Profile as independent payload-policy domain

**Implements:**
- `VPNG0001-R1.R2.R4.R4.R2`
- `VPNG0001-R1.R2.R4.R4.R3`
- `VPNG0002-R2.R2.R2`
- `VPNG0003-R3.R2.R1`
- `VPNG0004-R4.R1.R1`

A Profile is preserved as a semantic domain even when its current concrete path set is empty.

Normalization is therefore two-stage:

```text
ProfileConfigIntent
    + current valid Device bindings
        ->
PayloadProfileRequest:
    profile_id
    direction
    destinations[]
    ordered_paths[]
```

`ordered_paths` may be empty.

An empty path set does **not** remove the Profile from structural policy. Its destinations
remain classified to that Profile and materialize a fail-closed terminal result rather than
falling through to ambient/main routing.

Availability is applied after this structural request exists. It may reorder
`ordered_paths` through negative priority modification, but it cannot rewrite:

- Profile identity;
- destinations;
- direction;
- Device membership;
- binding eligibility;
- structural existence of the Profile domain.

Profile is not a VPN session/interface/peer, route metric, probe target or Linux-rule
container. Those remain separate lower or adjacent contracts.

# 4. PayloadTrafficManager

**Component type:** Manager

**Implements:**
- `VPNG0001-R1.R1`
- `VPNG0002-R2.R1`
- `VPNG0002-R2.R2`
- `VPNG0002-R2.R3`
- `VPNG0002-R2.R4`
- `VPNG0002-R2.R5`
- `VPNG0003-R3.R1`
- `VPNG0003-R3.R2`
- `VPNG0003-R3.R3`
- `VPNG0003-R3.R4`
- `VPNG0003-R3.R5`
- `VPNG0003-R3.R7`
- `VPNG0004-R4.R1`
- `VPNG0004-R4.R1.R1`
- `VPNG0004-R4.R2`
- `VPNG0005-R5.R2`
- `VPNG0005-R5.R3`
- `VPNG0006-R6.R2`
- `VPNG0006-R6.R4`
- `VPNG0007-R7.R1`
- `VPNG0007-R7.R3`
- `VPNG0007-R7.R5`
- `VPNG0007-R7.R6`

## 4.1. Responsibility

The Manager owns the current semantic payload-policy projection for normalized Profiles.

Its structural input is a set of `PayloadProfileRequest` objects. A request remains present
even when `ordered_paths` is empty, so fail-closed Profile membership is not lost when
bindings disappear.

It owns:

- current accepted structural payload intent;
- current allowed path membership for that intent;
- configured path preference;
- current bounded availability-adaptation state;
- current effective path order;
- orchestration of desired payload network policy through the Adapter;
- current verified payload-policy projection published for observers.

It does **not** own:

- parsing the user configuration;
- VPN process creation;
- active probe transport;
- active probe target/mechanism/cadence;
- Linux route/table/nft representation;
- global user-facing status aggregation.

## 4.2. Why one Manager

The payload policy requirements form one transactional semantic responsibility:

```text
allowed traffic
+ allowed path membership
+ configured preference
+ availability priority modifier
+ fail-closed materialization
= one effective payload policy
```

Splitting membership and priority into independent Managers would create two writers to the
same effective routing domain and would require an additional transactional coordination
protocol not demanded by any accepted requirement.

Keeping them together therefore follows both the product semantics and
`VPNG0007-R7.R1`.

## 4.3. Availability state inside the Manager

For each availability subject (one Profile + logical VPN path), the Manager
may keep only the bounded semantic state necessary to implement `VPNG0003-R3.R3`,
`VPNG0003-R3.R4`, `VPNG0003-R3.R5.R1` and `VPNG0003-R3.R5.R2`:

- whether an availability problem is currently established;
- bounded progress toward establishing a problem;
- bounded progress toward confirming recovery.

No unbounded attempt history, evidence journal or replay log is justified.

**Implements:**
- `VPNG0003-R3.R3`
- `VPNG0003-R3.R4`
- `VPNG0003-R3.R5`
- `VPNG0003-R3.R5.R1`
- `VPNG0003-R3.R5.R2`
- `VPNG0007-R7.R1.R1`

The Manager consumes semantic availability evidence, not raw probe execution results.

Normalized evidence:

```text
AvailabilityEvidence:
    availability_subject_id
    logical_path_id
    observation_context
    outcome = positive | negative | no_evidence
```

where:

- `positive` is accepted evidence that the observed path property is currently usable;
- `negative` is accepted evidence that the observed path property is currently unusable;
- `no_evidence` means the observation attempt does not justify changing path state
  (for example, a local execution failure that does not itself prove path failure).

Only fresh evidence for the current availability subject/path/context enters hysteresis.

For each availability subject the Manager keeps bounded confirmation state:

```text
availability_problem: bool
degradation_progress: 0..degradation_threshold
recovery_progress:    0..recovery_threshold
```

The thresholds are finite local availability-policy parameters. They are not assumed to be
user-configurable unless a later requirement says so.

Transition semantics:

- while `availability_problem == false`:
  - negative evidence advances bounded degradation progress;
  - positive evidence clears degradation progress;
  - `no_evidence` does not fabricate path evidence;
  - reaching the degradation threshold establishes the problem;
- while `availability_problem == true`:
  - positive evidence advances bounded recovery progress;
  - negative evidence clears recovery progress;
  - `no_evidence` does not fabricate recovery;
  - reaching the recovery threshold clears the problem.

On either state transition, obsolete progress is reset.

No observation history, time window, replay log or unbounded attempt count is retained.

Adaptation consumes evidence from the user-selected availability criterion. For the first
release, that criterion is ICMP with explicit or derived target semantics defined below.

## 4.4. Availability affects priority only

The Manager applies availability only after structural policy has established the allowed
path set.

```text
structural allowed paths
        |
        v
configured preference
        |
        v
availability priority modifier
        |
        v
effective order
```

Availability is not allowed to:

- create path membership;
- remove policy permission;
- change traffic membership;
- change direction policy.

**Implements:**
- `VPNG0002-R2.R4`
- `VPNG0003-R3.R2`
- `VPNG0003-R3.R7`

## 4.5. Device binding projection

**Implements:**
- `VPNG0001-R1.R3.R4`
- `VPNG0001-R1.R3.R4.R1`
- `VPNG0001-R1.R3.R4.R2`
- `VPNG0001-R1.R3.R4.R3`
- `VPNG0001-R1.R3.R4.R3.R1`
- `VPNG0001-R1.R3.R4.R4`
- `VPNG0003-R3.R1.R1`

`PayloadTrafficManager` owns the current shared Device-binding projection used by all
Profiles.

For each active Device it combines:

```text
ordered expected-interface selectors/quotas
+
freshly observed candidate endpoints
+
previous current binding projection
```

into bounded current logical paths.

The projection preserves surviving slot assignments when new endpoints appear, so ordinary
environment change does not arbitrarily reorder existing paths.

Each accepted bound path has a stable logical identity:

```text
logical_path_id :=
    Device ID
    + expected-interface selector position
    + stable slot within selector quota
```

The current concrete endpoint binding is separate mutable state and is not part of the
logical identity itself.

The exact serialized/internal logical-path ID format is implementation detail.

No inactive/unreferenced Device participates in discovery/binding work.

Endpoints that match no active selector or match ambiguously do not become managed logical
paths.

For one selector, at most its configured quota is bound.

Linux concrete endpoint identity is `(ifname, ifindex)`; the same ifname with a new ifindex
is a fresh endpoint instance.

Quota admission preserves survivors:

- a newly observed candidate never evicts an already bound survivor merely because its name
  sorts earlier or it appeared in a later snapshot;
- over-quota candidates remain observable but unbound;
- once a bound disappearance is verified/committed, a waiting candidate may occupy the
  freed slot on a later reconciliation;
- waiting-candidate promotion preserves committed first-observed order;
- simultaneously first-observed candidates retain fresh kernel-snapshot order, with
  `ifindex` as the final tie-break;
- lexical ifname sorting is not used as policy.

This is bounded current binding state, not an event history: only the information needed to
preserve current survivor/admission order is retained.

This responsibility remains inside the existing PayloadTrafficManager for now because the
binding projection has no independent actuation or product policy outside the current payload
path set. A separate Device-binding Engine would require evidence of an independent ongoing
responsibility that cannot be represented here.

# 5. PayloadPolicyCalculator

**Component type:** Calculator

**Implements:**
- `VPNG0002-R2.R1`
- `VPNG0002-R2.R1.R1`
- `VPNG0002-R2.R1.R2`
- `VPNG0002-R2.R2`
- `VPNG0002-R2.R2.R1`
- `VPNG0002-R2.R3`
- `VPNG0002-R2.R3.R1`
- `VPNG0002-R2.R3.R2`
- `VPNG0002-R2.R3.R3`
- `VPNG0002-R2.R4`
- `VPNG0002-R2.R5`
- `VPNG0002-R2.R5.R1`
- `VPNG0007-R7.R3.R1`
- `VPNG0007-R7.R5`

The Calculator maps normalized structural intent and already-resolved external facts into a
deterministic semantic payload-policy projection.

It is pure: the same inputs produce the same projection.

This component is justified because policy interpretation is independently testable and must
not depend on hidden network history.

Its semantic inputs are:

```text
enabled ProfileConfigIntent set
+
current Device binding projection
+
normalized DevicePolicyIntent set
```

It first produces one `PayloadProfileRequest` per enabled Profile, then the structural
network-policy projection for those requests.

The Calculator must preserve these invariants:

- Profile remote membership comes only from its strict IPv4 destinations;
- ordinary->VPN NEW classification uses remote destination;
- VPN->ordinary NEW classification first restricts Profiles by actual ingress Device/path,
  then uses remote source prefix;
- exact duplicate destination ownership across enabled Profiles is invalid;
- different-length overlaps resolve deterministically by most-specific applicable Profile;
- path eligibility comes only from Profile.device_order plus current valid bindings of those
  Devices;
- zero eligible paths still preserve the Profile/destination domain with fail-closed terminal
  behavior;
- direction is explicit and independent;
- configured preference follows Profile.device_order -> expected-interface order -> stable
  slot;
- ordered Device firewall verdict is composed with Profile permission before lower Adapter
  materialization and can never widen Profile permission;
- per-path NAT intent comes from the owning Device policy and is independent from availability;
- transport publication intent is not interpreted as Profile payload permission;
- availability state is not an input to structural membership or permission;
- availability can later reorder only already-eligible logical paths.

## 5.1. First-release inbound/bidirectional path-capacity constraint

**Implements:**
- `VPNG0002-R2`
- `VPNG0002-R2.R3`
- `VPNG0002-R2.R3.R3`
- `VPNG0002-R2.R3.C1`
- `VPNG0002-R2.R3.C1.R1`

First release deliberately does not promise remote-initiated multi-path return-path behavior.

During configuration normalization, for every enabled Profile with:

```text
direction = inbound | bidirectional
```

the product computes the maximum eligible logical-path capacity implied by the currently
enabled Devices referenced by that Profile:

```text
Profile max path capacity
    =
sum(
    selector quota
    for every expected-interface selector
    of every currently enabled referenced Device
)
```

Exact selectors contribute quota 1. Prefix selectors contribute their explicit positive
quota.

If the resulting capacity is greater than 1, configuration normalization fails before
dependent network actuation with a diagnostic explaining that first-release
inbound/bidirectional multi-path is unsupported.

Consequences:

- current runtime presence of only one interface does **not** make a capacity>1 Profile
  acceptable;
- a disabled referenced Device contributes no current capacity; enabling it later is itself a
  configuration change and triggers validation again;
- outbound-only Profiles are not constrained by this rule and may remain multi-path;
- runtime disappearance/reappearance inside an already accepted capacity<=1 Profile does not
  change the product contract;
- no runtime fallback guesses return-path semantics if an unsupported topology is presented.

Historical EXP-014 remains the primary evidence candidate for a future release that restores
multi-path inbound/bidirectional support. Its result must not alter Release 1 behavior unless
requirements are explicitly revised.

# 6. AvailabilityPriorityCalculator

**Component type:** Calculator

**Implements:**
- `VPNG0003-R3.R1`
- `VPNG0003-R3.R2`
- `VPNG0003-R3.R3`
- `VPNG0003-R3.R4`
- `VPNG0003-R3.R7`
- `VPNG0007-R7.R1`
- `VPNG0007-R7.R5`

Inputs:

- allowed paths;
- configured deterministic preference;
- current established availability-problem flags.

Output:

- effective ordered allowed path set.

The Calculator does not decide whether a problem is established. That state belongs to the
Manager because confirmation spans observations.

The output always contains the same structurally allowed path membership. Availability can
only change ordering.

# 7. AvailabilityProbeAgent

**Component type:** Agent

**Implements:**
- `VPNG0003-R3.R6`
- `VPNG0003-R3.R6.R1`
- `VPNG0003-R3.R6.R2`
- `VPNG0003-R3.R6.R3`
- `VPNG0003-R3.R6.R3.R1`
- `VPNG0006-R6.R3`
- `VPNG0007-R7.R1`
- `VPNG0007-R7.R3`
- `VPNG0007-R7.R5`

## 7.1. Responsibility

The Agent owns ongoing execution of configured active availability observations.

It owns:

- currently requested normalized observation channels;
- cadence for the selected active-observation mechanism;
- bounded in-flight checks;
- association of each result with the current requested availability-subject identity and
  concrete path observation identity;
- rejection of results that no longer belong to the current observation context;
- local diagnostics about inability to resolve or execute the observation mechanism.

It does not own:

- payload path membership;
- configured route preference;
- availability hysteresis policy outcome;
- effective route order.

## 7.2. Why Agent

Active checking is ongoing observation of an external network condition. The component
does not manage that network condition; it observes it.

Therefore it is an Agent under `design/component-model.md`, rather than a Manager.

## 7.3. Generation token

To implement `VPNG0003-R3.R6.R2`, an in-flight result must carry enough identity to determine
whether it still belongs to the current physical observation context.

The minimal proposed mechanism is a monotonically replaced local observation-generation
token.

The token has no routing-policy meaning.

It exists only to reject stale physical results.

No logical evidence epoch, attempt journal or replay ordering is introduced.

**Implements:**
- `VPNG0003-R3.R6.R2`
- `VPNG0007-R7.R1`

## 7.4. User-defined check criterion and normalized target

**Implements:**
- `VPNG0003-R3.R6.R3.R1`

**Constrained by:**
- `VPNG0003-R3.R6.R3.R1.C1`

The product does not attempt to define one universal semantic "VPN path is good" predicate.

The user selects the check mechanism for one availability subject and may provide an
explicit IPv4 target in external configuration.

The probe runtime boundary receives only normalized requests:

```text
AvailabilityProbeIntent:
    availability_subject_id
    logical_path_id
    mechanism = icmp
    target = concrete IPv4
```

Therefore `AvailabilityProbeAgent` and `ActiveProbeDriver` do not know whether the target
was explicitly configured or derived by `AvailabilityTargetCalculator`.

Current accepted semantics:

1. explicit target -> normalization preserves exactly that IPv4 target;
2. omitted target -> `AvailabilityTargetCalculator` derives one concrete IPv4 from the
   already accepted topology/semantics of this availability subject;
3. there is no universal default probe IP;
4. if derivation is unresolved/ambiguous, runtime probe demand is not produced for that
   subject and the problem is diagnostic.

Target derivation remains above probe runtime and outside `VPNPathAdapter` policy.

Once a concrete target exists, evidence semantics remain user-relative:

```text
reply to the configured/normalized criterion -> positive evidence
valid check with no reply                    -> negative evidence
local execution failure                      -> no_evidence + diagnostic
```

The availability subject and concrete target are both part of the observation context. A
subject/target/path-binding change invalidates in-flight results from the preceding context.

Future TCP/UDP/HTTP checks may add Driver implementations behind the same normalized
criterion contract, but they are not first-release capabilities.

# 8. ActiveProbeDriver

**Component type:** Driver

**Implements:**
- `VPNG0003-R3.R6`
- `VPNG0003-R3.R6.R1`
- `VPNG0003-R3.R6.R3`
- `VPNG0003-R3.R6.R3.R1`
- `VPNG0003-R3.R6.R3.R1.C1.R1`
- `VPNG0007-R7.R3.R2`
- `VPNG0007-R7.R5`

The Driver provides a narrow technical operation:

```text
check(concrete path observation identity, configured mechanism)
    -> technical observation result
```

It hides mechanism-specific execution from the Agent.

For the first release, the concrete supported Driver mechanism is ICMP echo.

The Driver executes one ICMP check through the concrete current VPN path toward the resolved
target and reports technical reply/no-reply/local-error facts. The Agent maps those facts to
`positive/negative/no_evidence` according to the criterion contract.

TCP, UDP, HTTP and protocol-native liveness remain future possible Driver implementations,
not current capabilities.

## 8.1. Linux probe-plane implementation evidence gate

Historical experiments constrain, but do not fully select, the Linux implementation behind
the ICMP Driver.

Reusable evidence:

- EXP-024 proved on privileged CI and Debian 13 target that a probe process can be isolated
  selectively inside the shared managed namespace by capturing process identity on OUTPUT
  and carrying it into reverse INPUT through a dedicated conntrack mark;
- EXP-024 also disproved `meta skuid` on INPUT as a usable receiving-socket discriminator
  for this purpose;
- EXP-025 proved on privileged CI and Debian 13 target that the marked conntrack entry can
  survive concrete interface-generation replacement and be inherited by a later probe that
  deliberately reuses the same tuple/ICMP identifier;
- therefore exact path/interface-generation RPDB/nft regeneration alone is insufficient to
  establish fresh probe-flow identity;
- EXP-026 proved in privileged CI that deleting only the dedicated probe conntrack class by
  mark can break that stale inheritance while preserving differently marked control state,
  but the experiment record still lacks Debian 13 target confirmation.

Consequences for implementation:

```text
if Linux ICMP Driver uses EXP-024-style conntrack-carried process identity
    ->
it must implement and verify an explicit probe-generation invalidation boundary
    ->
it must not rely only on (ifname, ifindex) replacement / nft regeneration
```

A namespace-wide conntrack flush is not accepted by this evidence.

EXP-026 mark-filtered cleanup is the current narrow remediation candidate, not yet final
target evidence. Production acceptance of that specific remediation requires either Debian
13 confirmation or an explicit review decision that the privileged-CI evidence is sufficient.

This is an implementation/evidence gate, not new user-visible availability semantics.


## 8.2. Probe network preconditions and shared lower policy boundary

**Implements:**
- `VPNG0003-R3.R6`
- `VPNG0003-R3.R6.R1`
- `VPNG0003-R3.R6.R2`
- `VPNG0004-R4.R1`
- `VPNG0004-R4.R2`
- `VPNG0004-R4.R5`
- `VPNG0007-R7.R3`
- `VPNG0007-R7.R3.R1`
- `VPNG0007-R7.R3.R2`

A path-specific availability observation is valid only when its local network preconditions
ensure that the probe is actually constrained to the intended path and cannot silently escape
through another Device or ordinary routing.

The availability side owns the semantic lifecycle/readiness of those observation
preconditions:

```text
active normalized availability channels
        ->
required probe-owner network policy
        ->
shared lower NetworkPolicyAdapter / Executor
        ->
verified probe execution precondition
        ->
physical probe attempt
```

This does not turn `AvailabilityProbeAgent` into the owner of the remote network condition.
The Agent still observes that external condition; it may use lower Machinery to prepare and
verify its local measurement environment.

Payload-policy and probe-policy desired state are distinct semantic owner scopes even when
they share the same lower Linux realization boundary.

The lower network-policy contract must therefore preserve owner identity/scope and reject or
fail closed on unsafe inter-owner conflict before physical application.

A separate physical `ProbeRulesAdapter` is not introduced merely to preserve ownership.
The shared Adapter may realize both owners as long as its semantic contract keeps them
distinct.

When no enabled observation channel requires a probe-owner policy scope, that scope is
removed through the same verified cleanup boundary rather than being left as implicit
ambient state.

# 9. NetworkPolicyAdapter

**Component type:** Adapter

**Implements:**
- `VPNG0001-R1.R1`
- `VPNG0004-R4.R2`
- `VPNG0004-R4.R3`
- `VPNG0004-R4.R5`
- `VPNG0005-R5.R2`
- `VPNG0005-R5.R3`
- `VPNG0005-R5.R4`
- `VPNG0007-R7.R3`
- `VPNG0007-R7.R3.R2`
- `VPNG0007-R7.R5`

The Adapter is the shared boundary from owner-scoped semantic network policy into the lower
network-policy domain.

Current semantic owners include at least payload policy and probe-observation policy. Sharing
the physical Adapter does not merge those owners.

Its contract must express semantic operations such as:

```text
observe current owned policy state
apply desired semantic policy and verify postcondition
cleanup owned policy and verify absence
```

The upper Manager must not know:

- route-table allocation;
- route-owner protocol identifiers;
- rule priorities;
- physical gateway/onlink representation of a bound logical path;
- nft syntax;
- sysctl syntax;
- kernel command ordering;
- transaction scratch structures.

Those details belong below the Adapter boundary unless a future product requirement makes
one observable.

### 9.1. Semantic-to-physical route-priority realization boundary

`PayloadProfileRequest` is intentionally insufficient to construct an iproute2 command by
itself.

It contains semantic policy:

```text
profile_id
direction
destinations[]
ordered logical paths[]
```

The physical pure-priority backend additionally needs lower realization data:

```text
route-key destination / internal routing domain
logical path -> current RoutePriorityPathRoute
    current endpoint identity
    gateway?
    onlink
internal table allocation
internal route-owner protocol
owned working metric space
```

These lower values are **not** derived by PayloadTrafficManager and are not added to the
human configuration merely because the Linux backend needs them.

The NetworkPolicyAdapter/lower realization layer must combine:

- the Manager's semantic Profile/path order;
- current verified path binding/transport realization;
- internal owned-resource allocation;

into the physical route-key domain requests consumed by NetworkPolicyExecutor.

A missing or ambiguous physical realization for an otherwise allowed logical path is not
permission to invent a gateway, use ambient routing, or drop that path silently. It moves
the affected lower policy out of the pure-priority path and must remain fail-closed /
unconfirmed until structural realization/reconciliation can establish the required state.

This boundary also means that current `RoutePriorityPathRoute`, table/protocol values and
metric working space are lower internal contracts/evidence, not new product knobs.

The executable lower realization contract represents that internal data as:

```text
RoutePriorityDomainRealization:
    RoutePriorityDomainId
    table
    owner_protocol
    path_routes[]
    RoutePriorityMetricSpace

RoutePriorityMetricSpace:
    preference_slots[]  # strictly increasing Linux metrics
    scratch_metrics[]   # disjoint owned working space
```

Semantic `ordered_paths` are mapped to `preference_slots` in order. Because Linux prefers
the lower route metric, the preference slots must be strictly increasing numerically.
Multi-path realization requires at least one disjoint scratch metric so a cyclic permutation
can preserve make-before-break behavior.

The contract validates the internal representation but intentionally does not choose table,
protocol or metric values. Their allocation remains a lower Adapter responsibility.

That allocation must not be designed as an isolated priority-only namespace. Table IDs,
route-owner protocol, rule priorities and metric ownership are part of the same lower
network-policy ownership layout that will also realize structural routing/RPDB/filtering
state.

Therefore the next allocator unit is gated by the structural lower-policy layout:

- it may reserve/derive internal identifiers deterministically;
- it must keep owner scopes unambiguous for observation, mutation and cleanup;
- it must prevent collisions between independent Profiles/domains and probe/payload owner
  scopes;
- it must provide enough owned metric space for the accepted make-before-break algorithm;
- it must not reuse historical NG1/NG2 constants merely because they existed;
- it must remain entirely below the human-facing configuration contract.

The existing realization types are consumers of that future allocation contract, not the
authority that chooses global Linux resource namespaces.

### 9.2. Shared lower network-policy ownership/allocation layout

**Implements:**
- `VPNG0001-R1.R1`
- `VPNG0003-R3.R6`
- `VPNG0004-R4.R1`
- `VPNG0004-R4.R1.R1`
- `VPNG0004-R4.R2`
- `VPNG0004-R4.R5`
- `VPNG0004-R4.R6.R1.R1`
- `VPNG0005-R5.R2`
- `VPNG0005-R5.R4`
- `VPNG0005-R5.R5`
- `VPNG0007-R7.R1`
- `VPNG0007-R7.R3`
- `VPNG0007-R7.R3.R1`
- `VPNG0007-R7.R3.R2`

The lower Linux policy namespace is allocated from **semantic owner scopes**, not from
user-visible identifiers copied directly into kernel object names.

Current owner kinds are:

```text
PayloadPolicyOwner(profile_id)

ProbePolicyOwner(
    availability_subject_id = (profile_id, logical_path_id)
)
```

The owner key is semantic identity. Kernel resource numbers are internal realization.

#### Routing-table ownership

Each enabled payload Profile owns one internal routing table even when its current concrete
path set is empty. Keeping the table/domain present preserves the accepted rule that a
zero-path Profile remains a fail-closed policy domain instead of disappearing into ambient
routing.

A Profile table contains the structural routes for all of that Profile's remote
destinations plus a terminal fail-closed route. Pure-priority convergence mutates only the
ordinary path-route metrics inside that already-selected table.

Probe policy does not automatically receive one table per subject merely because the owner
exists. A probe-owner table is allocated only when the accepted physical probe mechanism
needs an independent path-routing domain. This keeps owner identity explicit without
pre-allocating unused kernel machinery.

Payload and probe table allocations come from disjoint lower resource pools.

#### RPDB ownership

Payload dispatch rules are generated from the normalized `(destination, Profile)` set and
are ordered deterministically by:

```text
prefix length descending
network address ascending
Profile ID ascending only as a final deterministic tie-break
```

Exact duplicate destination ownership is already rejected by configuration normalization,
so the final tie-break does not create policy semantics.

The payload RPDB pool must execute before ambient/main lookup for managed host-boundary
traffic. Probe rules, when required by the selected probe mechanism, use a disjoint
higher-precedence owner pool and an explicit probe discriminator; they do not reuse payload
dispatch identity.

Rule priority numbers are internal allocation, not configuration.

#### Route ownership markers

Linux route protocol values are role markers, not Profile/subject identifiers.

The lower platform contract reserves distinct marker roles for:

```text
managed path/unicast route
managed terminal/guard route
```

The exact numeric protocol values are platform constants and must be evidence-gated before
production use. Historical 201/202 behavior is reusable evidence but does not by itself make
those numbers an NG3 normative choice.

Owner scope is determined by the combination of allocated table/domain, route role/shape and
semantic allocation record. A protocol marker alone is never sufficient proof that an
arbitrary route may be deleted.

#### Metric ownership

For a payload Profile with `N` currently realized paths, the lower allocation supplies:

```text
N strictly increasing preference metrics
>= 1 disjoint scratch metric when N > 1
one terminal guard metric lower in preference than every preference/scratch metric
```

Availability changes only permute which already-eligible logical path owns each preference
slot. They do not allocate a second availability-specific metric namespace.

A zero-path Profile requires no preference/scratch metrics but still retains its terminal
fail-closed route.

The allocator must reject an unrepresentable path count before mutation. It must not silently
truncate paths or reuse a guard metric as scratch space.

#### nftables ownership

Packet filtering/NAT realization uses a dedicated VPN-GATE-owned nftables namespace inside
the managed network domain.

Payload and probe policy remain separate semantic owner scopes inside that namespace even
when one physical nft table is sufficient.

The lower allocator must not embed arbitrary user IDs directly into nft object names merely
for ownership. Stable internal owner tokens/indices may be used when per-owner objects are
required.

The dedicated nft namespace is cleanup identity for VPN-GATE packet-policy objects. A
pre-existing incompatible object in that reserved namespace is a marker conflict, not a
candidate for silent adoption or deletion.

##### nft namespace ownership marker

The first-release Linux nft namespace has one fixed table identity:

```text
family: ip
table:  vpn_gate
```

Table-name reservation alone is not sufficient evidence that a pre-existing table belongs
to this product.

An owned NG3 table therefore carries one exact versioned table comment:

```text
vpn-gate:ng3:owner-v1
```

The table-level observation states are:

```text
ABSENT
    no table ip vpn_gate exists

OWNED
    exactly one table ip vpn_gate exists
    and its table comment == "vpn-gate:ng3:owner-v1"

CONFLICT
    table ip vpn_gate exists
    but the ownership marker is absent, malformed or different
```

The marker is an ownership prerequisite, not blanket deletion authority.

Even an `OWNED` table must have its contained chains/rules/sets/objects inventoried against
accepted VPN-GATE shapes before cleanup or replacement. Any unexpected contained object
remains an explicit ownership conflict rather than something to delete merely because it
sits inside the marked table.

##### Invariant payload nft scaffold

The first-release payload nft namespace has two invariant base chains whose existence and
metadata do not depend on the unresolved final external Device firewall/NAT grammar.

```text
chain payload_forward
    type filter
    hook forward
    priority 0
    policy drop
    comment "vpn-gate:ng3:payload-forward-v1"

chain payload_postrouting
    type nat
    hook postrouting
    priority 100
    policy accept
    comment "vpn-gate:ng3:payload-postrouting-v1"
```

`payload_forward` owns the final VPN-GATE verdict for IPv4 packets forwarded through the
managed network domain. Its default `drop` is structural fail-closed behavior: an empty
payload policy forwards nothing.

The newly accepted managed-stack default-policy requirements add two further filter hooks:

```text
chain stack_input
    type filter
    hook input
    priority 0
    policy drop
    comment "vpn-gate:ng3:stack-input-v1"

chain stack_output
    type filter
    hook output
    priority 0
    policy drop
    comment "vpn-gate:ng3:stack-output-v1"
```

**Implements:**
- `VPNG0004-R4.R6.R1.R5`;
- `VPNG0004-R4.R6.R1.R5.R1`.

These chains are appliance/control-plane policy, not the user's Device firewall. Required
loopback, probe, publication or integration-specific local exceptions are explicit
VPN-GATE-owned contributions. User Device rules never become arbitrary host `INPUT/OUTPUT`
rules, and these managed-domain hooks do not imply ownership of the ordinary host namespace
firewall.

EXP-040 passed on privileged Linux CI and accepts the exact
`stack_input/stack_output` owner shapes above. Empty DROP chains remained terminal despite
foreign unconditional-ACCEPT base chains before and after priority 0; explicit owned ICMP
allow rules restored the tested local traffic.

The invariant scaffold may therefore include all four accepted base chains
(`stack_input`, `payload_forward`, `stack_output`, `payload_postrouting`).
System/local allow contributions remain a separate policy unit and are not implied by the
scaffold itself.

##### Managed local/system allow policy

**Implements:**
- `VPNG0004-R4.R6.R1.R5`;
- `VPNG0004-R4.R6.R1.R5.R1`;
- `VPNG0001-R1.R2.R4.R6.R3` where a supported Device publication requires local transport traffic;
- `VPNG0001-R1.R3.C1.R1` for integration-specific local control traffic explicitly required by a supported onboarding contract.

The managed `stack_input` / `stack_output` exception layer is compiled only from explicit
VPN-GATE-owned **local/system allow intents**. It is not a second user firewall and it must
not derive permissions from Device firewall `ALLOW` rules.

A normalized contribution has this semantic shape:

```text
LocalSystemAllowIntent
    owner_function
        = loopback
        | probe
        | publication(device_id)
        | integration(integration_id)
    hook = input | output
    protocol
    current_interface_identity?
    source_prefix?
    destination_prefix?
    source_port?
    destination_port?
    peer_or_endpoint_identity?
```

Every field is a semantic selector, not raw nft syntax. A contribution is valid only when its
`owner_function` is backed by an already accepted product/integration need and every selector
required to prevent scope broadening is known. Unknown lower facts produce no wider fallback
rule.

The desired policy is the set-union of normalized contributions after canonical
deduplication. Composition does not introduce ordering semantics between independent
contributions: each contribution is a positive exception to the chain's terminal DROP.
A rule compiler may combine mechanically equivalent selectors only when packet acceptance is
provably unchanged.

The following are forbidden as implicit defaults:

- blanket `accept` in either local chain;
- blanket `ct state established,related accept` covering unrelated local traffic;
- acceptance based only on an interface name when current interface identity is required;
- publication wildcarding beyond the normalized Device publication intent;
- probe acceptance broader than the exact probe flow contract;
- copying Device firewall rules into `stack_input` or `stack_output`.

Lifecycle ownership follows the source intent. If a publication, probe path or supported
integration disappears from current desired state, its local/system contribution becomes
stale and must be removed through the same observe/compare/converge discipline as other owned
nft state. A stale contribution never remains merely because it would be harmless.

The policy Calculator therefore has a bounded responsibility:

```text
accepted current product/integration intents
    + current verified lower identities required by those intents
        -> desired LocalSystemAllowIntent set
```

The existing nft realization boundary is responsible only for compiling that desired set,
observing owned rules, classifying exact/missing/stale/conflicting state and converging to the
supplied desired state. It must not invent missing local permissions.

This unit deliberately does **not** define a universal fixed exception list. Exact loopback,
probe, publication and integration contributions are admitted only when the corresponding
already-supported function reaches its own bounded implementation unit and can provide the
necessary selectors. This keeps `INPUT=DROP` / `OUTPUT=DROP` fail-closed semantics intact
without manufacturing new product behavior.

Concrete payload rules are added only by a fully normalized payload-policy projection. They
must not be inferred from historical TOML examples.

###### EXP-035 — проверка низкоуровневого nft-контракта NEW forwarding

**Implements:**
- `VPNG0002-R2.R1.R2` — remote destination/source определяется направлением NEW flow;
- `VPNG0002-R2.R3.R3` — разрешение инициирования flow зависит от direction;
- `VPNG0002-R2.R5.R1` — most-specific Profile selection нельзя подменять произвольным порядком allow rules;
- `VPNG0001-R1.R3.R2`, `VPNG0001-R1.R3.R3` — физические ingress/egress идентичности должны быть текущими;
- `VPNG0004-R4.R1`, `VPNG0004-R4.R2`, `VPNG0004-R4.R3.R2` — неподтверждённый или ошибочный lower rule не может расширять forwarding.

**Constrained by:**
- `VPNG0002-R2.R3.C1` — первая версия не принимает многопутевой inbound/bidirectional Profile;
- `VPNG0001-R1.R2.R4.R6.C1` — не выводить незакрытую пользовательскую grammar из lower nft синтаксиса.

**Scope:** только технический эксперимент с одной разрешающей rule shape для
host-boundary -> конкретный VPN endpoint: `meta iif` и `meta oif`
по числовым ifindices, точный IPv4 destination prefix, `ct state new`
и `accept`. Проверить nft JSON и фактическое поведение в
одноразовом network namespace с закрывающей `policy drop`.

Это **не** архитектурное принятие полного payload filter policy:
правила return flow, inbound permission, пересекающиеся префиксы с
most-specific конкуренцией, Device firewall и probe isolation остаются
обязанностями отдельной normalized policy projection. Даже если
эксперимент PASS, одиночный allow pattern нельзя публиковать как
полную компиляцию Profile. Его можно использовать как проверенную
lower primitive для последующего проектирования строгого owner
classifier и композиции.

**Components / interactions:** существующий нижний Linux nft
Driver/Adapter выполняет экспериментальные команды; pure
`NftNamespaceObservation` поставляет canonical JSON. Новый runtime
Manager/Agent/Executor, state store и event contract не вводятся.
Эксперимент необходим, потому что exact numeric-ifindex filter match
с prefix и conntrack нельзя считать доказанным только на основании
EXP-033 (тот проверял postrouting masquerade).

**External environment:** GitHub Actions privileged Linux runner,
`iproute2`, `nftables`, `conntrack` и ICMP в disposable namespaces.
Сопоставление с Debian target остаётся отдельной проверкой
совместимости при необходимости, а не обязательным условием
проведения этого эксперимента.

**Simplification / evidence:** один узкий набор rule/negative controls;
проверить hit и отсутствие bypass с иного ingress, иного egress,
вне-prefix traffic и same-name-new-ifindex. Не создавать
обобщённый firewall AST, runtime parse grammar, persistent index map,
retry engine или вторую policy-classification логику.

**Gate:** до PASS эксперимента нельзя считать эту lower-rule shape
платформенно подтверждённой; даже PASS не разрешает materialization
непроверенной полной Profile permission или открытие `ForwardingGate`.

**EXP-035 result:** PASS on privileged GitHub Linux CI. Numeric current
`meta iif/oif` plus `ct state new` and exact IPv4 destination prefix
matched only the intended NEW packet. Different ingress, different egress,
outside-prefix traffic and same-name/new-ifindex replacement did not match.
Current interface operands rendered symbolically; the stale old oif rendered
as a decimal-string ifindex. This evidence accepts the lower primitive only;
full payload filter semantics remain gated as stated above.

###### EXP-036 — проверка prefix-scoped stateful return primitive

**Implements:**
- `VPNG0002-R2.R1.R2` — remote prefix сохраняет одинаковый смысл в обоих направлениях;
- `VPNG0002-R2.R3.R3` — return traffic уже разрешённого flow может обслуживаться statefully;
- `VPNG0001-R1.R3.R2`, `VPNG0001-R1.R3.R3` — обратный packet path привязан к текущей concrete interface generation;
- `VPNG0004-R4.R1`, `VPNG0004-R4.R2`, `VPNG0004-R4.R3.R2` — stale/неподтверждённый return state не должен расширять forwarding.

**Constrained by:**
- `VPNG0002-R2.R3.C1` — Release 1 inbound/bidirectional max-path constraint остаётся;
- `VPNG0001-R1.R2.R4.R6.C1` — lower nft expression не выбирает user grammar.

Для outbound NEW primitive из EXP-035 кандидат stateful reverse primitive
должен быть **prefix-scoped**, а не только `ct state established,related`:
`meta iif = current path`, `meta oif = host boundary`,
`ip saddr = тот же remote prefix`, `ct state established,related`.
Иначе retained conntrack для старого/другого remote prefix мог бы получить
широкое разрешение через тот же interface pair после structural change.

EXP-036 должен проверить реальный bidirectional ICMP flow, отсутствие
разрешения для unsolicited reverse NEW, отсутствие return для remote source
вне prefix даже при отдельно разрешённом outbound NEW test packet, и
same-name/new-ifindex replacement. После замены новый outbound NEW rule
может быть создан для нового oif, но старый reverse rule по old iif не
должен пропустить reply; новый reverse rule должен восстановить flow.

Это по-прежнему **lower primitive evidence**, а не полный filter compiler:
inbound NEW, Device firewall composition, multi-Profile canonical projection
и full owner convergence остаются отдельными units.

**EXP-036 result:** PASS on privileged GitHub Linux CI. The prefix-scoped
reverse rule admitted a real established reply, rejected unsolicited reverse
NEW and an established reply whose remote source was outside the prefix, and
failed closed after same-name interface replacement until a current-ifindex
reverse rule was installed. Actual nft JSON renders the state set as
`["established","related"]`; live/stale interface rendering follows the
same symbolic/decimal-index rule established by EXP-033/035.

###### Authoritative payload_forward observation — design gate

**Component:** read-only direct Calculator over the owned nft table and one fresh,
unambiguous interface inventory.

**Implements:**
- `VPNG0002-R2.R1.R2`;
- `VPNG0002-R2.R3.R3`;
- `VPNG0002-R2.R5.R1`;
- `VPNG0001-R1.R3.R2`;
- `VPNG0001-R1.R3.R3`;
- `VPNG0004-R4.R1`;
- `VPNG0004-R4.R2`;
- `VPNG0004-R4.R5`.

**Constrained by:**
- `VPNG0002-R2.R3.C1`;
- `VPNG0001-R1.R2.R4.R6.C1`.

The observer does **not** compile Profile policy. It only classifies exact
lower rule shapes already proven by EXP-035/036 and preserves the semantic
fields required for a later desired-state comparison:

```text
NEW:
    ct state new
    exact iif
    exact oif
    one remote IPv4 prefix match (saddr or daddr)
    accept
    exact NEW owner comment

RETURN:
    ct state { established, related }
    exact iif
    exact oif
    one remote IPv4 prefix match (saddr or daddr)
    accept
    exact RETURN owner comment
```

Counters used by EXP-035/036 are instrumentation, not required policy.
The production owner shape therefore omits `counter`; accepting arbitrary
counter-bearing rules as production-owned would widen cleanup authority for
no accepted requirement.

Before implementation, EXP-037 must resolve two representation facts:
how nft JSON renders `/32` `ip saddr/daddr` matches, and the exact
no-counter expression arrays. The observer may normalize only evidence-backed
forms. Unknown comment, state set, prefix representation, extra expression,
action or field is an explicit conflict, never silently ignored.

Interface operands follow EXP-033/035/036: current names resolve through the
fresh inventory; decimal ifindices may resolve to a current identity only when
that exact index is present, otherwise remain stale numeric identity.
A same-name replacement never equals the old numeric generation.

**Scenario:** strict owner inventory must be able to distinguish current
recognized payload forwarding objects from stale recognized objects and
unknown/conflicting rules before any structural cleanup or activation.

**Necessity / simplification:** a pure Calculator is required because the
scaffold currently leaves all rules unclassified. No compiler, mutation,
policy ordering, handle cache, event owner, retry loop or firewall AST is
introduced. Rule handles identify observed objects only.

**Evidence plan:** EXP-037 for final no-counter JSON forms and `/32`;
rootless parser regression for NEW/RETURN, saddr/daddr, current/stale
interfaces, malformed state/prefix/comment/action/extra expressions,
duplicate handles and duplicate physical rules; privileged integration reads
the actual EXP-037 rules through the production observer.

**Gate:** EXP-037 is PASS. Implementation of the strict read-only observer is
therefore allowed. Passing the observer unit still does not authorize full
Profile filter materialization.

**EXP-037 evidence:** no-counter NEW/RETURN owner rules contain exactly five
expressions. `/32` remote matches render as a plain IPv4 address string;
non-host prefixes such as the tested `/24` render as a prefix object.
The observer accepts only these evidence-backed canonical forms.

**Gate amendment after EXP-037:** `VPNG0002-R2.R1.R1` permits arbitrary
strict IPv4 CIDR destinations, including `0.0.0.0/0`. EXP-037 closed only
`/32`; EXP-035/036 closed `/24`. Before implementation the observer gate
must additionally resolve nft canonicalization for `/0` and boundary
prefix lengths. EXP-038 is therefore required. If nft optimizes `/0`
by removing the payload-prefix expression, the observer design must be revised
rather than pretending the missing expression is equivalent by assumption.

**EXP-038 result:** PASS on privileged GitHub Linux CI. `/0`, `/1` and

###### Exact payload_forward desired data and actual-vs-desired comparison

**Component:** immutable lower desired data + pure Direct Calculator. This is
**not** the Profile/Device policy compiler.

**Implements:**
- `VPNG0002-R2.R1.R1`;
- `VPNG0002-R2.R1.R2`;
- `VPNG0002-R2.R3.R3`;
- `VPNG0002-R2.R5.R1`;
- `VPNG0001-R1.R3.R2`;
- `VPNG0001-R1.R3.R3`;
- `VPNG0004-R4.R1`;
- `VPNG0004-R4.R2`;
- `VPNG0004-R4.R5`.

**Constrained by:**
- `VPNG0002-R2.R3.C1`;
- `VPNG0001-R1.R2.R4.R6.C1`.

The higher semantic Calculator eventually composes Profile direction/destinations, path
bindings, most-specific Profile selection and the later accepted ordered Device firewall.
This historical lower unit predates that complete composition and therefore remains only the
exact positive Profile NEW/RETURN physical-rule sub-contract; it must not be described as the
complete Device firewall compiler.

This unit defines only one exact physical desired rule:

```text
PayloadForwardRuleSpec:
    kind = NEW | RETURN
    ingress = current InterfaceIdentity
    egress = current InterfaceIdentity
    remote_field = saddr | daddr
    remote_prefix = strict IPv4Network
```

and an immutable `PayloadForwardDesiredState` containing a physically unique
set of such specs. It has no Profile ID, Device ID or rule handle because those
are not part of physical nft rule identity. Semantic provenance remains above
this lower contract.

The comparator takes:

```text
strict observed payload_forward rules
+ one fresh interface inventory
+ exact lower desired state
    ->
confirmed desired specs
missing desired specs
stale recognized physical rules
conflicts
```

A recognized current-identity rule that is not in desired state is `stale`,
not confirmed. A stale-interface-generation rule is also `stale`. Any
observer conflict remains a conflict. Desired rules whose endpoints are not
present in the same current interface inventory are invalid input rather than
permission to add a rule to an unverified endpoint.

**Necessity / simplification:** this comparison is required before safe cleanup
or physical materialization, but it deliberately avoids creating a second
Profile classifier or pretending to represent the later ordered Device firewall semantics. No I/O, mutation,
stored handles, retry state or lifecycle component.

**Evidence:** rootless exact comparison tests over NEW/RETURN, duplicate desired
physical rules, unexpected recognized current rules, stale numeric generations,
missing rules, conflicts and non-current desired endpoints. Existing live
observer evidence remains sufficient; no new kernel fact is introduced.

**Gate:** PASS for lower desired data/comparison only. Full semantic compilation
and physical filter mutation remain separate gated units.

###### Forward semantic compiler — next-unit design constraint

**Implements:** `VPNG0002-R2.R1.R2`, `VPNG0002-R2.R3.R3`,
`VPNG0002-R2.R5.R1`, `VPNG0001-R1.R2.R4.R6.R2`,
`VPNG0004-R4.R1`, `VPNG0004-R4.R3.R2`.

A naive union of Profile CIDR allow rules is not equivalent to accepted
most-specific classification. Example: a broad outbound Profile may allow
path B while a more-specific outbound Profile owning the packet allows only
path A. If the broad rule remains `daddr broad + oif B -> accept`, routing
drift or a mixed transition could forward the more-specific packet through B,
even though the selected Profile forbids that path.

The positive-only/default-drop lower model therefore requires the semantic
compiler to produce **disjoint effective remote-prefix fragments** before
creating physical allow rules:

- outbound: partition remote IPv4 space across all outbound/bidirectional
  candidate Profiles by the accepted global most-specific rule, then attach
  only the selected Profile's allowed paths to each fragment;
- inbound: for each concrete ingress logical path, first restrict candidates
  to inbound/bidirectional Profiles allowing that path, then partition remote
  source space by most-specific Profile for that path;
- return rules use the same selected fragments with reversed interface roles
  and the reverse remote field.

With disjoint fragments, all lower rules remain positive accepts under the
default-drop chain and rule order stays semantically irrelevant, matching the
accepted unordered `PayloadForwardDesiredState`.

**Ordered Device firewall composition — accepted semantic architecture**

**Implements:**
- `VPNG0001-R1.R2.R4.R6.R2`;
- `VPNG0001-R1.R2.R4.R6.R2.R1`;
- `VPNG0001-R1.R2.R4.R6.R2.R2`;
- `VPNG0001-R1.R2.R4.R6.R2.R3`;
- `VPNG0001-R1.R2.R4.R6.R2.R4`;
- `VPNG0001-R1.R2.R4.R6.R2.R5`.

**Constrained by:**
- `VPNG0001-R1.R2.R4.R6.C1`;
- `VPNG0001-R1.R2.R4.R6.R2.R5.C1`.

The positive-only Profile partition remains the **hard Profile permission gate**, but it is
no longer the whole Device firewall. The accepted composition is:

```text
packet on exact managed host-boundary <-> current Device path pair
        |
        v
ordered Device firewall chain
        |
        +-- DENY   -> drop
        +-- REJECT -> active reject
        +-- ALLOW  -> return to Profile gate
        |
        +-- explicit-policy no match -> drop
        +-- omitted-policy default   -> return
        |
        v
Profile NEW/RETURN hard gate
        |
        +-- permitted -> accept
        +-- otherwise -> payload_forward policy drop
```

This order is required because Device `ALLOW` is only permission to continue to the
generated Profile guard; it is **not** an nft `accept` that can widen Profile permission.
Conversely, Device `DENY/REJECT` is terminal and can narrow traffic that Profile would
otherwise permit.

Linux/nftables performs packet-by-packet ordered evaluation. VPN-GATE only validates,
normalizes, compiles, orders and converges the rules.

User order is semantic inside the Device chain. A broad early rule remains broad; the
compiler must not reorder a later specific rule ahead of it. Direction is compiled relative
to the exact current path binding:

```text
OUT: iif = current host boundary, oif = current Device path
IN:  iif = current Device path,   oif = current host boundary
```

Source/destination address and port predicates match literal payload packet fields at this
FORWARD point. The existing Device `MASQUERADE` contract runs later in postrouting, so
outbound source fields are still pre-NAT here. External VPN transport addresses are not
payload source/destination fields.

The Device chain is traversed before both Profile NEW admission and the prefix-scoped
ESTABLISHED/RELATED return primitive. Therefore an explicit Device firewall applies to
actual packets in both directions and can terminate an already established flow; there is
no implicit Device-layer established-flow bypass ahead of user rules. Profile statefulness
still determines whether a returned flow is in Profile permission after Device `ALLOW`.

Omitted Device firewall configuration is normalized to the semantic equivalent of
unrestricted `IN ALLOW any` plus `OUT ALLOW any`. An explicit non-empty policy has a
terminal no-match `drop`. Exact external TOML punctuation/spelling remains deferred by
`VPNG0001-R1.R2.R4.R6.C1`.

The current `PayloadForwardRuleSpec` and strict observer remain valid evidence/data for the
positive Profile NEW/RETURN sub-contract only. They are no longer a complete representation
of final `payload_forward` ownership once Device jump/ordered chains are materialized.
A later lower-policy unit must extend owner observation/desired state for jump, return,
drop/reject and ordered child-chain objects before physical Device firewall mutation is
authorized.

Endpoint-scoped Device rules are a future extension. They must resolve a configured logical
endpoint through confirmed transport provenance to the exact current binding; runtime
ifnames are not user-facing selectors. Under
`VPNG0001-R1.R2.R4.R6.R2.R5.C1`, this does not block ordinary Release-1 Device firewall
rules.

###### Device firewall lower structural ownership

EXP-041 proves the lower nft control-flow primitives required by the accepted composition:

- `payload_forward` may jump to one ordinary owned child chain for the exact current
  host-boundary/path pair;
- Device `ALLOW` is represented by child-chain `return`, so evaluation continues to the
  later Profile hard gate rather than accepting directly;
- Device `DENY` may terminate with `drop`;
- explicit-policy no-match is represented by a final terminal child `drop`;
- nft preserves the physical order of child rules;
- a `reject` action is structurally observable, while its final normalized
  protocol-appropriate realization remains separately gated.

The lower owner markers accepted for this structural layer are:

```text
child chain:   vpn-gate:ng3:device-fw-child-v1
base jump:     vpn-gate:ng3:device-fw-jump-v1
explicit rule: vpn-gate:ng3:device-fw-rule-v1
fallthrough:   vpn-gate:ng3:device-fw-fallthrough-v1
```

The generic nft namespace inventory preserves each contained object's physical
`source_order` in addition to canonical JSON. Existing unordered consumers may continue to
canonicalize locally; ordered Device firewall observation must use the preserved physical
order.

The structural observer recognizes:

- owned ordinary child-chain shape;
- exact current/stale interface identity for Device jumps;
- ordered explicit child rules whose final action is `return`, `drop` or `reject`;
- exactly positioned terminal fallthrough `drop`;
- conflicts such as a jump to a non-owned child chain, wrong owner markers, unsupported
  rule actions or fallthrough before later rules.

This is **structural ownership evidence only**. Match predicates are retained as canonical
JSON and are not yet promoted into normalized Device-firewall semantics. Therefore this
observer is not by itself authority to delete/rewrite arbitrary recognized rules, and it
does not close the separate protocol/port-predicate or final REJECT realization gates.

###### Device firewall normalized intent and exact lower desired comparison

The internal semantic model now represents an optional Device firewall independently of its
external grammar:

```text
DeviceFirewallPolicyIntent
    device_id
    rules = omitted | ordered non-empty rules

DeviceFirewallRuleIntent
    direction = IN | OUT
    action = ALLOW | DENY | REJECT
    protocol?
    source_port?
    destination_port?
    source_ipv4_cidr?
    destination_ipv4_cidr?
    comment?
```

Omitted policy remains distinct from an explicit policy. An explicit policy is non-empty and
preserves literal rule order. The model validates only already accepted field semantics and
basic type/range invariants; it deliberately does not select the external spelling or the
final accepted protocol vocabulary.

A separate exact lower desired contract represents one owned child chain plus its exact
host/path jump and ordered physical rules. Predicate expressions and final nft actions are
canonical JSON at this boundary. The desired layer therefore records already-compiled lower
facts but does not compile semantic predicates itself.

`compare_device_firewall` compares:

- exact current ingress/egress identities;
- exact opaque lower child-chain identifier supplied by the caller;
- exact ordered rule sequence;
- exact predicate-expression JSON;
- exact lower action JSON;
- terminal-fallthrough position;
- stale extra owned chains/jumps;
- structural conflicts from the read-only observer.

A mismatch in rule order is a desired-state mismatch even when the same rule set is present.

The lower contract intentionally does not derive a production child-chain naming scheme.
Naming remains an input to the lower realization layer until the semantic compiler unit
selects a deterministic lower identifier. The comparison layer grants no mutation authority.

This closes the normalized-intent / exact-lower-comparison unit while leaving the next
semantic compiler gate explicit: converting accepted internal Device-firewall fields into
proven nft predicate expressions requires its own lower evidence and review, especially for
protocol/port predicates and final REJECT realization.

No deny-rule ordering or nft jump graph is introduced merely to solve Profile prefix
overlap; the already accepted canonical CIDR partition remains the simpler Profile-gate
mechanism. Ordered chains exist because user-authored Device firewall order is now itself an
accepted product semantic.

###### Profile most-specific CIDR partition Calculator

**Component type:** pure Direct Calculator. This is Profile classification
in bulk form, **not** final effective permission and not nft compilation.

**Implements:**
- `VPNG0002-R2.R1.R2`;
- `VPNG0002-R2.R3.R3`;
- `VPNG0002-R2.R5.R1`;
- `VPNG0004-R4.R1`.

Input is the existing set of `PayloadProfileRequest` objects and, for inbound
partitioning, one concrete `LogicalPathId`. Output is a canonical set of
disjoint `(profile_id, remote_prefix_fragment)` entries.

Outbound partition considers only outbound/bidirectional Profiles and applies
the same global most-specific selection as `classify_outbound_profile`.
Inbound partition first restricts to inbound/bidirectional Profiles containing
the supplied ingress path, then applies the same most-specific selection as
`classify_inbound_profile`.

A broader Profile fragment is split by every more-specific prefix owned by a
different candidate Profile. Nested prefixes belonging to the same Profile are
semantically redundant for selection and may collapse. Exact same prefix
owned by different candidate Profiles is an error, never arbitrary order.

The partition is **Profile permission only**. Ordered Device firewall composition,
path-specific lower rules and protocol/port restrictions are downstream
responsibilities. An envelope can narrow fragments but cannot use this
Calculator to expand Profile permission.

**Necessity:** positive-only nft rules must not rely on rule ordering or
routing correctness to reproduce most-specific Profile selection. A disjoint
partition provides an independently testable semantic basis for later lower
rule generation.

**Simplification:** use standard strict IPv4 CIDR subtraction/collapse only.
No ACL AST, decision tree runtime, persistent prefix trie, rule ordering,
network I/O or mutation.

**Evidence:** rootless tests compare partition ownership against the existing
point classifiers over every address in bounded test networks, including
nested prefixes, default route, same-Profile redundancy and path-relative
inbound selection.




`/31` remain explicit prefix objects; `/32` is a plain IPv4 address string.
The same forms are used by NEW daddr and RETURN saddr matches. The strict
observer implementation gate is therefore open for all accepted IPv4 CIDR
prefix lengths.





`payload_postrouting` exists as the stable owner boundary for supported payload source-NAT
realization. It is valid and intentionally empty when no accepted Device/path requires NAT.
Its base-chain policy is `accept`; the presence of the chain alone never creates NAT.

The two chain comments are lower schema/version markers. A same-name chain with missing or
different marker, hook, type, priority or policy is an ownership/shape conflict.

##### Payload source-NAT lower contract

The internal normalized NAT semantic is already fixed independently of its final external
TOML spelling:

```text
NatIntent.NONE
NatIntent.MASQUERADE
```

For one current logical path owned by a Device:

```text
NONE
    -> no VPN-GATE payload NAT contribution for that path

MASQUERADE
    -> one postrouting masquerade contribution for payload
       entering from the managed ordinary/host boundary
       and leaving through that path's current concrete endpoint
```

The physical match must bind to the exact current interface identities, not merely reusable
interface names.

The intended Linux/nft match is therefore based on numeric current interface indices:

```text
meta iif == host_boundary.ifindex
meta oif == path_endpoint.ifindex
masquerade
```

A same-name/new-ifindex endpoint must not inherit a stale NAT contribution before the new
binding is accepted and structural policy is rebuilt.

The NAT contribution intentionally does not repeat Profile destination prefixes.

Reason:

1. `payload_forward` is evaluated before postrouting and owns payload permission;
2. only traffic already admitted by the complete forwarding policy can reach the NAT action;
3. one Device/path may be shared by multiple Profiles;
4. duplicating destinations into NAT would create a second policy-classification surface
   with no requirement benefit.

The host-boundary ingress match also keeps locally generated probe/control traffic out of
payload NAT.

NAT intent is structural and availability-independent. Availability may reorder eligible
paths but cannot create/remove a Device NAT contribution.

If several Profiles share the same current path, their identical NAT contribution is
deduplicated by the exact `(host boundary identity, path endpoint identity)` pair.

This lower contract does not choose the final human-facing `nat` field spelling. It consumes
an already normalized semantic intent.

EXP-033 passed on the current Linux/nftables target.

The rule was created with numeric interface indices and behaved as exact ifindex identity.
Current nft JSON representation is intentionally normalized as follows:

- while the stored ifindex resolves to a current interface, the operand is rendered as that
  interface name even with `nft -n -j list ruleset`;
- after the interface disappears, the same stored operand is rendered as a decimal-string
  ifindex;
- recreating the same interface name with a new ifindex does not make the stale rule match.

Therefore authoritative NAT observation must normalize an nft meta-interface operand using a
fresh current interface inventory:

```text
textual ifname
    -> current InterfaceIdentity(ifname, ifindex)

decimal-string operand
    -> unresolved/stale numeric ifindex unless that exact index is independently present
```

It must never compare only textual interface names.

EXP-033 also proved real source translation, ingress scoping and same-name replacement
behavior. The exact nft rule comment is `vpn-gate:ng3:payload-nat-v1`; the rule handle is
incidental.

###### Authoritative payload NAT rule observation

**Component:** read-only direct Calculator for normalized nft observation/comparison.

**Implements:**
- `VPNG0001-R1.R2.R4.R6.R1` — explicit Device NAT intent projected onto an exact current path;
- `VPNG0001-R1.R3.R2` — unambiguous current physical endpoint binding;
- `VPNG0001-R1.R3.R3` — replaced endpoint must not inherit old interface identity;
- `VPNG0004-R4.R3.R2` — structural NAT changes may not bypass a restrictive transition;
- `VPNG0004-R4.R4` — unconfirmed network state cannot authorize forwarding;
- `VPNG0004-R4.R5` — authoritative actual state is required after uncertainty.

**Constrained by:**
- `VPNG0001-R1.R2.R4.R6.C1` — lower NAT observation does not assume an unaccepted human-facing configuration grammar.

**Scenario and responsibility:** After an external Device endpoint disappears or is recreated
with the same name, the product must distinguish the old physical NAT rule from the new
desired path binding before any structural reconciliation. An existing read-only nft
Adapter supplies canonical objects in the owned table; a fresh interface inventory
supplies current `(ifname, ifindex)` identities. The direct Calculator classifies the
owned NAT chain and compares recognized physical rules against already normalized
`PayloadNatDesiredState`, returning confirmed/missing/stale/conflict without mutation.

**Interactions and external environment:** The Calculator has synchronous, explicit
inputs and no kernel I/O, timer, retained history or event ownership. The Adapter's
table ownership and invariant scaffold checks must pass before using its output.
The only external facts are the observed nft JSON representation and fresh Linux link
identity. EXP-033 supplies the platform evidence for name/decimal-index renderings.

**Necessity and simplification:** Exact physical rule classification is required before
deleting or replacing any owned NAT object; desired-state projection alone cannot prove
actual current state. One pure Calculator is sufficient: no additional Agent, cache,
async event/retry flow, second NAT routing policy, or persistent interface history is
introduced.

**Constraints and lifting:** A conflict, invalid/stale endpoint or incomplete ownership
classification cannot be turned into permission to forward or delete state. The observer
changes no user-visible NAT capability and imposes no new product restriction; only
future physical NAT mutation remains gated behind the structural `ForwardingGate`.

**Evidence plan:** Rootless tests cover strict whole-chain recognition, current and
stale ifindices, same-name replacement, unexpected owned expressions/comments, duplicate
rules, missing desired state and invalid/ambiguous inventory; existing EXP-033 establishes
real nft/kernel representation. Run NG3 Python CI on the actual reviewed branch,
perform expert review against this architecture, and record dispositions before accepting
this review unit.

The strict NAT observer operates only after table/scaffold ownership is confirmed and consumes:

```text
canonical nft objects from table ip vpn_gate
+
one fresh current InterfaceIdentity inventory
```

Every rule in `payload_postrouting` is inside VPN-GATE's owned policy boundary and must be
classified. It is not safe to ignore a rule merely because its comment is unfamiliar.

The only currently accepted payload NAT rule shape is:

```text
chain = payload_postrouting
comment = "vpn-gate:ng3:payload-nat-v1"

expr[0]:
    meta iif == <interface operand>

expr[1]:
    meta oif == <interface operand>

expr[2]:
    masquerade

no additional semantic expressions
```

Rule `handle` is retained as exact current kernel-object identity for a later mutation
planner, but it is not semantic desired-state identity.

Interface operands normalize as follows:

```text
ifname string:
    resolve through fresh current interface inventory
    -> current InterfaceIdentity

decimal-string ifindex:
    if exact current ifindex exists, resolve to that InterfaceIdentity
    otherwise retain as stale/unresolved numeric interface identity

other textual/numeric form:
    conflict
```

A stale/unresolved numeric identity never confirms a desired current
`PayloadMasqueradeSpec`.

The observer must report an explicit conflict for:

- missing/wrong NAT owner comment;
- wrong chain/table/family;
- missing or repeated iif/oif match;
- name/index operand that cannot be normalized unambiguously;
- any extra match/action/expression;
- NAT action other than plain masquerade;
- duplicate normalized physical NAT rule.

Thus actual-vs-desired comparison can classify:

```text
confirmed desired masquerade contribution
missing desired contribution
stale recognized owned contribution
conflicting/unrepresentable owned NAT rule
```

and can do so without equating same-name/new-ifindex endpoints.

Observation remains read-only. Physical NAT add/delete is not accepted until this parser and
comparison contract are executable and reviewed.

EXP-034 has subsequently proved on the selected GitHub Linux/nft target that a recognized
stale NAT rule can be deleted by its observed handle after same-name interface replacement,
without deleting the new current rule. A nonexistent handle delete fails without changing
the observed nft objects. This is **technical evidence only**, not authority for production
mutation: full owned-scope classification, an independently confirmed disabled
`ForwardingGate`, fresh pre/post-observation, and guarded structural convergence remain
necessary before any runtime NAT write path is accepted.

###### Guarded NAT-only structural mutation reference slice

**Component type:** a bounded direct `NetworkPolicyExecutor` operation with a lower
Linux nft Driver and the existing read-only Calculator. This is deliberately a
partial reference slice, **not** completion of full Release 1 structural policy.

**Implements:**
- `VPNG0001-R1.R2.R4.R6.R1`;
- `VPNG0001-R1.R3.R2`;
- `VPNG0001-R1.R3.R3`;
- `VPNG0004-R4.R3.R2`;
- `VPNG0004-R4.R4`;
- `VPNG0004-R4.R5`.

**Constrained by:**
- `VPNG0001-R1.R2.R4.R6.C1` — no guessed external NAT grammar.

**Scenario:** One recognized old exact-ifindex NAT rule remains in the marked
payload postrouting chain after a Device endpoint was replaced. The required
current physical NAT desired state may need stale rule deletion and new rule
addition, but no packet may forward during the mixed transition.

**Responsibilities and interactions:** The direct Executor first converges the
owned managed-netns `ForwardingGate` to `DISABLED` and confirms a fresh read.
An injected lower Driver obtains one nft ruleset observation bracketed by two
fresh link inventories; relevant current `(ifname, ifindex)` identities must
agree. Existing pure observers confirm the table/scaffold and classify every
rule in `payload_postrouting` against the supplied normalized desired state.
The Executor must additionally account for **every other object** in the owned
nft table; this bounded slice explicitly refuses mutation if there is any
unsupported object or a rule in `payload_forward`. This refusal is a missing
reference capability, not a new product-level constraint. The eventual complete
structural Executor must combine the independently reviewed forward/probe and
NAT classifications rather than silently narrowing supported payload traffic.

**One-step mutation / postconditions:** With no conflicts and exact current
desired endpoint identity, choose one deterministic recognized stale handle for
deletion, or one missing desired current exact-ifindex masquerade for addition.
Recheck `ForwardingGate == DISABLED` immediately before each write. After
each write, obtain a fresh bounded structural snapshot and prove the expected
**whole-chain change**: delete removed exactly that handle and preserved all
other rules, or add introduced exactly one recognized desired physical NAT
rule with a fresh handle while preserving all previous rules. A successful
nft command is not an independently confirmed postcondition.

**Failure recovery:** A thrown/failed lower command cannot authorize replay
of a stale plan. Reobserve the owned scope and gate; report the authoritative
current result or an unconfirmed failure. Do not open forwarding, silently
delete a conflict, adopt a same-name replacement, or keep an old handle as a
persistent desired-state identity. A later retry must plan from fresh state.
All VPN-GATE structural writes to this owned namespace must be serialized;
unrecognized concurrent external changes cause a fail-closed refusal.

**External evidence and necessity:** EXP-033 validates numeric-ifindex rule
realization and stale interface representation; EXP-034 validates exact-handle
old-rule deletion and failure isolation on the selected Linux/nft target.
A physical Driver is necessary for actual kernel actuation; the existing
read-only Calculator is reused for all classification. No second policy
classifier, background Agent, retry queue, stored handle registry, async
completion protocol or new user configuration is introduced.

**Scope / constraint lifting:** Since this reference slice permits only an
empty forward chain and no other unknown table objects, it is safe but
**not sufficient for the production case with materialized forward/probe
rules**. No acceptance of first-release product scope reduction follows.
The complete structural Executor remains separately gated on composition
with the full nft owner classifiers, RPDB/routes and final forwarding
activation.

**Evidence plan:** rootless fake Driver/Gate tests for lost barrier,
unknown nft objects, stale/duplicate/conflicting NAT, exact single-step
postconditions and failed command re-observation; a disposable-netns
physical backend integration for real add/delete with `ip_forward=0`.
Only after independent expert review may this partial lower slice be
considered executable reference evidence. It must never reopen the root
forwarding barrier.

##### Ordinary-side Profile gateway NAT boundary

**Implements:**
- `VPNG0001-R1.R2.R4.R4.R4`;
- `VPNG0001-R1.R2.R4.R4.R4.R1`;
- `VPNG0004-R4.R6.R1.R6`;
- `VPNG0004-R4.R6.R1.R6.R1`.

**Constrained by:**
- `VPNG0001-R1.R2.R4.R4.R4.C1`.

This is a second source-NAT purpose and must not be conflated with Device
`NatIntent.MASQUERADE`.

```text
Device VPN-side NAT
    ordinary -> managed firewall -> Device/path postrouting masquerade -> VPN

Profile ordinary-side gateway NAT
    VPN -> managed Device/Profile firewall -> explicit host boundary
        -> host forwarding toward ordinary network
        -> optional Profile-scoped gateway source NAT
```

The first exists to make ordinary-originated traffic usable through a VPN path. The second
exists only when an ordinary-network next hop needs replies to return through the VPN-GATE
host without being taught routes to remote VPN prefixes.

A packet whose destination is the VPN-GATE host itself is locally delivered on the host side
and does not require the gateway-forwarding NAT contribution. The semantic intent therefore
does not mean "SNAT every inbound VPN packet"; it means "SNAT the already-permitted
VPN-originated packet when the host forwards it onward through the owned ordinary-side
gateway boundary".

The normalized upper intent is conceptually:

```text
ProfileGatewayNatIntent:
    profile_id
    mode = NONE | MASQUERADE
```

This type name is architectural shorthand, not accepted external configuration syntax.

The Device/Profile firewall runs before the packet leaves the managed network domain.
Consequently source address/port filtering still sees the original remote payload sender.
Ordinary-side gateway NAT must never be moved ahead of that managed policy boundary.

###### Profile association across the host boundary

Per-Profile gateway NAT cannot safely reclassify packets on the host merely by remote source
prefix.

Inbound Profile classification is path-relative:

```text
actual ingress logical path
    +
remote source prefix
    ->
selected Profile
```

Two Profiles may therefore overlap in remote prefix space while being unambiguous because
they admit different ingress paths. Once several managed paths converge on one ordinary host
boundary, source CIDR alone no longer carries that provenance.

The lower boundary must consequently preserve a verifiable association:

```text
selected Profile inside managed policy
        +
packet crossing explicit host boundary
        ->
BoundaryProfileAssociation(profile_id, packet/flow)
        ->
ProfileGatewayNatOwner(profile_id)
```

`BoundaryProfileAssociation` is a semantic lower contract, not a selection of Linux
mechanism. A reserved packet mark, a distinct boundary resource, conntrack metadata or
another mechanism may be accepted later only after evidence proves that it preserves the
already-selected Profile without colliding with routing/probe/host policy.

The host-side NAT implementation must not infer the Profile from:

- source CIDR alone;
- boundary ifname alone when the boundary is shared;
- current VPN ifname that is no longer present in the host-side packet path;
- Device identity without the Profile classification result.

If the exact current packet/flow association cannot be confirmed, that Profile's gateway NAT
is unready and must not be applied.

###### Ownership and component boundary

The semantic owner remains the existing payload/Profile policy owner. No new long-lived
Manager is introduced.

The existing `NetworkPolicyAdapter` gains a **separate host-boundary lower realization
sub-contract** because this mutable state is outside the managed network namespace:

```text
observe ProfileGatewayNatOwner(profile_id)
apply desired Profile gateway NAT + verify
cleanup owned Profile gateway NAT + verify absence
```

This host-boundary owner scope is disjoint from the managed-domain
`table ip vpn_gate` owner scope. It may mutate only explicitly reserved boundary objects
required for the selected Profile gateway NAT and must treat unrelated host firewall/routing
state as foreign.

The exact host-side nft table/chain identity, packet-association carrier and command ordering
remain implementation/evidence decisions. They are not user-facing knobs.

A structural transition that changes Profile gateway NAT or its boundary association is not
eligible for the pure route-priority fast path. The affected forwarding must remain
restrictive until managed policy, association and host-boundary NAT postconditions are all
freshly verified.

###### Return path and failure semantics

For a forwarded VPN-originated packet, successful ordinary-side source NAT makes the
ordinary-network destination reply to the VPN-GATE host gateway address. Normal conntrack
reverse NAT then restores the remote destination on the reply before routing it back toward
the explicit managed boundary.

This capability does not replace the existing requirement that traffic for managed remote
prefixes be routed into the VPN-GATE boundary. It only avoids requiring each downstream
ordinary host to know those remote routes.

Failure or ambiguity in host-side NAT observation, owner classification or Profile
association cannot be treated as "NAT probably active". The Profile gateway-NAT function is
reported unconfirmed/unready and no new boundary NAT permission is activated from guessed
state.

**Simplification:** no universal host-firewall Manager, per-packet userspace proxy, endpoint
provisioning service, durable association journal or guessed host-route editor is introduced.

**Evidence gate:** before physical implementation, a bounded experiment must prove the
selected Linux mechanism for carrying the already-selected Profile association across the
namespace/boundary and for applying/reversing host-side masquerade without affecting
unrelated host traffic. The experiment must include overlapping remote prefixes on distinct
ingress paths so that source-prefix-only reclassification would fail, plus host-local traffic
that must not receive gateway NAT.

The scaffold is deliberately independent from the root structural barrier:

- structural rebuild happens while verified `ip_forward=0`;
- the scaffold may then be created/repaired and verified;
- final allow/NAT rules are materialized behind the still-closed root barrier;
- RPDB activation and full route+nft verification still occur before re-enabling forwarding.

A foreign nft base chain outside `table ip vpn_gate` is not adopted or deleted by this
scaffold. For safety, the payload forward chain must still prevent a foreign unconditional
`accept` chain at another priority from bypassing its default drop.

EXP-032 passed on the current Linux/nftables target.

The accepted JSON metadata is:

```json
{"comment":"vpn-gate:ng3:payload-forward-v1","family":"ip","handle":1,"hook":"forward","name":"payload_forward","policy":"drop","prio":0,"table":"vpn_gate","type":"filter"}

{"comment":"vpn-gate:ng3:payload-postrouting-v1","family":"ip","handle":2,"hook":"postrouting","name":"payload_postrouting","policy":"accept","prio":100,"table":"vpn_gate","type":"nat"}
```

Handles are incidental and excluded from scaffold identity.

The live packet test also proved:

- an empty `payload_forward policy drop` blocks transit;
- foreign unconditional-accept base chains at priorities `-100` and `100` do not bypass
  that drop;
- explicit allow rules inside `payload_forward` can permit the tested path;
- the empty `payload_postrouting` chain contains no NAT rule.

Observation uses full JSON ruleset inventory rather than treating a failed
`list table` command as proof of absence:

```text
nft -j list ruleset
```

This keeps:

- valid table absence;
- malformed/unsupported owned-table shape;
- command/JSON observation failure;

as distinct states.

The marker is lower implementation state. It is not user configuration and does not encode a
Profile/Device ID.

EXP-031 passed against the current nftables target.

The marked table is currently observed as:

```json
{"comment":"vpn-gate:ng3:owner-v1","family":"ip","handle":2,"name":"vpn_gate"}
```

and an unmarked same-name table as:

```json
{"family":"ip","handle":3,"name":"vpn_gate"}
```

The numeric handle is incidental kernel identity and is not part of the ownership marker.

The executable observer must therefore compare `family`, `name` and exact `comment`,
while retaining contained objects separately for later strict shape classification.

#### Deterministic allocation and configuration change

Allocation is deterministic for one accepted semantic owner set.

A minimal implementation may rank canonical owner keys and assign the next available entry
from an ordered platform resource pool. Persistent hash maps or durable allocation journals
are not required merely to preserve numeric IDs across a configuration change.

No product requirement promises stable table/rule/metric numbers across a structural
configuration transition.

If a configuration change changes owner membership or allocation rank, the change is a
**structural** network-policy transition. It must pass through the accepted restrictive
barrier/reconciliation path; it is not eligible for the pure-priority fast path.

#### Cleanup and conflict rule

Reserved lower resource spaces are not permission for blind deletion.

Cleanup/recovery must:

1. inventory the reserved resource scope;
2. prove each candidate resource matches an accepted VPN-GATE owner/role shape;
3. delete/reconcile only proved owned resources;
4. treat an unexpected object inside a reserved table/priority/protocol/nft namespace as an
   observable ownership conflict and fail closed rather than silently deleting foreign
   state.

This applies equally to current and stale allocations from a previous accepted
configuration.

Because table/rule allocations may change across a structural configuration transition,
cleanup identity must be derivable from the reserved lower namespace and exact resource
shape, not solely from the current configuration's allocation map.

#### Platform resource-space contract

Concrete numeric pools are lower Linux platform constants.

They must satisfy:

- disjoint payload/probe table pools;
- disjoint RPDB owner pools with the required precedence relative to ambient/main lookup;
- route protocol marker values that are representable and observable through the accepted
  inventory mechanism;
- enough metric space for the largest accepted currently realized path set plus scratch and
  terminal guard;
- no arbitrary small product limit when a larger kernel resource space can be used safely;
- privileged evidence for the actual chosen Linux numeric ranges before production code
  relies on them.

The user configuration never contains these values.

#### Accepted current Linux platform space

EXP-028 passed in privileged GitHub Linux CI, including both first and last values of the
declared table/RPDB pools. The current NG3 Linux reference implementation therefore uses:

```text
payload table pool:
    [0x80000000, 0xC0000000)

probe table pool:
    [0xC0000000, 0x100000000)

probe RPDB priority pool:
    [0x2000, 0x4000)      # 8192..16383

payload RPDB priority pool:
    [0x4000, 0x6000)      # 16384..24575

ambient/main lookup priority:
    32766

managed terminal/guard route protocol:
    201

managed path/unicast route protocol:
    202

first preference route metric:
    1

terminal guard route metric:
    0xffffffff

owned nftables namespace:
    family ip
    table vpn_gate
```

The high table ranges are role-classifiable by their top bits and avoid common low routing
table IDs. The selected RPDB quarters deliberately leave priorities `1..8191` and
`24576..32765` outside VPN-GATE ownership for other explicitly provisioned network-domain
policy while keeping probe rules before payload rules and payload rules before the standard
main lookup.

EXP-028 also records an observation relevant to future strict structural inventory:
with current iproute2 `-N`, `RTN_BLACKHOLE` may be rendered as numeric string `"6"`.
Parsers must normalize the semantic route type rather than require only the word
`"blackhole"`.

These are current Linux implementation constants, not user-facing schema. A materially
different kernel/iproute2/nftables platform must rerun the platform evidence gate rather
than assuming the numeric contract is portable without verification.

The executable pure allocator implements this contract over an injected
`NetworkPolicyPlatformSpace` rather than hard-coding production constants. It:

- ranks payload Profiles by canonical ID for table allocation;
- ranks probe routing demands by `(profile_id, logical_path_id)`;
- allocates payload dispatch priorities by longest-prefix-first destination order;
- keeps payload/probe table and RPDB pools disjoint;
- rejects Linux reserved table IDs and RPDB priority 0;
- requires probe RPDB space to precede payload dispatch and payload dispatch to precede the
  platform's ambient/main lookup;
- derives the same Profile-local preference metric namespace independently in every Profile
  table;
- preserves zero-path Profiles with a table/guard allocation but no priority metric space;
- exposes reserved pool membership independently of the current allocation map so stale
  resources from a previous configuration remain classifiable for cleanup.

# 10. NetworkPolicyExecutor

**Component type:** Executor

**Implements:**
- `VPNG0004-R4.R2`
- `VPNG0004-R4.R3`
- `VPNG0004-R4.R3.R1`
- `VPNG0004-R4.R3.R2`
- `VPNG0004-R4.R5`
- `VPNG0005-R5.R2`
- `VPNG0005-R5.R3`
- `VPNG0007-R7.R1`
- `VPNG0007-R7.R5`

The Executor converges the lower network domain from freshly observed current state to the
caller-selected desired semantic state.

The executable reference now separates a single physical-attempt contract from retry policy:

```text
fresh authoritative observation
        ->
pure convergence plan
        ->
apply semantic steps
        ->
fresh authoritative observation
        ->
exact postcondition check
```

A failed physical step terminates that attempt. The remaining plan is discarded, the
Executor re-observes before returning failure, and any later attempt must re-plan from that
new observation. The attempt helper contains no hidden retry loop.

A successfully issued command sequence is not confirmation. Success requires a fresh final
observation that exactly matches the desired one-route-per-logical-path assignment.

Required properties:

- observe before planning when the previous result is not authoritative;
- use a deterministic plan for one transaction;
- verify the resulting postcondition;
- never report desired state as confirmed merely because commands were issued;
- after partial failure, re-observe before planning another mutation;
- prefer a safe restrictive result when the required postcondition cannot be confirmed.

The Executor distinguishes two transition classes.

## 10.1. Pure priority permutation — make-before-break route-slot transaction

**Implements:**
- `VPNG0004-R4.R3.R1`
- `VPNG0003-R3.R2`
- `VPNG0003-R3.R3`
- `VPNG0003-R3.R4`

When the desired change alters only priority/order of the same eligible unicast path set,
the Linux implementation uses owned ordinary metric space and must be able to identify one
currently unused metric whenever a route move requires working space.

### Priority convergence domain

One executable priority-convergence attempt is scoped to **one independently observable
route key** inside a Profile routing domain, not to an aggregate union of all Profile
destinations.

For the current IPv4 direction this means that a backend instance/planning snapshot
represents one concrete owned route-key scope such as one destination prefix in the
appropriate internal routing table/domain, together with the eligible logical paths for
that route key.

This boundary is required because a Profile may materialize multiple kernel route entries
for different destinations. After a physical partial failure, one destination can contain a
temporary duplicate or completed move while another destination is still at the old
assignment. Aggregating such rows into one `logical_path -> metrics` map would lose
authoritative state and could falsely justify deletion or success.

Therefore:

- each route-key domain is observed and converged from its own fresh kernel snapshot;
- one current domain snapshot is normalized from numeric IPv4 iproute2 JSON by exact
  owner-protocol + destination scope and current path endpoint identity;
- path identity matching includes the current `(ifname, ifindex)` endpoint plus the
  expected gateway/onlink shape, so same-name interface replacement or a foreign owned row
  cannot impersonate the accepted logical path;
- route forms not representable by the single-path priority contract (multipath/nexthop
  forms, cross-family `via`, or unrepresented flags) fail observation instead of being
  silently projected into a simpler state;
- the path-level `logical_path -> observed metrics` model is valid only inside one such
  route-key domain;
- temporary progress may differ between route-key domains while convergence is in flight,
  but every affected domain must preserve the pure-priority safety invariant: every eligible
  path remains represented and no ineligible path is introduced;
- completion of a Profile-level priority change is confirmed only after all affected
  route-key domains have fresh postconditions matching the same desired logical-path order;
- coordinator execution is deterministic over a canonical destination order, performs no
  hidden retry, and does not infer Profile success from per-domain command return values;
- after all bounded domain attempts finish, the coordinator performs a second fresh
  verification pass across every affected domain; only that final aggregate postcondition
  may mark the Profile priority change confirmed;
- failure in one domain does not permit stale-plan replay in that or another domain; each
  further attempt starts from fresh observation of the domain it will mutate.

No requirement promises an atomic simultaneous metric permutation across all destination
prefixes. The required observable invariants are preserved path membership/safety during
the transition and the configured effective order after verified convergence.

The unused/free metric is inferred operationally from freshly observed current state. It is
not configuration, semantic state or a permanently materialized "hole".

In particular, EXP-027 proved that an all-live steady state needs no configured/materialized
gap: the next unused ordinary metric is sufficient for the first move. Other layouts may
naturally expose a free metric between ordered regions as a consequence of the current route
arrangement.

The only move primitive is:

```text
X currently at Mold
Mfree is free

1. add the same allowed route X at Mfree
2. verify/continue transaction
3. delete X at Mold
```

Between steps 1 and 3:

- every eligible path still has at least one route;
- `X` temporarily has two route copies with different metrics;
- no unrelated or previously ineligible path is introduced.

After deletion, `Mold` becomes the new free metric position.

The deterministic planner repeats this primitive until the current route ordering equals the
desired ordering.

The executable convergence layer additionally accepts a **freshly observed owned-route
snapshot** in which one logical path may temporarily have more than one metric after a
partially completed make-before-break move.

Its normalized recovery semantics are:

- identical logical-path membership remains mandatory for the priority-only path;
- an already-observed redundant route copy may be deleted only while another confirmed copy
  of the same logical path remains;
- after redundant copies are normalized, further movement is expressed only as the semantic
  `RoutePriorityMove(from_metric, to_metric)` primitive;
- a `RoutePriorityMove` retains the architectural meaning
  `add new copy -> verify -> delete old copy`; it is not exposed as independently replayable
  raw add/delete commands;
- a path with no observed route, an inter-path metric collision, a route outside the owned
  metric space, or a structural membership difference is rejected from this priority-only
  convergence path;
- after any partial execution failure the remaining plan is stale: the Executor must
  re-observe authoritative state and produce a new convergence plan before another mutation.

The convergence planner itself is not postcondition evidence. Confirmation still belongs to
the physical Executor/Adapter boundary after Linux mutation and re-observation.

The current executable Linux backend now closes that boundary for the **pure-priority
single-route-key** subset:

- route observation is bracketed by two current interface inventories;
- relevant `(ifname, ifindex)` identities must remain stable across that observation window;
- every mutation re-observes the whole route-key domain before and after the physical step;
- add-before-delete is accepted only when the fresh after-add snapshot equals the exact
  expected whole-domain state;
- delete-old is followed by another fresh exact whole-domain postcondition check;
- duplicate cleanup is likewise prechecked and verified against the whole domain;
- any unrelated route drift inside the same domain invalidates the semantic step rather than
  being ignored;
- the backend issues exact argv-based iproute2 commands inside the managed namespace and does
  not use shell interpolation.

This physical slice does not yet imply completion of structural policy mutation, RPDB/nft
materialization, multi-domain Profile orchestration or daemon lifecycle.

Priority mutation is serialized **per Profile/routing domain**:

- only one priority transaction for that Profile/domain mutates its metric layout at a time;
- the active transaction plan is immutable and is not cancelled halfway through;
- newer desired orders may be coalesced to the latest desired order while the active
  transaction completes;
- after final verification, a later transaction starts from freshly observed materialized
  state and the latest desired order;
- replay of every intermediate availability transition is neither required nor desired;
- unrelated Profiles/domains are not globally serialized merely because one Profile is
  moving metrics.

This is the NG3 re-derivation of the historical "metric hole" algorithm. Historical NG2
EXP-027 already demonstrated the relevant Linux property: the same path can temporarily
exist at two metrics, exact deletion removes only the old copy, and the full eligible set
remains present for both ordinary prefixes and `default`.

The historical evidence is reusable because the kernel claim is materially identical; the
NG2 product semantics are not inherited by that fact.

## 10.2. Structural policy transition — guarded fail-closed convergence

**Implements:**
- `VPNG0004-R4.R3.R2`
- `VPNG0004-R4.R1`
- `VPNG0004-R4.R2`
- `VPNG0004-R4.R5`

If membership, direction, filtering/NAT or another structural policy dimension changes, the
priority-only route-slot proof no longer applies.

The Executor may establish/retain a restrictive guard for the affected traffic while it
changes lower state, and may temporarily interrupt forwarding when necessary to preserve the
safety postconditions.

It must never preserve continuity by passing traffic through a path or policy state that is
forbidden by either the old or new accepted policy.

After partial failure it re-observes authoritative lower state before planning further
mutation.

### 10.2.1. Complete structural routing desired state

Before a structural transaction is applied, the lower Adapter/Calculator must be able to
derive a complete desired routing projection for the affected payload owner set.

For each enabled Profile the projection contains:

```text
one allocated Profile table

one terminal fail-closed route:
    table = Profile table
    type = BLACKHOLE
    destination = default
    protocol = guard marker
    metric = terminal guard metric

for every Profile destination and current realized logical path:
    one desired path route
    table = Profile table
    destination = Profile destination
    protocol = path marker
    metric = current semantic preference slot
    endpoint/gateway/onlink = verified integration realization

for every Profile destination:
    one host-boundary RPDB dispatch rule
    iif = current verified managed host-boundary endpoint
    to = Profile destination
    table = Profile table
    priority = deterministic allocation
```

A zero-path Profile therefore still has:

- its allocated table;
- its terminal guard;
- its destination dispatch rules;

and has no ordinary path routes. Dispatching its traffic into that table must terminate in
the guard rather than fall through to ambient/main routing.

The lower desired projection is data only. Constructing it does not mutate Linux state and
does not claim the policy is active.

The verified managed host-boundary endpoint is an internal runtime fact, not a user-visible
route/rule field.

### 10.2.2. Structural activation barrier

A structural transition is wider than route-table preparation.

In particular, installing a new RPDB dispatch rule can make a newly prepared Profile table
reachable. That activation must not occur before the filtering/NAT state required by the
same new semantic policy is safe.

#### Root barrier primitive

The first-release structural barrier is the managed network namespace's own IPv4 forwarding
gate:

```text
net.ipv4.ip_forward = 0
```

This sysctl belongs to the isolated managed network domain, not to the ordinary host network
namespace.

The Executor may begin allowing structural mutation only after:

```text
write ip_forward = 0
        ->
fresh reread
        ->
observed value == 0
```

A successful write command without the confirming reread is not a barrier.

This primitive is deliberately below the user configuration contract. It is not a policy
knob and does not depend on Profile direction, NAT spelling, Device firewall grammar or
current route allocation.

The root barrier is global to managed IPv4 forwarding. Structural transitions may therefore
temporarily interrupt forwarding for Profiles whose individual semantic policy did not
change. Release 1 does not promise continuity across a structural policy transition; the
separate pure-priority fast path remains the mechanism for non-disruptive priority-only
changes.

The global barrier is chosen intentionally instead of a per-Profile nft deny rule:

- it does not depend on correctly classifying overlapping Profile prefixes while state is
  mixed;
- it remains effective when path bindings or RPDB allocations are being replaced;
- it does not depend on the final NAT/Device-firewall grammar;
- critically, it does not rely on the nft namespace being already trusted while nft
  ownership/conflict recovery is itself in progress.

If the Executor cannot verify `ip_forward=0`, it must not begin or continue an allowing
structural rebuild. From a previously verified state the requested structural transition is
aborted. During startup/recovery from UNKNOWN state, inability to establish the barrier is a
hard failure and no new allowing state is materialized.

The managed namespace forwarding gate therefore becomes explicit lower owned state:

```text
ForwardingGate:
    desired = enabled | disabled
    observed = 0 | 1 | unknown
```

Only `observed = 0` is sufficient as the structural barrier.

EXP-030 passed in privileged GitHub CI and proved the selected primitive on the current Linux
target with real forwarded packets:

- the managed namespace value was independently writable/readable;
- changing it did not change the host namespace value;
- `ip_forward=1` passed transit ICMP across a two-interface routing namespace;
- `ip_forward=0` blocked that same transit path;
- restoring and rereading `1` restored forwarding.

The executable lower backend may therefore use
`ip netns exec <managed-ns> sysctl ... net.ipv4.ip_forward`, but success remains defined by
the fresh reread value rather than process exit status alone.

#### Structural transaction ordering

With the root barrier verified, the physical structural transaction has this ordering
contract:

```text
fresh lower observation
        ->
set/reread managed-netns ip_forward = 0
        ->
prepare/verify new guarded routing tables
    - terminal guards first
    - desired ordinary path routes
        ->
prepare/verify required nft filtering/NAT state
        ->
install/switch/verify RPDB dispatch
        ->
verify complete desired routing + nft postcondition
        ->
set/reread managed-netns ip_forward = 1
        ->
fresh final verification
        ->
cleanup stale old allocation/state when safe
```

The exact barrier mechanism is part of the forthcoming nft/structural Executor unit, but its
semantic postcondition is already fixed:

> while structural state is mixed or unconfirmed, affected traffic cannot traverse a policy
> that is forbidden by either the previously accepted or newly accepted policy.

A route-table preparation helper may create an otherwise unreachable new table before nft
activation, because no new RPDB rule reaches it yet. It may not switch dispatch as a
standalone optimization.

Similarly, stale old table/rule cleanup must not occur merely because the new commands were
issued; the new complete postcondition must first be authoritatively verified.

This is why the pure-priority path remains a separate fast path: only there is path
membership/filter/NAT unchanged and the semantic make-before-break proof sufficient without a
structural barrier.

### 10.2.3. Authoritative structural route/RPDB observation

Structural recovery requires inventory of the **whole reserved lower namespace**, not only
resources named by the current allocation map.

The current Linux observation commands are:

```text
ip -j -N -4 route show table all
ip -j -N -4 rule show
```

EXP-029 established the current iproute2 6.19 numeric JSON form relevant to the accepted NG3
resource space:

- non-main high table IDs are numeric strings;
- route protocols are numeric strings;
- ordinary unicast type may be omitted;
- `RTN_BLACKHOLE` is numeric string `"6"`;
- host-route `/32` destination may be rendered as a bare IPv4 address;
- route scope is numeric string `"253"` for the tested direct-device routes;
- RPDB `priority` is numeric;
- RPDB lookup table is a numeric string;
- payload destination selector is represented by `dst` address plus `dstlen`;
- `src = "all"` is explicit in the tested rules;
- probe `fwmark` / `fwmask` are hexadecimal strings.

The structural observer must normalize these representation forms into typed semantic lower
objects.

Rows outside VPN-GATE reserved table/priority pools may be ignored by this owner-specific
inventory. Rows **inside** reserved pools must not be silently ignored merely because their
shape is unexpected.

For a reserved object the observer returns either a recognized managed route/rule or an
explicit ownership conflict / unsupported reserved shape.

Observation failure, malformed JSON and ownership conflict are distinct from a valid empty
managed inventory.

The route observer resolves any managed `dev` through the same fresh `(ifname, ifindex)`
interface inventory used elsewhere. Same-name interface replacement must therefore remain
visible.

This observation boundary is read-only. It does not authorize cleanup or activation by
itself.

# 11. Event contracts

The architecture currently needs only semantic event edges required by Engine roles.

## 11.1. Availability observation

`AvailabilityProbeAgent -> PayloadTrafficManager`

**Implements:**
- `VPNG0003-R3.R6`
- `VPNG0003-R3.R6.R1`
- `VPNG0003-R3.R6.R2`
- `VPNG0003-R3.R6.R3`
- `VPNG0007-R7.R5`

The event must identify the availability subject and logical path and carry only the bounded
observation information needed by the Manager.

The event carries normalized `AvailabilityEvidence`.

Local inability to execute the observation mechanism produces `no_evidence` plus diagnostic
state unless the observation contract proves that the failure itself demonstrates path
unusability.

By `VPNG0003-R3.R6.R3`, only evidence that observes a relevant path property may become
`positive` or `negative`.

No requirement currently justifies:

- durable replay;
- global revision numbers;
- a persistent event log;
- a universal ordering service.

## 11.2. Payload state publication

`PayloadTrafficManager -> observers`

**Implements:**
- `VPNG0006-R6.R2`
- `VPNG0006-R6.R4`

The Manager publishes a current projection that distinguishes desired/effective/unknown
state where that distinction affects behavior or safety.

System-wide current status is composed by `RuntimeStatusAgent` from authoritative owner
snapshots; see section 13.

Publication success is separate from convergence success.

If the Manager has already applied and freshly verified the required semantic state but
publishing the resulting current projection fails transiently:

- the verified semantic/physical operation is not blindly repeated solely because the
  publisher failed;
- the owner retains enough current verified projection to retry publication;
- a later audit/reconciliation may republish the current projection without mutating already
  matched lower state;
- unexpected internal programming/runtime faults remain errors and are not converted into a
  fake successful publication state.

This follows `VPNG0005-R5.R3`, `VPNG0006-R6.R3`, `VPNG0006-R6.R4` and keeps mutation retry separate
from information-delivery retry.

# 12. Startup, shutdown and recovery

This pass does **not** introduce a LifecycleManager.

No accepted requirement currently proves that lifecycle orchestration needs an independent
long-lived semantic component.

Instead, the architecture records only required postconditions:

**Implements:**
- `VPNG0001-R1.R2`
- `VPNG0004-R4.R4`
- `VPNG0005-R5`
- `VPNG0005-R5.R1`
- `VPNG0005-R5.R4`
- `VPNG0005-R5.R5`
- `VPNG0005-R5.R6`
- `VPNG0005-R5.R6.R1`
- `VPNG0005-R5.R6.R2`
- `VPNG0005-R5.R6.R3`
- `VPNG0007-R7.R1`

Required orchestration semantics:

1. acquire/establish instance ownership/exclusion needed to prevent competing mutation;
2. before trusting a new candidate configuration, observe and cleanup/contain stale owned
   state from an incomplete or previous instance using only ownership markers/invariants that
   do not depend on successfully parsing the new config;
3. if stale owned state cannot be safely cleaned or contained, do not proceed as though a
   known baseline exists; retain/re-establish protective restriction and report the failure;
4. load and validate the candidate Device/Profile configuration before dependent actuation;
5. construct/verify the managed network domain and protective fail-closed boundary before
   declaring payload ready;
6. create/start runtime components only after their prerequisites exist;
7. external VPN process/interface presence is **not** a general startup-success prerequisite:
   an enabled Profile may reach ready structural policy with zero current paths and remains
   fail-closed until valid bindings appear;
8. materialize current Profile policy from valid bindings and verify required safety/readiness
   postconditions from fresh observation;
9. only then report successful start/readiness;
10. during shutdown, quiesce ongoing activity before deleting state it depends on where
    dependency requires this order;
11. attempt cleanup of independent owned domains even if another cleanup fails;
12. preserve all material failures for observability.

Startup/stop interaction is phase-bounded:

- stop/shutdown handlers must be effective before startup begins creating owned mutable state;
- if a stop is requested during STARTING, finish/abort the current bounded phase safely and do
  not begin later startup phases;
- once startup may have created forwarding-capable or other safety-relevant owned state, stop
  must execute containment/cleanup rather than exit and abandon partial state;
- a stop between lower-state apply and readiness publication must not leave owned forwarding
  active after process exit.

This is the recovered semantic value of the historical
`LOCK -> CLEANUP -> LOAD/VALIDATE -> APPLY -> RUN` ordering. The exact CLI/service-manager
mechanism and exact phase implementation are replaceable.

## 12.1. Product lifecycle control surface

The lifecycle operations required by `VPNG0005-R5.R6` are exposed through a thin product
control surface.

The architecture does not require that surface to be a specific CLI, service manager,
socket or API. Those are replaceable interface mechanisms.

Semantically:

```text
start
    -> run startup orchestration
    -> report success only after required readiness/safety postconditions

stop
    -> run quiesce + cleanup orchestration
    -> report success only after required cleanup postconditions

restart
    -> stop/cleanup as required
    -> start from the resulting authoritative state
    -> never report success while previous required cleanup remains unresolved
```

The control surface is not a long-lived domain Engine and owns no independent lifecycle
policy. It invokes procedural assembly/orchestration whose postconditions are already
defined by the lifecycle requirements.

This keeps product control operations explicit while avoiding a LifecycleManager that has no
independently required semantic state.

For the current scope, procedural lifecycle orchestration remains the accepted architecture.
A dedicated Engine would require a later requirement proving an ongoing semantic
responsibility that cannot be represented by these direct operations.

## 12.2. Local Manager reconciliation

**Implements:**
- `VPNG0005-R5.R2`
- `VPNG0005-R5.R2.R1`
- `VPNG0005-R5.R3`
- `VPNG0005-R5.R3.R1`
- `VPNG0007-R7.R1`
- `VPNG0007-R7.R1.R1`

Any Manager that owns mutable external state keeps the current accepted desired semantic
state and periodically re-observes its own managed domain while the corresponding function
is active.

The reconciliation loop is local to the Manager:

```text
current desired state
        +
periodic audit / relevant event
        |
        v
observe authoritative actual state
        |
        +-- already satisfied --> no physical mutation;
        |                        publish/republish confirmed projection if needed
        |
        +-- drift / previous recoverable failure
                    |
                    v
             converge through Adapter
                    |
                    v
             verify postcondition
```

The periodic audit is a fallback for silent drift. Relevant external or internal events may
trigger earlier reconciliation, but correctness does not depend on receiving such an event.

The exact audit interval is a local implementation parameter unless a later product
requirement makes recovery latency user-visible.

No global scheduler, durable retry queue, missed-tick replay or retry-history journal is
introduced.

If an audit occurs while reconciliation is already active, at most one future reconciliation
need must be retained; multiple equivalent triggers may be coalesced because the next
reconciliation always starts from freshly observed actual state.

A recoverable failure does not enqueue the failed command sequence for replay. The Manager
retains desired semantic state and on a later reconciliation re-observes reality and computes
a new convergence operation from current state.

This architecture makes retry idempotence a property of semantic reconciliation rather than
command replay.

# 13. RuntimeStatusAgent

**Component type:** Agent

**Implements:**
- `VPNG0006-R6`
- `VPNG0006-R6.R1`
- `VPNG0006-R6.R2`
- `VPNG0006-R6.R3`
- `VPNG0006-R6.R4`
- `VPNG0007-R7.R1`
- `VPNG0007-R7.R1.R1`
- `VPNG0007-R7.R3.R1`
- `VPNG0007-R7.R5`

The Agent observes current projections published by the Engines that own product domains and
composes a user-facing current status snapshot.

It is deliberately an Agent rather than a Manager because it does not actuate or own the
represented domains.

Inputs are current-snapshot InfoEvents, including where applicable:

- accepted/configured intent reported by the owner that accepted it;
- current logical VPN-path binding/effective path information;
- current payload policy/effective ordering;
- availability observation/diagnostic state;
- lifecycle/readiness/cleanup failures;
- lower-domain convergence failures that prevent required postconditions.

The Agent stores only the latest relevant snapshot per authoritative source. It does not
store event history, reconstruct past transitions or become a system-of-record.

Conceptual output:

```text
RuntimeStatusSnapshot:
    configured_intent
    confirmed_effective_state
    availability_state
    readiness
    blocking_problems
    unknown_or_unconfirmed_fields
```

Truthfulness rules:

- a desired/configured value is never reported as confirmed actual merely because it was
  requested;
- missing or stale authoritative information is represented as unknown/unconfirmed;
- a local source retains ownership of its semantic truth; the StatusAgent only composes;
- conflicting snapshots are surfaced as an inconsistency/problem rather than resolved by a
  hidden status policy;
- current status contains no unbounded history.

The presentation mechanism is outside this component contract. CLI, API, text output or
another user-facing surface may render the same current `RuntimeStatusSnapshot` without
changing status semantics.

Historical work discussed a dedicated aggregated `ProfileState` combining binding,
payload-rules, publication and probe diagnostics. That aggregation was explicitly not
finalized in the recovered material and is **not** imported as an NG3 requirement here.
Current R6 remains satisfied by truthful composition of authoritative snapshots; any stronger
Profile-specific verdict model requires separate requirement work.

A final status query therefore does not require direct knowledge of kernel commands or
internal Manager state.

# 14. Requirement coverage in this architecture pass

| Requirement area | Architecture status |
| --- | --- |
| `VPNG0001-R1.R1` forwarding | represented by PayloadTrafficManager + NetworkPolicyAdapter |
| `VPNG0001-R1.R2` declarative operation | recovered strict Device/Profile user contract normalized by ConfigurationAdapter, including Device transport-policy intents; exact optional-policy external grammar is explicitly postponed in `design/deferrals/NG3-user-facing-policy-grammar.md` |
| `VPNG0001-R1.R3` VPN-channel service | logical path identity/binding and administrator onboarding architecture accepted |
| `VPNG0001-R1.R3.C1` first-release admin provisioning | accepted constraint; no VPN provisioning Manager |
| `VPNG0001-R1.R3.C1.R1` admin instructions/contract | required onboarding contents architecturally defined; concrete per-integration documents remain implementation work |
| `VPNG0001-R1.R3.C2` isolated VPN data-plane endpoint | architecture constraint derived from managed-network isolation |
| `VPNG0001-R1.R3.C2.R1` isolated-channel onboarding result | placement result architecture accepted; concrete provisioning commands remain implementation-specific |
| `VPNG0002-R2` subtree — payload policy | Profile destinations/direction/device_order compile deterministically through PayloadPolicyCalculator |
| `VPNG0003-R3.R1`–`VPNG0003-R3.R5`, `VPNG0003-R3.R7` path ordering/adaptation | represented by PayloadTrafficManager + AvailabilityPriorityCalculator |
| `VPNG0003-R3.R6` subtree — path-usability evidence | subject-specific user criterion accepted; explicit target or deterministic Profile/path-topology derivation normalized to concrete IPv4 before probe runtime |
| `VPNG0004-R4` subtree — safety | isolation, verified convergence, make-before-break priority permutation and guarded structural transition accepted |
| `VPNG0005-R5.R1`, `VPNG0005-R5.R4`, `VPNG0005-R5.R5`, `VPNG0005-R5.R6` lifecycle | postconditions and thin control surface represented; long-lived LifecycleManager intentionally absent |
| `VPNG0005-R5.R2`, `VPNG0005-R5.R3` recovery | local Manager reconciliation with periodic audit and fresh observation; no retry queue/replay |
| `VPNG0006-R6.R1` configured intent visibility | RuntimeStatusAgent composes owner-published accepted intent |
| `VPNG0006-R6.R2`, `VPNG0006-R6.R4` effective/truthful state | RuntimeStatusAgent composes authoritative current snapshots and preserves unknown/unconfirmed state |
| `VPNG0006-R6.R3` system failure visibility | RuntimeStatusAgent aggregates current blocking diagnostics without becoming policy owner |
| `VPNG0007-R7` subtree — implementation quality | applied as cross-cutting architecture rules |

# 15. Deliberately omitted machinery

The following are deliberately absent from this first architecture because no accepted NG3
requirement currently makes them necessary:

- global event journal;
- generic reliable replay bus;
- universal revision/epoch framework;
- global state machine for availability;
- attempt-history storage;
- separate route-priority Manager;
- separate availability route writer;
- independent lifecycle Engine;
- configuration super-object containing every subsystem detail;
- universal probe mechanism abstraction beyond the narrow Driver contract;
- kernel-specific routing allocation objects in upper Managers.

This omission is an implementation of `VPNG0007-R7.R1`, not a claim that such machinery can
never become necessary.

# 16. Implementation freedoms and future extensions

## 16.1. Remaining configuration semantics

The configuration boundary itself is now defined and the VPN-path binding contract is
architecturally closed.

The core Device/Profile human-facing configuration contract is now recovered and recorded in
`design/NG3/config-model.md`.

Remaining interface freedom is narrower:

- parser/serialization implementation details that do not change accepted TOML semantics;
- final spelling/default semantics for configuration features not yet accepted;
- any future live-change/reload capability, which is not currently promised;
- Device firewall/publication fields that were explicitly outside the implemented
  core config contract.

These freedoms must not be expanded into a universal configuration framework without a new
requirement.

## 16.2. Availability target derivation

The product semantics and architecture boundary are now defined:

- availability is subject-specific (Profile + logical VPN path);
- explicit target is preserved exactly;
- bare ICMP derives one concrete target deterministically from already accepted
  subject/path/Device/interface/binding/peer topology semantics;
- no universal global default target exists;
- `AvailabilityTargetCalculator` performs this pure normalization before probe runtime;
- unresolved/ambiguous derivation is diagnostic and produces no runtime probe demand.

Concrete Device/integration-specific derivation formulas remain implementation work behind
the accepted Calculator contract. They must satisfy the deterministic subject-specific
contract and require their own implementation evidence.

Future TCP/UDP/HTTP mechanisms remain outside current scope.

## 16.3. User-visible status presentation

Status aggregation semantics and ownership are now defined by `RuntimeStatusAgent`.

Still replaceable as interface implementation detail:

- concrete CLI/API/text presentation format;
- formatting and filtering for different operator surfaces.

These do not require another domain component unless later product requirements make
presentation behavior itself semantic.

## 16.4. Lifecycle ownership

Affected requirements:
- `VPNG0005-R5.R1`
- `VPNG0005-R5.R2`
- `VPNG0005-R5.R3`
- `VPNG0005-R5.R4`
- `VPNG0005-R5.R5`
- `VPNG0005-R5.R6`

Lifecycle control semantics and autonomous local reconciliation are now explicit. They
still do not justify a separate global lifecycle component.

For the first release, VPN tunnel/session creation is outside this lifecycle scope by
`VPNG0001-R1.R3.C1`; lifecycle concerns VPN-GATE-owned state and its use of already provisioned
channels.

Procedural assembly plus the thin product control surface remains the simpler accepted
architecture.

## 16.5. Administrator-facing VPN-channel onboarding implementation

The onboarding architecture is closed:

- the administrator provisions/configures the external channel;
- its data-plane endpoint must be present inside the managed domain;
- configuration binds a stable logical path identity to one verified current endpoint;
- availability-check target may be explicit or derived from current endpoint/network facts;
- acceptance/rejection and unresolved target/binding conditions are observable.

Remaining work is concrete documentation and integration implementation for each supported
VPN technology.

# 17. Current architecture principle

For this NG3 pass:

> If a component cannot point to a requirement, it does not enter the architecture.

And conversely:

> A requirement is allowed to remain without architecture until its semantics are concrete
> enough to justify one.
