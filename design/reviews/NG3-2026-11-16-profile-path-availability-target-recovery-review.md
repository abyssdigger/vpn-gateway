# VPN-GATE NG3 — Profile/Path Availability Target Recovery Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-probe-target-normalization-40m`

## Recovered historical semantics

Recovered prior-chat context establishes the intended availability configuration semantics more
precisely than the previous checkpoint.

Historical product model:

```text
bare icmp
    -> derive one path-specific target from existing Profile/path topology semantics

icmp/<explicit-ip>
    -> use exactly that explicit target
```

The availability criterion belonged to a Profile/path use, not to a physical interface in
isolation.

Therefore:

```text
wg0 IFF_UP
    !=
wg0 AVAILABLE for every policy/Profile context
```

The same physical interface may be useful for one policy/profile path and unusable for
another.

NG3 keeps this semantics without importing NG2's `Profile` type as a required model. The
neutral NG3 term is:

```text
availability subject
    = policy/traffic context + logical VPN path
```

## Requirement corrections

### VPNG-R3.R6.R1

Evidence identity is now subject-specific.

A physical interface/endpoint is not sufficient availability identity.

### VPNG-R3.R6.R3.R1

The user-defined check criterion applies to one availability subject, not globally to one
interface.

### VPNG-R3.R6.R3.R2

Accepted target semantics:

```text
external target explicit
    -> preserve exactly that IPv4

external target omitted
    -> deterministically derive one IPv4 from already accepted
       subject/path/Device/interface/binding/peer topology semantics

runtime probe demand
    -> always contains one concrete IPv4 target
```

There is no universal global default probe IP.

If the available topology/semantics cannot yield one unambiguous target, VPN-GATE must not
silently substitute an arbitrary address.

## Architecture

### AvailabilityTargetCalculator

A pure Calculator performs target normalization before probe runtime.

Inputs:

```text
availability subject
mechanism
explicit target?
accepted policy/path/device/binding/peer topology facts
```

Output:

```text
concrete IPv4
| unresolved
| ambiguous
```

Rules:

- explicit target is returned unchanged;
- omitted target is derived mathematically from existing subject-specific semantics;
- no external/global fallback IP is invented;
- different availability subjects may derive different targets even if they share one
  physical interface;
- unresolved/ambiguous derivation prevents runtime probe demand and remains diagnostic.

Exact Device/integration-specific formulas are implementation specializations behind this
accepted Calculator contract.

They are deliberately not promoted into product requirements because the accepted product
semantics are the deterministic subject-specific derivation rule, not a fixed cross-protocol
address table.

Each supported integration must provide implementation evidence that its derivation formula
satisfies the contract.

### Probe runtime boundary

`AvailabilityProbeAgent` and `ActiveProbeDriver` receive only normalized requests:

```text
AvailabilityProbeIntent:
    availability_subject_id
    logical_path_id
    mechanism
    target = concrete IPv4
```

They do not know whether the target was explicit or derived.

### Hysteresis boundary

Availability hysteresis state is per availability subject, not per physical interface.

Physical observation execution may still share/deduplicate equivalent lower probe planes
where mechanism/path/target are identical, but resulting evidence is attributed to the
correct subject(s) before policy adaptation.

## First-release constraint

The previously accepted first-release constraint remains unchanged:

- supported mechanism: ICMP echo;
- TCP/UDP/HTTP remain future extensions.

The recovered compact spellings such as `interface_balancing = "icmp"` and
`"icmp/<ip>"` are historical UI examples. NG3 does not need to freeze that exact field
name/string grammar to close the semantic architecture.

## Closure decisions

**ACCEPT CLOSURE** for:

- `VPNG-R3.R6.R1`;
- `VPNG-R3.R6.R3.R1`;
- `VPNG-R3.R6.R3.R2`;
- `VPNG-R3.R6.R3`;
- `VPNG-R3.R6`;
- parent `VPNG-R3`.

The exact per-Device derivation formula remains implementation/evidence work, not an open
architecture semantic question.

## Simplification review

This recovery does not justify:

- a global default target service;
- target selection inside ProbeAgent/Driver;
- target semantics inside PayloadTrafficManager;
- one availability state per interface;
- a generic probe plugin framework.

One pure Calculator plus existing normalized contracts is sufficient.

## Verdict

**PASS — RECOVERED HISTORICAL SEMANTICS RESTORED.**

The default-target gate is resolved at the correct abstraction level.
