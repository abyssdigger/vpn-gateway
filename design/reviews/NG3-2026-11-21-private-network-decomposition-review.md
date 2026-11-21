# NG3-2026-11-21 Private-network decomposition review

## Scope

Reviewed baseline:

- branch: `ng3-cd-private-network-decomposition-30m`
- candidate commit: `3ee7f4030995590b33da9270bc55f28c4809c0eb`
- structured architecture: `design/NG3/structured-architecture.md`
- source architecture: `design/NG3/architecture.md`
- component model: `design/component-model.md`

The review asks two questions:

1. how the `Private network` Space should nest components;
2. how the existing flat `NetworkPolicyEnforcer` decisions should be reorganized without
   changing their accepted semantics.

No product requirement or executable behavior is changed by this review.

## Decomposition criteria

The candidate hierarchy was evaluated primarily against:

1. **independent external API demand** — a component with clients outside its proposed parent
   should not be hidden under that parent unless a deliberate deep `@` is justified;
2. **mandatory parent coherence** — a component whose correctness/lifecycle is meaningful only
   inside a parent contract is a strong subcomponent candidate;
3. **shared dependency pressure** — machinery needed by several peer parents should be lifted
   to their nearest common level instead of being assigned to the first caller;
4. **independent state/lifecycle meaning** — separately observable or controllable state is a
   reason to keep a sibling boundary;
5. **Adapter visibility** — internal realization behind an Adapter should not be flattened
   into peer Space residents merely because the implementation has separate files/classes.

## Hierarchy variants

### Variant A — flat Space

Shape:

```text
Private network
    @NetworkPolicyAdapter
    NetworkPolicyEnforcer
    NetworkPolicyLayoutCalculator
    RoutingDriver
    NftBackend
    @ForwardingGate
    @VPNPathAdapter
    ...
```

Strengths:

- mechanically honest about implementation pieces;
- no artificial ownership is invented.

Weaknesses:

- destroys the architecture value of the Adapter boundary: internal realization becomes a
  peer of the boundary that is supposed to hide it;
- does not express mandatory coherence between Adapter and Enforcer;
- makes the Space resident list grow with lower implementation granularity;
- encourages callers to treat internal machinery as stable Space-level architecture.

Assessment: useful as an inventory, poor as architecture.

### Variant B — all-in-one PrivateNetworkAdapter

Shape:

```text
Private network
    @PrivateNetworkAdapter
        NetworkPolicy...
        VPNPath...
        ForwardingGate...
        ...
```

Strengths:

- smallest external surface;
- no deep `@` if every operation is proxied through the facade.

Weaknesses:

- duplicates the Space abstraction itself: the Space API is already the union of its resident
  APIs;
- combines unrelated semantic boundaries (network policy, endpoint binding, root forwarding
  control) only because they touch the same environment;
- forces lifecycle/startup clients to route a safety-gate operation through a policy Adapter;
- turns replacement of one independent boundary into replacement/review of a God Adapter.

Assessment: compact but semantically over-composed.

### Variant C — Adapter-centric tree

Shape:

```text
Private network
    @NetworkPolicyAdapter
        NetworkPolicyEnforcer
            ForwardingGate
            lower machinery
    @VPNPathAdapter
```

Strengths:

- preserves the central policy Adapter boundary;
- captures the strong Adapter -> Enforcer coherence.

Weaknesses:

- `ForwardingGate` has independent clients outside `NetworkPolicyEnforcer`:
  startup, stop, managed-domain lifecycle and recovery/containment paths;
- honest rendering therefore requires a deep `@ForwardingGate`, which is exactly the review
  signal introduced by the structured notation;
- proxying those clients through `NetworkPolicyAdapter` would create a false policy
  dependency.

Assessment: better than flat/monolithic, but the gate placement is wrong.

### Variant D — selected boundary/coherence hybrid

Shape:

