# VPN-GATE NG3 — Architecture Report

**Status:** partial NG3 architecture, design-cycle draft  
**Cycle:** `ng3-design-cycle-20261115-managed-domain-contract-40m`  
**Requirements:** `design/NG3/requirements.md`  
**Component model:** `design/component-model.md`

This document is an implementation report for accepted NG3 requirements.

It is not a source of new product semantics.

No NG2 component is inherited merely because it existed. Historical NG2 design may be used
as evidence that a mechanism is technically plausible or as a source of failure modes, but
every NG3 architectural element below must be justified again by NG3 requirement IDs.

# 1. Architecture scope of this pass

This pass attempts architecture only for the requirements that are already sufficiently
defined to justify concrete responsibilities:

- payload policy materialization;
- deterministic path preference;
- availability-driven priority adaptation;
- active availability observation;
- fail-closed network-policy application;
- local drift/retry behavior around owned network policy;
- current component-level state publication.

This pass intentionally does **not** yet define:

- the complete user configuration schema;
- configuration parsing/normalization ownership;
- automatic VPN-session provisioning/configuration, because `VPNG-R1.R3.C1` explicitly leaves
  that responsibility to the administrator in the first release;
- the exact administrator-facing VPN-channel onboarding contract required by
  `VPNG-R1.R3.C1.R1`;
- final end-user status aggregation;
- transport publication;
- final ROU/BOU topology;
- Linux-specific route/table/nft/sysctl representation;
- WireGuard/OpenConnect-specific machinery;
- a universal event persistence/replay layer.

Those gaps remain requirements without invented architecture.

## 1.1. Managed network isolation boundary ("стакан")

**Implements:**
- `VPNG-R4.R6`
- `VPNG-R4.R6.R1`
- `VPNG-R4.R6.R1.R1`
- `VPNG-R4.R6.R1.R2`
- `VPNG-R4.R6.R1.R3`
- `VPNG-R4.R6.R1.R4`
- `VPNG-R4.R2`
- `VPNG-R4.R4`
- `VPNG-R5.R1`
- `VPNG-R5.R4`
- `VPNG-R7.R3`
- `VPNG-R7.R3.R2`

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
- **identity:** the exact rule that binds a configured logical VPN path to a concrete
  endpoint remains unresolved and is intentionally delegated back to the requirement tree.

This closes the architectural shape of the managed domain without inventing the still-open
path-identity/configuration contract.

The host network namespace is outside this managed domain. Interaction with the host must
occur only through explicit boundary links/contracts.

The purpose of this boundary is not "use netns because NG1 used netns". It is to realize
`VPNG-R4.R6`: unrelated host network state must not become implicit product state or be
mutated as a side effect of internal routing changes.

The namespace is therefore an architecture choice. If another mechanism can later satisfy
the same isolation/ownership requirements more simply, the requirement does not protect the
namespace itself.

### Architectural consequence for external VPN channels

**Constrained by:**
- `VPNG-R1.R3.C1`
- `VPNG-R1.R3.C2`

**Implements:**
- `VPNG-R1.R3.C1.R1`
- `VPNG-R1.R3.C2.R1`

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

For the current scope, onboarding is architecturally closed only with respect to **where the
result must end up**: the data-plane endpoint must be inside the managed domain and the host
boundary must be explicit.

Onboarding remains open with respect to **which concrete endpoint corresponds to which
logical VPN path**. That identity/configuration decision is not derivable from the isolation
requirements and is tracked in the requirement tree as a new decomposition block on
`VPNG-R1.R3`.



## 1.2. Architecture-wide implementation requirements

The structure and maintenance rules of this report itself implement cross-cutting NG3
requirements that do not belong to one runtime component.

**Implements:**
- `VPNG-R7.R2`
- `VPNG-R7.R3.R3`
- `VPNG-R7.R4`
- `VPNG-R7.R6.R1`
- `VPNG-R7.R6.R2`

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
- `VPNG-R1.R1`
- `VPNG-R2.R1`
- `VPNG-R2.R2`
- `VPNG-R2.R3`
- `VPNG-R2.R4`
- `VPNG-R4.R1`

## S2 — Preferred path degrades

Two or more paths are allowed. The preferred path becomes practically unusable while at
least one allowed alternative remains usable. New traffic should prefer the usable
alternative, without changing path membership.

Relevant requirements:
- `VPNG-R3.R1`
- `VPNG-R3.R2`
- `VPNG-R3.R3`
- `VPNG-R3.R4`
- `VPNG-R3.R5`
- `VPNG-R3.R7`

