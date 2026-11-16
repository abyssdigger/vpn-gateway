# VPN-GATE NG3 — Transition tips from NG2 and earlier

**Status:** normative design-review checklist for NG3  
**Evidence companion:** design/NG3/experiment-evidence-transition.md

Purpose: before inventing a requirement, state, component or mechanism, check what the project
has already learned. A historical fact constrains design; it does not automatically restore
the historical architecture.

# 1. Requirements / architecture

## TIP-R1 — History is evidence, not authority

Use old material in this order:

    old product meaning -> candidate requirement evidence
    old experiment      -> technical constraint/evidence
    old component       -> architecture candidate only

Never derive a requirement merely to preserve an old mechanism.

## TIP-R2 — Recover Purpose/Reason first

If historical behavior has no natural, unambiguous Purpose/Reason under the current tree,
stop and escalate. Do not repair the causal gap with architecture wording.

## TIP-R3 — Superseded design can leave valid facts

EXP-013/016 are examples: their Linux/FIB facts remain evidence even though the architecture
that originally needed them was removed.

## TIP-R4 — PREPARED is not evidence

Current examples: multi-path inbound return pinning, MTU/MSS policy, target-systemd lifecycle,
and Debian 13 confirmation of EXP-026.

## TIP-R5 — Preserve ownership semantics, not superseded component vocabulary

The recovered NG2 snapshot used an older vocabulary where `Engine` and `Executor` were not
generic architectural categories. Current NG3 has since accepted
`design/component-model.md`, where Engine is a component family and Executor is Machinery.

Therefore:

- do not use the NG2 taxonomy to reopen the current component model;
- do reuse its ownership boundaries when they still apply;
- classify recovered responsibilities using the **current** NG3 vocabulary.

Historical names such as `AvailabilityProbeManager` or `NetworkRulesAdapter` are evidence
about responsibility boundaries, not mandatory current class names.

## TIP-R6 — Components exchange semantic contracts, not lower implementation detail

Across a boundary, expose the meaning needed by the consumer.

Prefer:

```text
desired semantic state
current semantic observation
verified result
```

over leaking shell commands, route metrics, nft syntax or lower state that the consumer does
not need.

This is especially important when recovering old code-level contracts: a concrete CODE type
can be useful evidence of meaning without requiring the same serialized/API shape in NG3.

## TIP-R7 — Async boundaries follow ownership, not fashion

Events are appropriate between independent long-lived owners.

Calculators, Adapters, Executors and Drivers may be invoked synchronously by their owner when
there is no useful asynchronous ownership boundary.

Do not convert every internal calculation into an Event merely because the old runtime had an
event environment. Conversely, do not collapse an actual independent owner into a synchronous
helper merely to reduce message count.

# 2. Human-facing configuration

## TIP-C1 — Config is user policy, not Linux mechanics

Do not require users to provide ifindex, route metrics, table/rule priorities, current kernel
object identities or derived aggregate quota.

If a value is derivable and not a real user choice, derive it.

## TIP-C2 — Device and Profile are distinct

    Device  = transport capability: how traffic can travel
    Profile = network need: where/how user traffic should travel

A Device may serve multiple Profiles. A Profile may use multiple Devices.

## TIP-C3 — Stable IDs are user identities

Device/Profile IDs are stable opaque references. Runtime interfaces are discovered objects,
not user identities.

## TIP-C4 — Explicit administrative state, no hidden meaning

Recovered principles:

- enabled is explicit;
- disabled object may be a minimal placeholder;
- known disabled reference is valid;
- unknown reference is an error;
- boolean is a real boolean;
- enum has one canonical spelling.

## TIP-C5 — Reject ambiguity instead of repairing it

Examples: host bits in strict CIDR, duplicate ordered references, ambiguous selectors,
invalid/reversed ranges, guessed unsupported grammar.

## TIP-C6 — Order matters only where declared policy

Semantic order exists in Profile.device_order and Device.expected_interfaces.
Destination list order is not routing policy.

## TIP-C7 — Semantics and prototype spelling are separate layers

Recovered semantics may be normative while final human syntax remains open.

Current examples:

