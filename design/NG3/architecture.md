# VPN-GATE NG3 — Architecture Report

**Status:** partial NG3 architecture, design-cycle draft  
**Cycle:** `ng3-design-cycle-20261115-40m`  
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
- the complete VPN process/device lifecycle;
- final end-user status aggregation;
- transport publication;
- final ROU/BOU topology;
- Linux-specific route/table/nft/sysctl representation;
- WireGuard/OpenConnect-specific machinery;
- a universal event persistence/replay layer.

Those gaps remain requirements without invented architecture.

# 2. Architecture summary

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

# 3. PayloadTrafficManager

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

## 3.1. Responsibility

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

## 3.2. Why one Manager

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

## 3.3. Availability state inside the Manager

For each availability-enabled logical path, the Manager may keep only the bounded semantic
state necessary to implement `VPNG-R3.R3`, `VPNG-R3.R4` and `VPNG-R3.R5`:

- whether an availability problem is currently established;
- bounded progress toward establishing a problem;
- bounded progress toward confirming recovery.

No unbounded attempt history, evidence journal or replay log is justified.

**Implements:**
- `VPNG-R3.R3`
- `VPNG-R3.R4`
- `VPNG-R3.R5`
- `VPNG-R7.R1.R1`

The exact evidence input semantics are not finalized in this pass; see design gaps.

## 3.4. Availability affects priority only

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

# 4. PayloadPolicyCalculator

**Component type:** Calculator

**Implements:**
- `VPNG-R2.R1`
- `VPNG-R2.R2`
- `VPNG-R2.R3`
- `VPNG-R2.R5`
- `VPNG-R7.R3.R1`
- `VPNG-R7.R5`

The Calculator maps normalized structural intent and already-resolved external facts into a
deterministic semantic payload-policy projection.

It is pure: the same inputs produce the same projection.

This component is justified because policy interpretation is independently testable and must
not depend on hidden network history.

The exact normalized input schema remains intentionally unspecified until the configuration
requirements are decomposed further.

# 5. AvailabilityPriorityCalculator

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

# 6. AvailabilityProbeAgent

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

## 6.1. Responsibility

The Agent owns ongoing execution of configured active availability observations.

It owns:

- currently requested observation channels;
- active-check cadence;
- bounded in-flight checks;
- association of each result with the current requested path identity;
- rejection of results that belong to a superseded physical observation generation;
- local diagnostics about inability to execute the observation mechanism.

It does not own:

- payload path membership;
- configured route preference;
- availability hysteresis policy outcome;
- effective route order.

## 6.2. Why Agent

Active checking is ongoing observation of an external network condition. The component
does not manage that network condition; it observes it.

Therefore it is an Agent under `design/component-model.md`, rather than a Manager.

## 6.3. Generation token

To implement `VPNG-R3.R6.R3`, an in-flight result must carry enough identity to determine
whether it still belongs to the current physical observation context.

The minimal proposed mechanism is a monotonically replaced local observation-generation
token.

The token has no routing-policy meaning.

It exists only to reject stale physical results.

No logical evidence epoch, attempt journal or replay ordering is introduced.

**Implements:**
- `VPNG-R3.R6.R3`
- `VPNG-R7.R1`

# 7. ActiveProbeDriver

**Component type:** Driver

**Implements:**
- `VPNG-R3.R6`
- `VPNG-R3.R6.R1`
- `VPNG-R7.R3.R2`
- `VPNG-R7.R5`

The Driver provides a narrow technical operation:

```text
check(concrete path observation identity, configured mechanism)
    -> technical observation result
```

It hides mechanism-specific execution from the Agent.

No concrete mechanism is selected normatively in NG3 yet.

ICMP, TCP connect, protocol-native liveness or another mechanism therefore remain possible
implementation choices until requirements or accepted constraints narrow that space.

# 8. NetworkPolicyAdapter

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

# 9. NetworkPolicyExecutor

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

# 10. Event contracts

The architecture currently needs only semantic event edges required by Engine roles.

## 10.1. Availability observation

`AvailabilityProbeAgent -> PayloadTrafficManager`

**Implements:**
- `VPNG-R3.R6`
- `VPNG-R3.R6.R1`
- `VPNG-R3.R6.R3`
- `VPNG-R7.R5`

The event must identify the logical path and carry only the bounded observation information
needed by the Manager.

The exact positive/negative evidence shape is unresolved.