## S3 — Local presence is not sufficient evidence

A VPN interface/process can remain locally present while the remote path property relevant
to the product scenario is no longer usable. Payload may also be idle, so waiting for a
payload failure is not always useful.

The architecture therefore selects active observation as the first NG3 mechanism for
obtaining evidence required by `VPNG-R3.R6`. Active probing is an architectural choice,
not a product promise.

Relevant requirements:
- `VPNG-R3.R6`
- `VPNG-R3.R6.R3`

## S4 — Old observation finishes late

The observed concrete path context changes while an earlier asynchronous check is still
in-flight. Its later result must not modify current preference.

Relevant requirements:
- `VPNG-R3.R6.R1`
- `VPNG-R3.R6.R2`

## S5 — Network mutation partially fails

The system begins changing owned network policy and one lower operation fails. The next
decision must be based on freshly observed authoritative state and must not silently expose
unallowed forwarding.

Relevant requirements:
- `VPNG-R4.R2`
- `VPNG-R4.R3`
- `VPNG-R4.R4`
- `VPNG-R4.R5`
- `VPNG-R5.R2`
- `VPNG-R5.R3`

## S6 — One cleanup area fails

Shutdown owns several independent resources. Failure to clean one must not prevent attempts
to clean the others, and the failures must remain visible.

Relevant requirements:
- `VPNG-R5.R4`
- `VPNG-R5.R5`
- `VPNG-R6.R3`

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
- `VPNG-R1.R3`
- `VPNG-R1.R3.C1.R1`

**Constrained by:**
- `VPNG-R1.R3.C1`

For the first release, VPN-GATE consumes VPN channels that have already been deployed and
basically configured by the administrator.

The architecture therefore does **not** introduce a VPN-session/tunnel provisioning Manager
merely because older generations contained VPN process-management machinery.

The product-side boundary must eventually define enough administrator-facing contract to make
an externally provisioned channel:

- place its data-plane endpoint inside the isolated managed network domain;
- identifiable as a concrete VPN-GATE path;
- observable to the extent required by routing, safety and status requirements;
- usable by payload policy;
- documentable as a repeatable administrator procedure.

The exact representation of that contract is intentionally open. A Linux interface move,
process placement, interface name, protocol-specific handle or another mechanism must not be
selected until the supported deployment requirements make that choice necessary.

## 3.2. Logical VPN path binding

**Implements:**
- `VPNG-R1.R3.R1`
- `VPNG-R1.R3.R2`
- `VPNG-R1.R3.R3`
- `VPNG-R4.R6.R1.R4`
- `VPNG-R7.R3.R1`
- `VPNG-R7.R3.R2`

The architecture separates:

```text
logical path identity
!=
concrete current data-plane endpoint
```

The product-facing path identity is stable for the configuration lifecycle. Runtime endpoint
identity may change when the administrator recreates/replaces the externally provisioned VPN
channel.

The normalized internal contract therefore contains a logical path identity plus enough
binding intent to locate the expected concrete endpoint. The exact user-facing syntax that
produces this normalized contract is intentionally not defined here.

A concrete endpoint becomes the current endpoint for a logical path only after the binding
has been observed and verified.

### VPNPathAdapter

**Component type:** Adapter

**Implements:**
- `VPNG-R1.R3.R2`
- `VPNG-R1.R3.R3`
- `VPNG-R4.R6.R1.R4`
- `VPNG-R7.R3`
- `VPNG-R7.R5`

The Adapter is the boundary between logical VPN-path semantics and the externally
provisioned concrete VPN endpoint.

Conceptual contract:

```text
observe_binding(logical_path_id, normalized_binding_intent)
    -> matched current endpoint
     | absent
     | ambiguous
     | wrong managed domain
     | structurally unusable
```

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

The exact endpoint selector carried by `normalized_binding_intent` remains intentionally
open until `VPNG-R1.R2` is decomposed. This keeps runtime identity semantics defined while
leaving the external declarative interface unresolved.

## 3.3. Declarative configuration boundary

**Implements:**
- `VPNG-R1.R2.R1`
- `VPNG-R1.R2.R2`
- `VPNG-R1.R2.R3`
- `VPNG-R1.R3.C1.R1`
- `VPNG-R2.R1`
- `VPNG-R2.R2`
- `VPNG-R2.R3`
- `VPNG-R2.R3.R1`
- `VPNG-R2.R3.R2`
- `VPNG-R2.R4`
- `VPNG-R2.R5`
- `VPNG-R4.R1`
- `VPNG-R7.R3.R1`
- `VPNG-R7.R3.R2`
- `VPNG-R7.R5`