- Device NAT meaning none / masquerade is recovered;
- Device envelope is restrictive intersection with Profile policy;
- transport publication belongs to Device/transport boundary;
- old envelope/publication TOML is prototype evidence, not automatic NG3 schema v1;
- timing/unit field names remain a later human-facing grammar decision.

# 3. Device and binding

## TIP-D1 — Device describes expected capability, not runtime state

expected_interfaces means endpoints are expected/discovered, not created or guaranteed by
the config object.

## TIP-D2 — Discovery is demand-driven

Active Device = enabled AND referenced by at least one enabled Profile.

## TIP-D3 — Quota belongs to each selector

Exact selector has intrinsic quota 1. Prefix selector has explicit positive quota.
Total Device capacity is derived.

## TIP-D4 — Device policy can narrow, never widen Profile permission

    effective permission = Profile permission INTERSECT Device envelope

NAT/publication are transport concerns, not availability or Profile identity.

## TIP-B1 — Events are wakeups, not truth

    Netlink/event/timer -> reconcile
    fresh authoritative snapshot -> decision

Periodic/full reconciliation covers lost events.

## TIP-B2 — Valid absence is not observation failure

A trustworthy snapshot saying “interface absent” is lifecycle state.
Failure to obtain/parse inventory means actual state is unknown and must not be treated as
absence.

## TIP-B3 — Current concrete identity is (ifname, ifindex)

Same-name/new-ifindex is a new endpoint generation. Numeric ifindex is still not a durable
historical generation token because reuse is possible.

## TIP-B4 — Discovery is not admission

Observed matching endpoint != admitted selector slot != usable Profile path.
Over-quota candidates may be observable but must not create routing, payload permission or
availability subjects.

## TIP-B5 — Preserve survivors

Existing admitted survivors retain relative order. New candidates append. Over-quota
promotion follows committed first-observed order; simultaneous fresh candidates retain
kernel-snapshot order with ifindex tie-break. Lexical ifname order is not policy.

## TIP-B6 — Logical path identity belongs to the configured slot

    logical path = Device ID + selector position + stable quota slot

Current concrete endpoint is mutable binding state, not the logical identity.

## TIP-B7 — Apply success is not commit

    observe -> plan -> apply -> fresh observe -> verify -> commit

A successful mutation command does not by itself establish committed binding/runtime truth.

# 4. Profile

## TIP-P1 — Profile is an independent routing/payload-policy domain

It is not a VPN interface, peer, session, route metric, probe target or Linux-rule container.

## TIP-P2 — Zero paths does not delete Profile

An enabled Profile with zero current paths still owns its destinations and must fail closed
rather than fall through to ambient/main routing.

## TIP-P3 — Profile chooses Devices; binding yields paths

Human policy names ordered Devices. Runtime normalization expands valid Device bindings into
ordered logical paths.

## TIP-P4 — Direction is payload semantics

Direction says who may initiate useful flows in the Profile domain; it is not VPN-session or
probe direction.

## TIP-P5 — Remote prefixes have one semantic

ordinary -> VPN NEW: classify by remote destination.
VPN -> ordinary NEW: first restrict by actual ingress Device/path, then classify by remote
source.

## TIP-P6 — Release 1 rejects multi-path inbound/bidirectional at config normalization

Historical EXP-014 did not prove remote-initiated multi-path return-path pinning.

The accepted first-release constraint is now explicit:

```text
direction = outbound
    -> multi-path allowed

direction = inbound | bidirectional
    -> configured maximum eligible logical-path capacity must be <= 1
```

Validation uses configured capacity from currently enabled referenced Devices and selector
quotas, not the number of interfaces that happen to be present at runtime.

Do not weaken this to "currently one bound path is enough"; that would allow the unsupported
topology to appear later through ordinary interface discovery.

Multi-path inbound/bidirectional is a Release 2 candidate and requires explicit requirement
revision plus EXP-014 or equivalent return-path evidence.

# 5. Bootstrap / lifecycle

## TIP-L1 — Startup success is safe appliance readiness, not VPN connectivity

Historical NG1 meaning:

    startup success =
        managed network domain exists
        + protective state exists
        + runtime is running
        + required postconditions verified

