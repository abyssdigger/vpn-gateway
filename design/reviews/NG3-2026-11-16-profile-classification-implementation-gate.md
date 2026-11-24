# VPN-GATE NG3 — Profile traffic classification implementation gate

**Cycle:** `ng3-design-cycle-20261116-post-closure-implementation-readiness-40m`  
**Review unit:** pure outbound/inbound Profile prefix classification

## Scope

Implement pure classification over accepted `PayloadProfileRequest` values.

Outbound NEW flow:

```text
remote destination
    -> most-specific applicable Profile
```

Inbound NEW flow:

```text
actual ingress LogicalPathId
    -> restrict Profiles to those containing that path
    -> remote source
    -> most-specific applicable Profile
```

No packet processing, conntrack, firewall or Linux rule generation is part of this unit.

## Requirements

Primary:

- `VPNG-R2.R1`;
- `VPNG-R2.R1.R1`;
- `VPNG-R2.R1.R2`;
- `VPNG-R2.R2`;
- `VPNG-R2.R3`;
- `VPNG-R2.R3.R1`;
- `VPNG-R2.R3.R2`;
- `VPNG-R2.R3.R3`;
- `VPNG-R2.R5`;
- `VPNG-R2.R5.R1`;
- `VPNG-R4.R1`.

## Direction

Outbound candidate Profiles:

```text
direction = outbound | bidirectional
```

Inbound candidate Profiles:

```text
direction = inbound | bidirectional
```

Return traffic of already admitted flows is outside this NEW-flow classifier.

## Prefix semantics

Profile `destinations` are remote-side prefixes.

Therefore:

- outbound uses remote destination address;
- inbound uses remote source address.

Different-length overlaps resolve by longest/more-specific prefix.

Exact duplicate prefix ownership is rejected by configuration normalization before this unit.

No match returns `None`; it does not select ambient/default policy.

## Inbound ingress restriction

Inbound classification first restricts candidate Profiles to those whose
`ordered_paths` contains the actual ingress logical path.

A more-specific prefix belonging only to another Device/path cannot shadow a less-specific
Profile valid for the actual ingress path.

This ordering of restrictions is part of product semantics, not an implementation
optimization.

## Component design

Pure calculation inside `PayloadPolicyCalculator`.

No new component.

## Evidence plan

Rootless tests:

- outbound direction filtering;
- inbound direction filtering;
- most-specific overlap;
- no match returns None;
- inbound actual-ingress restriction before prefix specificity;
- same remote prefix can classify differently on different ingress paths through different
  Profiles;
- zero-path Profile never accepts inbound NEW traffic.

## Verdict

**PASS — pure Profile NEW-flow classification may be implemented.**
