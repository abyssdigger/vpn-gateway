# VPN-GATE NG3 — Payload NAT Lower Contract Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-structural-barrier-40m`

## Scope

Derive the internal lower realization of the already accepted Device source-NAT semantics
without selecting the final human-facing TOML grammar.

## Requirement basis

`VPNG0001-R1.R2.R4.R6.R1` requires an explicit distinction between:

```text
no payload source NAT
masquerade through the current concrete Device/path
```

and explicitly rejects a hidden NAT default.

The architecture already places NAT in `DevicePolicyIntent`, separate from availability.

Therefore the internal enum is not a new product decision:

```text
NONE
MASQUERADE
```

## Physical match

For a MASQUERADE Device/path, the lower rule is scoped by:

```text
current host-boundary interface identity
current bound path endpoint identity
```

and materialized as exact numeric nft interface-index matches.

This avoids the same-name/new-ifindex hazard: an old rule cannot automatically authorize a
new concrete interface merely because the new interface reused the old name.

## Why no destination match in NAT

Profile destination/direction permission belongs to `payload_forward`.

The postrouting NAT layer is downstream of that filter decision.

Repeating destination prefixes in NAT would duplicate policy classification and complicate
overlap semantics without changing the user requirement.

The NAT rule answers only:

> if an already-permitted payload packet leaves by this Device path, should VPN-GATE source
> NAT it?

## Probe/control separation

The rule also matches the managed host-boundary ingress identity.

Locally generated ICMP probe/control traffic therefore does not receive payload NAT merely
because it leaves the same VPN endpoint.

## Shared Device/path

A current path may serve several Profiles.

The same physical masquerade contribution is deduplicated by exact boundary/egress identity;
it is not emitted once per Profile.

## Availability

Availability does not add/remove NAT rules.

A path remains a structural eligible path while availability changes only its routing
priority.

## User-grammar boundary

This review does **not** declare that the final TOML must literally use:

```toml
nat = "none"
nat = "masquerade"
```

Those spellings remain schema evidence, not accepted grammar.

The executable lower layer will consume normalized `NatIntent` only.

## Evidence gate

EXP-033 must prove on the current target:

1. nft accepts numeric `meta iif` / `meta oif` matching in postrouting;
2. the rule round-trips with unambiguous JSON representation;
3. a matching forwarded flow is actually masqueraded;
4. a packet entering from a different interface is not matched;
5. same-name/new-ifindex replacement does not match the stale numeric rule.

## Verdict

**PASS — internal NAT realization derived; external grammar remains unresolved.**