Missing VPN interfaces/processes are binding state, not automatically daemon startup failure.

## TIP-L2 — Cleanup stale owned state before trusting new config

Historical ordering:

    LOCK -> CLEANUP -> LOAD/VALIDATE -> APPLY -> RUN

Invalid new config must not prevent cleanup/containment of stale old state.

## TIP-L3 — Cleanup failure blocks unsafe startup

Do not continue from an unverified baseline just to make startup progress.

## TIP-L4 — Stop during STARTING must contain partial forwarding

Once a phase may have created forwarding-capable state, a stop request must cleanup/contain
rather than abandon partial state.

## TIP-L5 — Normal ownership and teardown containment are different

External VPN process lifecycle may be administrator-owned, but owned managed-domain teardown
still must not leave resources indefinitely preventing cleanup.

# 6. Routing / safety

## TIP-N1 — Owned forwarding needs a terminal safety decision

Experiments showed ambient FORWARD policy can leak traffic. Managed forwarding must end in a
product-controlled allow/deny decision.

## TIP-N2 — Route presence and metric are not health

A route/interface/process may remain present while payload is dead. Metric expresses
preference among eligible paths, not liveness.

## TIP-N3 — Pure priority permutation is make-before-break; the hole is emergent

EXP-027 proved the move primitive:

```text
add duplicate at a currently unused metric
delete only the old copy
```

All eligible paths remain represented.

The free metric is **operationally inferred**, not a semantic/config/runtime "hole" object.

Important edge case from EXP-027:

```text
all-live steady state
    -> no materialized/configured gap is required
    -> the next unused ordinary metric is sufficient for the first move
```

Do not over-specify a permanently reserved N+1 layout merely because one transaction needs
working space.

Do not reintroduce staging tables or delete-as-scratch without a new requirement.

## TIP-N4 — Route-priority mutation is serialized only per affected Profile/routing domain

For one Profile/routing domain:

- one priority transaction runs at a time;
- a half-completed transaction is not cancelled;
- its plan completes through final verification;
- newer desired orders may be coalesced to the latest desired state;
- after commit/verification, the next transaction starts from freshly observed materialized
  state;
- replay of every intermediate availability transition is unnecessary.

Unrelated Profiles need not be globally serialized merely because one Profile is moving
metrics.

## TIP-N5 — Structural transition is a different class

Membership/filter/NAT/direction changes are not covered by the priority-only proof and may
need restrictive fail-closed convergence.

# 7. Availability / probes

## TIP-A1 — Binding presence is not availability

WireGuard and OpenConnect experiments independently prove interface/process presence does not
guarantee usable payload path.

## TIP-A2 — Availability subject is (Profile, logical path)

One physical interface may be good for one Profile and bad for another.

## TIP-A3 — Availability changes priority only

It must not change Profile destinations, direction, Device membership, binding eligibility
or structural Profile existence.

## TIP-A4 — User defines the practical criterion

First release is ICMP.

    icmp/IP -> exact target
    bare icmp -> deterministic Profile/path-specific target derived above probe runtime

No universal public default probe IP.

## TIP-A5 — Preserve physical-fact versus policy-interpretation ownership, not old event names

The NG2 snapshot used `AvailabilityGoodNews`, `AvailabilityTick` and
`AvailabilityPriorityChannel` after removing an older window/evidence hierarchy.

Current NG3 has re-derived the boundary as normalized
`positive | negative | no_evidence` plus bounded confirmation state.

The transferable rule is:

```text
probe side
    -> reports relevant physical observation

payload/Profile owner
    -> decides what that observation means for priority
```

Do not restore GoodNews/Tick, attempt IDs, windows, epochs or replay merely because they once
existed in code/design. Use the current requirement-derived evidence contract unless a new
requirement shows it is insufficient.

## TIP-A6 — Shared lower network machinery must preserve semantic ownership

Payload rules and probe rules may converge through one lower network-policy Adapter/Executor,
but they remain distinct semantic owners/scopes.

Requirements:

