# VPN-GATE NG3 — Pure structural pipeline integration evidence gate

**Cycle:** `ng3-design-cycle-20261116-post-closure-implementation-readiness-40m`  
**Review unit:** rootless cross-contract integration evidence for already accepted pure units

## Purpose

Individually accepted pure contracts must compose without changing their semantics.

This unit adds no production mechanism.

It verifies the seam:

```text
Device/Profile TOML
    -> structural normalization
ip-link JSON
    -> authoritative InterfaceIdentity inventory
structural config + inventory
    -> stable logical path bindings
Profiles + bindings
    -> PayloadProfileRequest
remote flow context
    -> Profile classification
established problem flags
    -> effective path order
```

## Scenarios

1. Multi-path outbound Profile:
   - configured Device/selector order survives interface inventory ordering;
   - classification identifies the Profile;
   - one established path problem changes only effective priority.

2. Zero-binding Profile:
   - Profile request remains present with `ordered_paths=()`;
   - outbound remote prefix still classifies to that policy domain;
   - lower layers can therefore fail closed rather than lose Profile ownership.

3. Inbound single-path Release 1:
   - accepted capacity<=1 config;
   - actual ingress logical path is required for inbound classification.

## Non-goals

No Linux mutation, route metrics, probe execution, traffic envelope, NAT or publication.

## Verdict

**PASS — integration evidence may be added without new product semantics.**
