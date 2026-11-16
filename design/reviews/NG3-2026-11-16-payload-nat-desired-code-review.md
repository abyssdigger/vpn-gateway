# VPN-GATE NG3 — Payload NAT Desired Projection Code Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-structural-barrier-40m`  
**Implementation/fix commits reviewed:**  
- `37a3060a148d8ecc963a946f0119108df0f892a8`
- `ec207dfd7e28fcd1fc2338321be16c91be2b9058`  
**Live evidence:** EXP-033

## Scope

This unit introduces only normalized internal Device NAT semantics and a pure desired-state
projection for current payload paths.

It does not parse external TOML and does not mutate nft.

## Internal semantic contract

```text
NatIntent.NONE
NatIntent.MASQUERADE
```

`DeviceNatPolicyIntent` binds one explicit normalized NAT intent to one Device ID.

The enum is an internal semantic representation, not acceptance of final external field
spelling.

## Desired projection

For every logical path present in the current payload Profile union:

- the current physical `RoutePriorityPathRoute` must exist exactly once;
- the owning Device must have one explicit normalized NAT intent;
- `NONE` emits no NAT contribution;
- `MASQUERADE` emits one `PayloadMasqueradeSpec` containing:
  - logical path identity;
  - exact current host-boundary `InterfaceIdentity`;
  - exact current egress `InterfaceIdentity`.

A path shared by multiple Profiles is emitted once.

Multiple current paths of one MASQUERADE Device receive independent contributions because
their concrete egress identities differ.

## No implicit default

PASS.

A current payload path whose Device has no normalized NAT intent is rejected.

The builder never interprets missing policy as either NONE or MASQUERADE.

A zero-path Profile produces no physical NAT contribution and therefore does not require a
fictional endpoint-level rule. Upstream configuration normalization remains responsible for
requiring explicit Device NAT semantics before an active Device can become accepted policy.

## Structural/current-state boundary

PASS.

The physical path-route set must exactly equal the union of current semantic payload paths.

Extra stale realization and missing realization are both rejected.

One current concrete endpoint cannot represent two logical paths.

The host boundary itself cannot simultaneously be a VPN egress endpoint.

These checks prevent NAT projection from silently widening the current accepted binding
topology.

## Availability independence

PASS by construction.

Availability state is not an input.

The builder consumes structural Profile path membership only, so availability-only
preference changes cannot create or remove NAT contributions.

## Finding F1 — duplicate Profile identity was not initially rejected

**Severity:** local complete-projection hardening  
**Disposition:** fixed in `ec207dfd`

An exported desired-state boundary should not silently union two directly constructed
Profiles carrying the same Profile ID.

Duplicate payload Profile identity is now rejected.

## Finding F2 — host boundary could be supplied as a path endpoint

**Severity:** local topology hardening  
**Disposition:** fixed in `ec207dfd`

The normal architecture already separates the ordinary host boundary from VPN path
endpoints. The exported lower builder now independently rejects equality between those
concrete InterfaceIdentity values.

## Evidence

Final GitHub Actions run:

```text
run:      43842165993
commit:   ec207dfd7e28fcd1fc2338321be16c91be2b9058
unit:     267 tests, OK
EXP-033 exact-ifindex masquerade: PASS
EXP-032 scaffold + preparation integrations: PASS
EXP-031 owner marker: PASS
EXP-030 forwarding barrier: PASS
EXP-028/029 + route-priority: PASS
overall:  success
```

## Residual boundary

The next lower unit is authoritative observation/classification of actual
`payload_postrouting` NAT rules.

EXP-033 proves that nft renders a live ifindex operand as ifname and a stale unresolved
operand as decimal-string ifindex. That observer must combine full ruleset JSON with a fresh
interface inventory and must not compare interface names alone.

Physical NAT mutation remains gated on that observation/comparison layer and the already
accepted root forwarding barrier.

## Final verdict

**PASS AFTER HARDENING.**