- probe-path safety rules cannot silently widen payload permission;
- payload rules cannot accidentally erase required probe isolation;
- owner conflicts are detected before unsafe physical application;
- sharing one lower Adapter is not permission to merge owner policy.

A separate physical ProbeRulesAdapter is not justified merely to keep semantic owners
separate; ownership can be represented in the desired-state contract.

## TIP-Q1 — A path-specific probe must not escape through an alternate Device

A successful check through the wrong path is invalid evidence.

## TIP-Q2 — INPUT meta skuid is not a usable receiving-socket discriminator

EXP-024 explicitly rejected that mechanism.

## TIP-Q3 — Conntrack-carried process identity is viable but generation-sensitive

EXP-024 target-confirmed:

    OUTPUT process selector -> dedicated ct mark -> reverse INPUT recognition

This allows selective probe isolation without global local default-DROP.

## TIP-Q4 — Interface generation does not freshen conntrack identity

EXP-025 target-confirmed stale inheritance:

    interface replacement + new ifindex + rebuilt RPDB/nft
        != fresh conntrack-carried probe identity

An explicit probe-generation invalidation boundary is required if that mechanism is used.

## TIP-Q5 — EXP-026 is a candidate, not target proof yet

Privileged CI proves mark-filtered cleanup can remove probe-class state while preserving
different-mark control state and restoring NEW+mark-set. Debian 13 confirmation remains open.

## TIP-O1 — Physical success and publication success are separate postconditions

A verified successful mutation must not be blindly repeated merely because publication of the
resulting state failed.

The owner should retain enough current verified projection to retry publication separately.

```text
apply + verify succeeded
publish failed
    -> retain verified state
    -> retry publication
    -> do not repeat physical action solely for the publisher failure
```

Unexpected internal faults remain errors; they must not be converted into fake successful
publication.

## TIP-O2 — Audit repairs drift and can republish; it should not rewrite matched state

For an authoritative owner:

```text
observe
  -> MATCHED
       -> no physical mutation
       -> publish/republish current projection if needed

  -> NOT MATCHED
       -> reconcile
       -> fresh observe
       -> verify
       -> publish
```

Audit cadence is a lifecycle policy/implementation parameter unless a product requirement
makes recovery latency user-visible.

# 8. Backend / evidence discipline

## TIP-F1 — Backend evidence stays backend-specific

iptables-nft facts do not automatically prove native nftables behavior, and vice versa.

## TIP-F2 — Per-table atomicity is not whole-policy atomicity

Filter/NAT/routing safety still requires explicit sequencing and verification.

## TIP-F3 — Numeric nft iif/oif is current-generation enforcement, not durable identity

Rendered nft text may also replace live numeric operands with symbolic ifname, so verifier
logic must preserve exact generation meaning independently.

## TIP-E1 — Cite the exact claim

Do not use a broad experiment as evidence for behavior it did not test.

## TIP-E2 — Negative findings constrain architecture

A target-confirmed failure mode such as EXP-025 is not “failed evidence”; it is an
implementation constraint.

## TIP-E3 — Re-run only when the claim materially changes

Re-run when backend/environment/topology/claim strength changes, or an unproven gate becomes
blocking. Do not re-run merely because component names changed.

# 9. Mandatory review questions

Before accepting a new decomposition or component responsibility ask:

1. Is this product semantics or an old implementation detail?
2. Is Purpose/Reason explicit and unambiguous?
3. Does old evidence already prove or disprove the technical assumption?
4. Are discovery, admission, binding and availability being kept distinct?
5. Are valid absence and unknown observation being kept distinct?
6. Is transient kernel identity being promoted into product identity?
7. Is health being allowed to rewrite structural policy?
8. Is user config being added for a derivable value?
9. Is ambiguous input being silently accepted?
10. Is prototype syntax being promoted without explicit human acceptance?
11. Is PREPARED/CI-only evidence being treated as target proof?
12. Is an old component retained only because it existed?
13. Does a new state/queue/history/replay mechanism serve a concrete supported scenario?
14. Does every failure mode preserve fail-closed behavior for managed traffic?
15. Is the proposed evidence the cheapest sufficient proof of the exact claim?

If a proposed change fails one of these questions, return to the earliest insufficient phase.