NG3 uses a declarative external configuration boundary. Users/admins describe product intent;
they do not provide an ordered recipe of Linux networking operations.

### ConfigurationAdapter

**Component type:** Adapter

The Adapter translates an external configuration representation into validated, normalized
domain intents.

It is Direct Machinery: a successful return means the supplied configuration has been
accepted and normalized; a failed return means no dependent network mutation may begin from
that candidate configuration.

The architecture intentionally avoids a global mutable "runtime configuration object".
Instead, the adapter produces explicit domain contracts needed by accepted requirements.

The first required normalized contracts are:

```text
VPNPathIntent:
    logical_path_id
    binding_intent

PayloadPolicyIntent:
    traffic_selector
    direction_permissions
    allowed_path_ids
    configured_preference
```

where:

- `logical_path_id` is the stable product identity from `VPNG-R1.R3.R1`;
- `binding_intent` contains only the information required by `VPNPathAdapter` to resolve
  one concrete endpoint inside the managed network domain;
- `traffic_selector` identifies the traffic class to which one policy intent applies;
- `direction_permissions` independently represents ordinary-network -> VPN and
  VPN -> ordinary-network permission;
- `allowed_path_ids` is the explicit set of logical VPN paths eligible for that traffic;
- `configured_preference` orders only those already allowed paths;
- the exact external syntax and concrete selector forms are implementation/interface choices
  and may be refined independently without changing the semantic contracts.

Payload policy and VPN path binding remain separate normalized contracts.

Validation must reject at least:

- missing required logical identity;
- duplicate/ambiguous logical path identity;
- binding intent insufficient to resolve a supported endpoint;
- contradictory declarations that cannot produce one deterministic semantic result.

A rejected configuration is not partially materialized.

### Administrator onboarding contract

For each supported externally provisioned VPN-channel integration, administrator
documentation must explain:

1. how to provision the external VPN channel according to its own mechanism;
2. what result must exist inside the managed network domain;
3. how to declare the logical `path_id` and binding intent through the product
   configuration boundary;
4. how to determine that VPN-GATE accepted or rejected the binding.

This closes the architecture of `VPNG-R1.R3.C1.R1` without choosing the final configuration
file syntax or a specific VPN protocol.

No ConfigManager, live-reload Engine, configuration database or generic plugin registry is
introduced. Those require separate accepted requirements if they become necessary.

# 4. PayloadTrafficManager

**Component type:** Manager

**Implements:**
- `VPNG-R1.R1`
- `VPNG-R2.R1`
- `VPNG-R2.R2`
- `VPNG-R2.R3`
- `VPNG-R2.R4`
- `VPNG-R2.R5`
- `VPNG-R3.R1`
- `VPNG-R3.R2`
- `VPNG-R3.R3`
- `VPNG-R3.R4`
- `VPNG-R3.R5`
- `VPNG-R3.R7`
- `VPNG-R4.R1`
- `VPNG-R4.R2`
- `VPNG-R5.R2`
- `VPNG-R5.R3`
- `VPNG-R6.R2`
- `VPNG-R6.R4`
- `VPNG-R7.R1`
- `VPNG-R7.R3`
- `VPNG-R7.R5`
- `VPNG-R7.R6`

## 4.1. Responsibility

The Manager owns the current semantic payload-policy projection for the traffic domain that
has already been normalized into its input contract.

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
`VPNG-R7.R1`.

## 4.3. Availability state inside the Manager

For each availability-enabled logical path, the Manager may keep only the bounded semantic
state necessary to implement `VPNG-R3.R3`, `VPNG-R3.R4`, `VPNG-R3.R5.R1` and
`VPNG-R3.R5.R2`:

- whether an availability problem is currently established;
- bounded progress toward establishing a problem;
- bounded progress toward confirming recovery.

No unbounded attempt history, evidence journal or replay log is justified.

**Implements:**
- `VPNG-R3.R3`
- `VPNG-R3.R4`
- `VPNG-R3.R5`
- `VPNG-R3.R5.R1`
- `VPNG-R3.R5.R2`
- `VPNG-R7.R1.R1`

The exact evidence input semantics are not finalized in this pass; see design gaps.

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
- `VPNG-R2.R4`
- `VPNG-R3.R2`
- `VPNG-R3.R7`