No requirement currently justifies:

- durable replay;
- global revision numbers;
- a persistent event log;
- a universal ordering service.

## 10.2. Payload state publication

`PayloadTrafficManager -> observers`

**Implements:**
- `VPNG-R6.R2`
- `VPNG-R6.R4`

The Manager publishes a current projection that distinguishes desired/effective/unknown
state where that distinction affects behavior or safety.

A final system-wide status model is not yet designed.

# 11. Startup, shutdown and recovery

This pass does **not** introduce a LifecycleManager.

No accepted requirement currently proves that lifecycle orchestration needs an independent
long-lived semantic component.

Instead, the architecture records only required postconditions:

**Implements:**
- `VPNG-R4.R4`
- `VPNG-R5.R1`
- `VPNG-R5.R4`
- `VPNG-R5.R5`
- `VPNG-R7.R1`

Required orchestration semantics:

1. establish a protective network boundary before declaring payload ready;
2. create/start components only after their prerequisites exist;
3. during shutdown, quiesce ongoing activity before deleting state it depends on where
   dependency requires this order;
4. attempt cleanup of independent owned domains even if another cleanup fails;
5. preserve all material failures for observability.

Whether these steps remain procedural assembly or require a dedicated Engine is intentionally
left open until deeper lifecycle requirements demand one.

# 12. Requirement coverage in this architecture pass

| Requirement area | Architecture status |
| --- | --- |
| `VPNG-R1.R1` forwarding | represented by PayloadTrafficManager + NetworkPolicyAdapter |
| `VPNG-R1.R2` declarative operation | **not yet architected**: configuration boundary missing |
| `VPNG-R2.*` payload policy | semantic ownership represented; normalized config schema missing |
| `VPNG-R3.R1-R5,R7` path ordering/adaptation | represented by PayloadTrafficManager + AvailabilityPriorityCalculator |
| `VPNG-R3.R6.*` active observation | represented by AvailabilityProbeAgent + ActiveProbeDriver; evidence semantics incomplete |
| `VPNG-R4.*` safety | lower boundary/executor responsibilities represented; concrete kernel strategy absent |
| `VPNG-R5.R1,R4,R5` lifecycle | postconditions recorded; orchestration component intentionally absent |
| `VPNG-R5.R2,R3` recovery | represented locally by Manager/Adapter/Executor contracts |
| `VPNG-R6.R1` configured intent visibility | **not yet architected** |
| `VPNG-R6.R2,R4` payload effective state | component-level projection represented |
| `VPNG-R6.R3` system failure visibility | partial diagnostics only; **final aggregation missing** |
| `VPNG-R7.*` implementation quality | applied as cross-cutting architecture rules |

# 13. Deliberately omitted machinery

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

# 14. Design gaps that block deeper architecture

## 14.1. Configuration model

Affected requirements:
- `VPNG-R1.R2`
- `VPNG-R2.R1-R5`
- `VPNG-R6.R1`

Missing requirement detail:

- how users identify traffic classes;
- how VPN paths are referenced;
- how directions are expressed;
- how conflicting/overlapping declarations are surfaced;
- which configuration changes must be supported live.

Until this is refined, NG3 must not invent a universal normalized config schema.

## 14.2. Availability evidence semantics

Affected requirements:
- `VPNG-R3.R3-R6`

Missing requirement detail:

- what exactly constitutes negative path evidence;
- whether local probe-execution failure is path evidence or only diagnostic;
- how delayed positive evidence interacts with a check boundary;
- whether thresholds are user-configurable product semantics or implementation policy.

This gap blocks final event contract and hysteresis algorithm.

## 14.3. User-visible status aggregation

Affected requirements:
- `VPNG-R6.R1-R4`

Current components can expose local current state, but the requirements do not yet define
the final user-facing status model, aggregation ownership or presentation boundary.

No RuntimeStateManager/StatusManager is introduced until that responsibility is made
concrete.

## 14.4. Complete lifecycle ownership

Affected requirements:
- `VPNG-R5.R1-R5`

The required postconditions are clear enough to constrain components but not yet sufficient
to prove that a separate long-lived lifecycle component is necessary.

Procedural assembly remains the simpler default.

# 15. Current architecture principle

For this NG3 pass:

> If a component cannot point to a requirement, it does not enter the architecture.

And conversely:

> A requirement is allowed to remain without architecture until its semantics are concrete
> enough to justify one.