```text
Private network
    @NetworkPolicyAdapter
        NetworkPolicyEnforcer
        [lower policy realization subcomponents as justified]
    @VPNPathAdapter
    @ForwardingGate
        ForwardingGateDriver
```

Rationale:

- each direct resident has independently demanded API outside its proposed parent;
- `NetworkPolicyEnforcer` has no architectural reason to be called around the Adapter and is
  strongly defined by the Adapter-supplied desired-state contract;
- `ForwardingGate` is shared by policy convergence and lifecycle/safety clients and therefore
  belongs at the common Space level;
- `VPNPathAdapter` has an independent observation/binding contract and does not depend on
  policy convergence.

Assessment: best fit to the current component model and the new Space/API notation.

## Current implementation pressure versus architecture boundary

The Python reference still contains direct lower calls that should not define the architecture
surface:

- `linux_availability_cycle.py` constructs `LinuxProbeRoutingBackend`,
  `LinuxStructuralPolicyBackend` and route-priority machinery directly;
- startup/stop/alpha code constructs `LinuxForwardingGateDriver` and calls the one-shot gate
  convergence helper directly.

These are useful evidence of current implementation composition, but they do not justify deep
Space-level APIs when the accepted architecture already describes the shared
`NetworkPolicyAdapter / Enforcer` boundary.

The structured architecture should expose the semantic boundary first and later use its
deep-`@` markers to decide which reference-code shortcuts deserve refactoring.

## Cross-Space finding in the old NetworkPolicyAdapter chapter

The flat `NetworkPolicyAdapter` section also owns
`Host-side Device server publication mapping — EXP-052`.

That contract explicitly manages host-side state outside the managed network domain. Under
the new Space model, keeping it inside the Private-network `NetworkPolicyAdapter` would
require the same component to be represented in another Space as `<partial>`.

The candidate therefore does **not** copy that sub-contract under the Private-network Adapter.
Its final placement is deferred until the host/transition Spaces are populated.

This is not a removal of the accepted publication behavior; it is a decomposition finding.

## NetworkPolicyEnforcer decision-organization variants

### Option 1 — mechanism-first

Example groups:

- routing/RPDB;
- nft;
- forwarding gate/sysctl;
- Linux platform constants.

Strength: technical facts are locally easy to find.

Weakness: safety and freshness invariants are duplicated across mechanisms; semantic
transition classes disappear; lower platform facts incorrectly look like Enforcer
responsibilities.

Verdict: rejected for the structured component description.

### Option 2 — execution-pipeline-first

Example:

```text
observe -> compare -> plan -> gate -> mutate -> verify -> recover
```

Strength: excellent procedural readability for one structural transaction.

Weaknesses:

- pure-priority and structural transitions have materially different proofs;
- desired-state compilation and lower observation formats become tempting to pull into the
  Enforcer merely because they occur before/inside the sequence;
- the model becomes procedural rather than responsibility-oriented.

Verdict: useful inside one transition description, insufficient as the top organization.

### Option 3 — responsibility first, transition branches second — selected

Order:

1. common Enforcer contract;
2. explicit transition classification;
3. pure-priority branch;
4. structural branch and dependency on the sibling `ForwardingGate`;
5. exact-before-release/failure postconditions;
6. lower technical boundary.

This keeps common invariants exactly once, then introduces the two different safety proofs
only where they diverge.

It also allows source material to move to its natural owner:

- complete desired-state projection -> Adapter/Calculator side;
- Linux JSON/argv representation -> Reader/Driver/Backend side;
- `ForwardingGate` primitive -> separate Space resident;
- administrative payload containment -> separate future operational contract.

Verdict: selected.

## Findings

### F1 — root gate scope must remain explicit

The candidate structural summary can be misread as if verified
`ForwardingGate=DISABLED` made every nft mutation safe. The source architecture explicitly
states that the root forwarding gate protects routed payload only and does not protect local
`stack_input/stack_output` traffic.

**Decision:** accepted.  
**Resolution:** fixed in the candidate architecture by adding an explicit local-policy safety
qualification under the structural branch.