# 5. PayloadPolicyCalculator

**Component type:** Calculator

**Implements:**
- `VPNG-R2.R1`
- `VPNG-R2.R2`
- `VPNG-R2.R3`
- `VPNG-R2.R3.R1`
- `VPNG-R2.R3.R2`
- `VPNG-R2.R4`
- `VPNG-R2.R5`
- `VPNG-R7.R3.R1`
- `VPNG-R7.R5`

The Calculator maps normalized structural intent and already-resolved external facts into a
deterministic semantic payload-policy projection.

It is pure: the same inputs produce the same projection.

This component is justified because policy interpretation is independently testable and must
not depend on hidden network history.

Its normalized input is `PayloadPolicyIntent`.

The Calculator must preserve these invariants:

- traffic membership comes only from `traffic_selector`;
- path eligibility comes only from `allowed_path_ids`;
- direction permissions are independent and explicit;
- configured preference cannot add an ineligible path;
- availability state is not an input to structural membership or permission;
- ambiguous overlapping policy must either resolve deterministically according to the
  accepted policy contract or be rejected before materialization.

# 6. AvailabilityPriorityCalculator

**Component type:** Calculator

**Implements:**
- `VPNG-R3.R1`
- `VPNG-R3.R2`
- `VPNG-R3.R3`
- `VPNG-R3.R4`
- `VPNG-R3.R7`
- `VPNG-R7.R1`
- `VPNG-R7.R5`

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
- `VPNG-R3.R6`
- `VPNG-R3.R6.R1`
- `VPNG-R3.R6.R2`
- `VPNG-R3.R6.R3`
- `VPNG-R6.R3`
- `VPNG-R7.R1`
- `VPNG-R7.R3`
- `VPNG-R7.R5`

## 7.1. Responsibility

The Agent owns ongoing execution of configured active availability observations.

It owns:

- currently requested observation channels;
- cadence for the selected active-observation mechanism;
- bounded in-flight checks;
- association of each result with the current requested path identity;
- rejection of results that no longer belong to the current observation context;
- local diagnostics about inability to execute the observation mechanism.

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

To implement `VPNG-R3.R6.R2`, an in-flight result must carry enough identity to determine
whether it still belongs to the current physical observation context.

The minimal proposed mechanism is a monotonically replaced local observation-generation
token.

The token has no routing-policy meaning.

It exists only to reject stale physical results.

No logical evidence epoch, attempt journal or replay ordering is introduced.

**Implements:**
- `VPNG-R3.R6.R2`
- `VPNG-R7.R1`

# 8. ActiveProbeDriver

**Component type:** Driver

**Implements:**
- `VPNG-R3.R6`
- `VPNG-R3.R6.R1`
- `VPNG-R3.R6.R3`
- `VPNG-R7.R3.R2`
- `VPNG-R7.R5`

The Driver provides a narrow technical operation:

```text
check(concrete path observation identity, configured mechanism)
    -> technical observation result
```

It hides mechanism-specific execution from the Agent.

NG3 currently selects active observation as the architecture for scenario S3, but does not
yet select a concrete transport mechanism.

ICMP, TCP connect, protocol-native liveness or another mechanism therefore remain possible
Driver implementations until requirements, evidence or accepted constraints narrow that
space.

# 9. NetworkPolicyAdapter

**Component type:** Adapter

**Implements:**
- `VPNG-R1.R1`
- `VPNG-R4.R2`
- `VPNG-R4.R3`
- `VPNG-R4.R5`
- `VPNG-R5.R2`
- `VPNG-R5.R3`
- `VPNG-R5.R4`
- `VPNG-R7.R3`
- `VPNG-R7.R3.R2`
- `VPNG-R7.R5`

The Adapter is the boundary from payload semantics into the lower network-policy domain.

Its contract must express semantic operations such as:

```text
observe current owned policy state
apply desired semantic policy and verify postcondition
cleanup owned policy and verify absence
```

The upper Manager must not know:

- route-table allocation;
- rule priorities;
- nft syntax;
- sysctl syntax;
- kernel command ordering;
- transaction scratch structures.

Those details belong below the Adapter boundary unless a future product requirement makes
one observable.

# 10. NetworkPolicyExecutor

**Component type:** Executor

**Implements:**
- `VPNG-R4.R2`
- `VPNG-R4.R3`
- `VPNG-R4.R5`
- `VPNG-R5.R2`
- `VPNG-R5.R3`
- `VPNG-R7.R1`
- `VPNG-R7.R5`

