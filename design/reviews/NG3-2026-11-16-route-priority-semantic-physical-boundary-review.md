# VPN-GATE NG3 — Route-Priority Semantic-to-Physical Boundary Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-primary-requirements-basis-40m`

## Trigger

After accepting Profile-level multi-domain convergence, the next implementation step was to
generate complete physical route-domain requests directly from `PayloadProfileRequest`.

That direct projection is not valid.

## Observed contract mismatch

`PayloadProfileRequest` contains:

```text
profile identity
direction
destinations
ordered logical path identities
```

The accepted physical iproute2 backend requires, per route-key domain:

```text
current endpoint identity
gateway/onlink shape
internal table
owner protocol
owned metric working space
```

Those values do not belong to user policy and are not present in the Manager's semantic
request.

## Classification

**Design-boundary insufficiency, not requirement insufficiency.**

The accepted requirements already say:

- the user config expresses intent rather than Linux internals;
- path identity is separate from current concrete endpoint;
- the Manager does not own Linux route/table representation;
- NetworkPolicyAdapter/Executor own lower materialization and authoritative state.

Therefore adding table/proto/metric/gateway fields to `PayloadProfileRequest` would violate
the existing separation rather than close a requirement gap.

## Resolution

The architecture now makes the boundary explicit.

NetworkPolicyAdapter/lower realization combines:

1. semantic Profile/path order from PayloadTrafficManager;
2. current verified path/transport realization;
3. internal owned-resource allocation;

to produce the physical route-key requests used by NetworkPolicyExecutor.

The physical fields remain internal.

If a logical allowed path has no unambiguous current physical route realization, the lower
layer must not invent one from ambient host state and must not silently remove the path from
policy. The affected lower policy remains unconfirmed/fail-closed until structural
reconciliation can establish a valid realization.

## Why no code in this unit

The current code has a valid lower `RoutePriorityPathRoute` type and a valid physical
backend, but the source of gateway/onlink and owned table/metric allocation has not yet been
implemented as one accepted lower realization contract.

Inventing those sources locally just to connect the existing classes would violate the
requirement/design gate.

## Next implementation unit

Define and evidence the internal lower route-realization/allocation contract that supplies:

- current `RoutePriorityPathRoute` per logical path;
- internal route table/owner identity;
- owned metric space per route-key domain;

without exposing these values as user configuration or moving Linux representation into
PayloadTrafficManager.

## Verdict

**PASS — boundary clarified; direct Manager-to-iproute projection rejected.**

No human product decision is required. The next work remains internal architecture/
implementation, but must start at the lower realization boundary rather than by enriching
the semantic Profile contract with Linux details.