### F2 — Enforcer must not own runtime retry/reconciliation

The heading `Failure and recovery` risks conflating one Enforcer invocation with later
Manager audit/retry responsibilities under `VPNG-U005-R5.R2/R3`.

**Decision:** accepted.  
**Resolution:** fixed by renaming/rewording the decision as a per-invocation failure
postcondition and explicitly leaving later retries to the caller/Manager from fresh state.

### F3 — deterministic lower allocation is a real Adapter subcomponent candidate

`network_policy_layout.py` is a pure deterministic Calculator over semantic owner demand and
injected platform resource space. The flat architecture explicitly places allocation below the
Adapter and upper product policy has no reason to know table/RPDB/metric/nft numeric layout.

**Decision:** accepted.  
**Resolution:** fixed by adding `NetworkPolicyLayoutCalculator` under
`NetworkPolicyAdapter`. Direct reference-code use outside the Adapter is treated as
implementation-composition debt, not Space API.

### F4 — host publication sub-contract crosses the Space boundary

The EXP-052 host mapping does not live in `Private network`.

**Decision:** accepted.  
**Resolution:** deferred until `STACK-HOST transition` / host Spaces are populated. Re-entry
condition: first structured pass over the host-side publication path. Until then it must not be
silently attached to the Private-network Adapter and must remain visible as a cross-Space
finding.

### F5 — lower reference code still bypasses the selected semantic boundary

Availability and lifecycle reference slices directly construct lower Backends/Drivers.

**Decision:** accepted.  
**Resolution:** deferred. Re-entry condition: executable-code alignment after the structured
Private-network component tree is accepted. No code refactor is justified before that
architecture is stable.

## Verdict

**PASS with accepted fixes F1-F3 and scoped deferrals F4-F5.**

Variant D and decision-organization Option 3 are internally coherent with the current
component model and preserve the accepted flat-architecture semantics while making two
previously hidden boundary problems visible.


## Fix verification

Reviewed fixed baseline: `b4add2c66a9f46a51c490e14a23ffd5abd3473c4`.

Verified:

- F1: the structured Enforcer now explicitly states that the root gate protects routed IPv4
  forwarding, not local INPUT/OUTPUT owner classes;
- F2: the Enforcer failure rule is now per-invocation and leaves later retry/reconciliation to
  caller/Manager from fresh state;
- F3: `NetworkPolicyLayoutCalculator` is now an internal Adapter subcomponent and is not
  exported as Space API;
- no nested subcomponent in the selected tree carries `@`;
- `ForwardingGate` remains a direct resident because its API has independent lifecycle/safety
  callers;
- `VPNPathAdapter` remains a direct resident because its endpoint-observation/binding API is
  independent of policy convergence.

Deliberately not placed in this pass:

- `ActiveProbeDriver` and other probe-execution machinery whose final Space ownership is not
  established by the reviewed boundary;
- individual desired-state compilers beyond the already clear lower resource-layout
  Calculator;
- the EXP-052 host-side publication owner, pending the first structured host/transition-space
  pass.

These omissions keep the current structured document honest rather than filling its tree from
file/module proximity.

**Final verdict on fixed baseline: PASS.**


## Structured-addenda follow-up

Reviewed baseline: `1d814a6981f6b6a16f526a0061f86479282a8ae4`.

The previously accepted Enforcer decomposition has been re-expressed under the flat
component-addenda methodology:

- accepted Enforcer decisions remain in `Architectural decisions`;
- already-resolved migration notes were removed as duplicate prose;
- the still-open administrative containment composition moved to `Findings`;
- the finding preserves the earlier decision that public containment is not a structural
  Enforcer mode and that `ForwardingGate` alone cannot satisfy the full contract.

No parent/child relationship, Space API or safety invariant changed.

**Follow-up verdict: PASS.**


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005-R5.R2` -> `VPNG-M001-R1.R1.R2`

The original IDs in the historical body are intentionally preserved.