The Executor converges the lower network domain from freshly observed current state to the
caller-selected desired semantic state.

Required properties:

- observe before planning when the previous result is not authoritative;
- use a deterministic plan for one transaction;
- verify the resulting postcondition;
- never report desired state as confirmed merely because commands were issued;
- after partial failure, re-observe before planning another mutation;
- prefer a safe restrictive result when the required postcondition cannot be confirmed.

The exact Linux transaction algorithm is not chosen in this pass.

In particular, the NG2 empty-slot route permutation mechanism is **not** automatically
carried into NG3. It may later be selected if lower-level routing requirements and kernel
evidence make it the minimal sufficient implementation.

# 11. Event contracts

The architecture currently needs only semantic event edges required by Engine roles.

## 11.1. Availability observation

`AvailabilityProbeAgent -> PayloadTrafficManager`

**Implements:**
- `VPNG-R3.R6`
- `VPNG-R3.R6.R1`
- `VPNG-R3.R6.R2`
- `VPNG-R7.R5`

The event must identify the logical path and carry only the bounded observation information
needed by the Manager.

The exact positive/negative evidence shape is unresolved. Local inability to execute the
observation mechanism is not automatically treated as path failure: by
`VPNG-R3.R6.R3`, evidence used for path adaptation must actually observe a relevant path
property.

No requirement currently justifies:

- durable replay;
- global revision numbers;
- a persistent event log;
- a universal ordering service.

## 11.2. Payload state publication

`PayloadTrafficManager -> observers`

**Implements:**
- `VPNG-R6.R2`
- `VPNG-R6.R4`

The Manager publishes a current projection that distinguishes desired/effective/unknown
state where that distinction affects behavior or safety.

A final system-wide status model is not yet designed.

# 12. Startup, shutdown and recovery

This pass does **not** introduce a LifecycleManager.

No accepted requirement currently proves that lifecycle orchestration needs an independent
long-lived semantic component.

Instead, the architecture records only required postconditions:

**Implements:**
- `VPNG-R1.R2`
- `VPNG-R4.R4`
- `VPNG-R5.R1`
- `VPNG-R5.R4`
- `VPNG-R5.R5`
- `VPNG-R5.R6`
- `VPNG-R5.R6.R1`
- `VPNG-R5.R6.R2`
- `VPNG-R5.R6.R3`
- `VPNG-R7.R1`

Required orchestration semantics:

1. establish a protective network boundary before declaring payload ready;
2. create/start components only after their prerequisites exist;
3. during shutdown, quiesce ongoing activity before deleting state it depends on where
   dependency requires this order;
4. attempt cleanup of independent owned domains even if another cleanup fails;
5. preserve all material failures for observability.

## 12.1. Product lifecycle control surface

The lifecycle operations required by `VPNG-R5.R6` are exposed through a thin product
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
- `VPNG-R5.R2`
- `VPNG-R5.R2.R1`
- `VPNG-R5.R3`
- `VPNG-R5.R3.R1`
- `VPNG-R7.R1`
- `VPNG-R7.R1.R1`

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
        +-- already satisfied --> publish/retain confirmed projection
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

# 13. Requirement coverage in this architecture pass

| Requirement area | Architecture status |
| --- | --- |
| `VPNG-R1.R1` forwarding | represented by PayloadTrafficManager + NetworkPolicyAdapter |
| `VPNG-R1.R2` declarative operation | configuration side represented by ConfigurationAdapter; lifecycle control side represented by thin product control surface |
| `VPNG-R1.R3` VPN-channel service | logical path identity/binding and administrator onboarding architecture accepted |
| `VPNG-R1.R3.C1` first-release admin provisioning | accepted constraint; no VPN provisioning Manager |
| `VPNG-R1.R3.C1.R1` admin instructions/contract | required onboarding contents architecturally defined; concrete per-integration documents remain implementation work |
| `VPNG-R1.R3.C2` isolated VPN data-plane endpoint | architecture constraint derived from managed-network isolation |
| `VPNG-R1.R3.C2.R1` isolated-channel onboarding result | placement result architecture accepted; concrete provisioning commands remain implementation-specific |
| `VPNG-R2` subtree — payload policy | semantic ownership represented; normalized config schema missing |
| `VPNG-R3.R1`–`VPNG-R3.R5`, `VPNG-R3.R7` path ordering/adaptation | represented by PayloadTrafficManager + AvailabilityPriorityCalculator |
| `VPNG-R3.R6` subtree — path-usability evidence | active observation selected via AvailabilityProbeAgent + ActiveProbeDriver; evidence semantics incomplete |
| `VPNG-R4` subtree — safety | lower boundary/executor responsibilities represented; managed network isolation selected; concrete lower mutation strategy otherwise incomplete |
| `VPNG-R5.R1`, `VPNG-R5.R4`, `VPNG-R5.R5`, `VPNG-R5.R6` lifecycle | postconditions and thin control surface represented; long-lived LifecycleManager intentionally absent |
| `VPNG-R5.R2`, `VPNG-R5.R3` recovery | local Manager reconciliation with periodic audit and fresh observation; no retry queue/replay |
| `VPNG-R6.R1` configured intent visibility | **not yet architected** |
| `VPNG-R6.R2`, `VPNG-R6.R4` payload effective state | component-level projection represented |
| `VPNG-R6.R3` system failure visibility | partial diagnostics only; **final aggregation missing** |
| `VPNG-R7` subtree — implementation quality | applied as cross-cutting architecture rules |

