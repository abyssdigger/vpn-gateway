# VPN-GATE NG3 — transport endpoint provenance and Release-1 postponement review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-endpoint-provenance-35m`

## Review unit

Future transport-endpoint provenance for one current logical VPN path, its Release-1
postponement, and the dependency boundary for endpoint-dependent convenience functions.

This unit deliberately does **not** select named-endpoint configuration syntax and does not
implement endpoint-specific firewall policy.

## Requirements

### VPNG0001-R1.R3.R5

**Purpose / Зачем**

The accepted purpose is to make common configuration and operation simpler where a logical
reference to the VPN endpoint is more useful than repeatedly writing its IP address:
availability defaults, endpoint-scoped filtering and other future consumers.

**Actor / Кто**

`VPN-GATE`.

**Action / Что**

Determine one transport endpoint/peer for the exact current concrete data-plane endpoint and
associate that fact with the current path-binding generation.

**Trigger / Когда**

During discovery/update of a current logical VPN path when the accepted supported-integration
discovery contract supplies sufficient observable evidence.

The requirement does not equate the transport endpoint with interface name, selector slot,
inner point-to-point peer or probe target.

### VPNG0001-R1.R3.R5.C1

The Release-1 limitation is accepted because reliable transport-endpoint provenance is not
yet proved for every supported integration and core R1 routing/binding plus explicit-target
availability do not require it.

Effective product envelope:

- a path without transport provenance remains usable for functions that do not need it;
- no first-release integration is required merely by R1 to discover a transport peer;
- a provenance-dependent function must not guess or silently broaden its semantics.

### VPNG0001-R1.R3.R5.C1.R1

The constraint shifts no hidden discovery work to the administrator. Instead VPN-GATE must
make the unsupported dependent function explicit. If a function already supports an
explicit IP alternative, that explicit form remains usable without endpoint discovery.

This is compatible with the existing availability contract:

- explicit ICMP target is preserved exactly;
- omitted target still uses an accepted deterministic derivation formula;
- when a particular formula requires transport provenance and it is unavailable, that
  derivation is unresolved and diagnostic rather than guessed.

## Scenario

An OpenConnect-like integration can create several `tunN` interfaces from one common
interface-name family while each userspace session connects to a different remote VPN
server.

The user may later want to express policy such as:

```text
named endpoint "uryupinsk"
    -> current VPN session whose transport peer is endpoint X

availability
    -> default probe derived from that endpoint when the integration says this is valid

future firewall
    -> apply a rule only to traffic traversing that endpoint/path
```

A runtime `tun17` name or stable logical slot is not sufficient to identify which remote
transport peer created that concrete interface.

## Components

### VPNPathAdapter

**Implements:**
- `VPNG0001-R1.R3.R5`
- `VPNG0001-R1.R3.R5.C1.R1`

**Constrained by:**
- `VPNG0001-R1.R3.R5.C1`

The existing Adapter remains the technical observation boundary. A supported integration may
enrich its exact current `PathBinding` with confirmed transport provenance.

No new long-lived Engine is justified.

### PayloadTrafficManager / current binding projection

The stable logical identity remains:

```text
Device + selector position + stable slot
```

Transport provenance is not added to `LogicalPathId`. It is scoped to the exact current
concrete binding and becomes stale when that binding is replaced.

### AvailabilityTargetCalculator

It may consume confirmed provenance only when an accepted integration-specific derivation
formula requires it. It does not discover the peer itself.

### Future endpoint-scoped firewall compiler

This review records only the dependency boundary: such a compiler may consume confirmed
logical endpoint/path provenance. Its user grammar, ordered firewall semantics and lower
materialization remain separate requirement/design work.

## Interactions

```text
integration-specific observation/onboarding fact
        |
        v
VPNPathAdapter
        |
        +--> exact current PathBinding
        |
        +--> optional confirmed transport provenance
                    |
                    +--> availability target derivation, when required
                    +--> future endpoint-scoped filtering, when accepted
                    +--> status/diagnostics
```

No consumer may infer provenance independently from `tun*`, slot number or inner peer
state.

## External environment

Relevant external facts are integration-specific:

- generic Linux interface/netlink inventory;
- protocol/process/session control information where available;
- administrator/bootstrap metadata where that is the accepted integration contract.

The architecture does not prescribe one universal source because EXP-039 disproves the
necessary generic-TUN assumption.

## EXP-039 evidence

Privileged GitHub Actions run `43897774703` passed.

A real userspace-held TUN interface:

- reported `POINTOPOINT`;
- exposed its configured inner/network-layer peer;
- retained identical parsed `ip -j -d link` and `ip -j addr` state while the same
  userspace process changed its separate transport socket peer from
  `198.51.100.39` to `203.0.113.39`;
- contained neither transport peer address in generic interface discovery.

Therefore:

```text
generic point-to-point TUN discovery
    !=
transport endpoint provenance
```

The result is sufficient to reject a generic implementation based only on point-to-point
interface state. Integration-specific mechanisms still require their own evidence when they
are implemented.

## Constraint lifting

The Release-1 constraint is local and does not narrow core VPN-path usefulness:

```text
no provenance
    -> routing/binding still valid
    -> explicit-target availability still valid
    -> provenance-dependent convenience unavailable/diagnostic
```

It must not be lifted into a claim that endpoint discovery is impossible in later releases or
for protocol-specific integrations.

## Simplification review

Rejected as unnecessary in this unit:

- persistent endpoint-provenance history;
- global binding-generation counter;
- generic peer-discovery daemon;
- named-endpoint config grammar;
- firewall AST changes;
- protocol-independent inference from `IFF_POINTOPOINT`;
- forcing all R1 integrations to expose peer metadata.

The smallest accepted model is one optional current fact supplied by the existing integration
observation boundary.

## Evidence/closure verdict

- requirement Purpose is explicit and supported by the accepted parent scope;
- actor, action and trigger are explicit;
- Release-1 constraint has a causal Reason and explicit compensation behavior;
- architecture references all three new R/C nodes;
- EXP-039 rejects the unsafe generic-discovery shortcut;
- no R1 implementation depends on the postponed capability;
- no named-endpoint syntax has been prematurely frozen.

**Verdict: PASS.** The three new nodes may be marked `[closed]`; the future capability is
architecturally closed while its Release-1 implementation remains intentionally constrained.
