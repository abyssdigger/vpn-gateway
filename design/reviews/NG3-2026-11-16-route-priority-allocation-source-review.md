# VPN-GATE NG3 — Route-Priority Allocation Source Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-primary-requirements-basis-40m`

## Trigger

The accepted lower realization contract now states the internal values required by the
physical priority backend:

- table;
- owner protocol;
- path route realization;
- preference/scratch metric space.

The next apparent coding step would be to choose those values.

## Review result

Choosing them inside a priority-only helper would be premature.

Table/rule/protocol/metric ownership is shared lower NetworkPolicyAdapter machinery. It must
remain compatible with:

- structural Profile routing;
- fail-closed zero-path behavior;
- RPDB selection;
- payload and probe owner scopes;
- filtering/NAT realization;
- cleanup and drift detection.

A locally convenient priority allocator could otherwise create identifiers that later
conflict with structural policy or require exposing implementation identifiers upward.

## Classification

**Design dependency, not requirement insufficiency.**

The accepted requirements are sufficient: users do not choose these Linux identifiers, and
the lower Adapter owns implementation realization.

The missing work is one coherent lower network-policy layout, not a product decision.

## Decision

Do not implement a standalone priority allocator yet.

The next lower-policy review unit must first define the shared internal ownership/allocation
layout for:

```text
routing domains / tables
route ownership marker
RPDB priorities
route metric spaces
payload/probe owner scopes
cleanup identity
```

The already accepted `RoutePriorityDomainRealization` then consumes allocations from that
layout.

Historical NG1/NG2 numeric constants may be used as evidence/examples but are not inherited
normatively.

## Safety / simplicity

This avoids two failure modes:

1. duplicated allocators choosing overlapping Linux identifiers;
2. leaking route table/metric/protocol values into Manager or user configuration merely to
   make the priority backend constructible.

It also keeps one authoritative place for owned-resource cleanup identity.

## Human gate

None.

This is an internal architectural dependency with no change to user-visible behavior,
configuration or accepted product scope.

## Verdict

**PASS — standalone priority allocator rejected; shared lower-policy allocation is the next
design unit.**