# 14. Deliberately omitted machinery

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

This omission is an implementation of `VPNG-R7.R1`, not a claim that such machinery can
never become necessary.

# 15. Design gaps that block deeper architecture

## 15.1. Remaining configuration semantics

The configuration boundary itself is now defined and the VPN-path binding contract is
architecturally closed.

Remaining configuration detail is limited primarily to external representation and lifecycle:

- the concrete external syntax used to express `traffic_selector`, path IDs and direction
  permissions;
- whether any configuration changes must be supported live;
- final user-visible configured-intent projection under `VPNG-R6.R1`.

The semantic payload-policy contract itself is now defined by `PayloadPolicyIntent`.

These gaps must be refined by their owning requirement branches rather than by expanding
`ConfigurationAdapter` into a universal configuration framework.

## 15.2. Availability evidence semantics

Affected requirements:
- `VPNG-R3.R3`
- `VPNG-R3.R4`
- `VPNG-R3.R5`
- `VPNG-R3.R6`

Current requirements are sufficient to reject stale/misbound evidence and to require an
adequate observation property, but they do not yet define the full confirmation policy.

Missing requirement detail:

- what exactly constitutes sufficient negative path evidence;
- how delayed positive evidence interacts with an evaluation boundary;
- whether confirmation thresholds are user-configurable product semantics or internal
  policy.

A local observation-execution failure is currently treated as diagnostic rather than path
evidence unless a lower requirement/evidence proves that such a failure itself demonstrates
path unusability.

This gap blocks final event contract and hysteresis algorithm.

## 15.3. User-visible status aggregation

Affected requirements:
- `VPNG-R6.R1`
- `VPNG-R6.R2`
- `VPNG-R6.R3`
- `VPNG-R6.R4`

Current components can expose local current state, but the requirements do not yet define
the final user-facing status model, aggregation ownership or presentation boundary.

No RuntimeStateManager/StatusManager is introduced until that responsibility is made
concrete.

## 15.4. Lifecycle ownership

Affected requirements:
- `VPNG-R5.R1`
- `VPNG-R5.R2`
- `VPNG-R5.R3`
- `VPNG-R5.R4`
- `VPNG-R5.R5`
- `VPNG-R5.R6`

Lifecycle control semantics and autonomous local reconciliation are now explicit. They
still do not justify a separate global lifecycle component.

For the first release, VPN tunnel/session creation is outside this lifecycle scope by
`VPNG-R1.R3.C1`; lifecycle concerns VPN-GATE-owned state and its use of already provisioned
channels.

Procedural assembly plus the thin product control surface remains the simpler accepted
architecture.

## 15.5. Administrator-facing VPN-channel onboarding contract

Affected requirements:
- `VPNG-R1.R3`
- `VPNG-R1.R3.C1`
- `VPNG-R1.R3.C1.R1`
- `VPNG-R6.R1`

The ownership boundary is now decided: the administrator provisions/configures the channel in
the first release.

Still missing are the supported-channel contract and instructions that tell the administrator
how VPN-GATE identifies and consumes such a channel.

This must be refined before choosing concrete interface/process/protocol identity machinery.

# 16. Current architecture principle

For this NG3 pass:

> If a component cannot point to a requirement, it does not enter the architecture.

And conversely:

> A requirement is allowed to remain without architecture until its semantics are concrete
> enough to justify one.
