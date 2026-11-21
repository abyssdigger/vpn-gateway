# VPN-GATE NG3 — Direct-Device Route Realizer Code Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-lower-policy-layout-40m`  
**Reviewed commit:** `8f301c181989e42cb30eba1f8895f932a6203d83`

## Scope

Reviewed `direct_device_route.py`, which implements the narrow integration capability
accepted by the preceding VPN-path route-realization boundary review.

The helper converts already verified `PathBinding` objects into:

```text
RoutePriorityPathRoute(
    same logical path,
    same current InterfaceIdentity,
    gateway=None,
    onlink=False
)
```

It is not called by ConfigurationAdapter or the generic binding projection.

## Requirement/design gate

PASS.

The helper implements lower integration detail under:

- `VPNG0001-R1.R3.R2` current concrete endpoint binding;
- `VPNG0001-R1.R3.C1.R1` supported-integration onboarding contract;
- `VPNG0007-R7.R3.R2` containment of lower technical details.

It does not claim that every supported VPN channel is direct-device.

## Evidence basis

Historical EXP-009 H5 proved direct-device forwarding through the tested OpenConnect
point-to-point endpoint without Linux `via` or `onlink`.

That evidence justifies an explicit direct-device integration capability. It does not
justify inferring the capability solely from an interface name or from generic Device
binding.

## Contract review

PASS.

The implementation:

- accepts only `PathBinding`;
- preserves exact current `InterfaceIdentity`;
- rejects duplicate logical-path bindings;
- rejects one concrete endpoint assigned to two logical paths;
- emits deterministic path-ID order so input collection order is not policy;
- allows an empty binding set;
- contains no gateway/peer inference.

The caller remains responsible for selecting this helper only for an integration whose
accepted onboarding/topology contract proves direct-device routing.

## Evidence

GitHub Actions run:

```text
run:      43826714249
commit:   8f301c181989e42cb30eba1f8895f932a6203d83
unit:     188 tests, OK
linux-route-priority: PASS
linux-policy-platform / EXP-028: PASS
overall:  success
```

## Residual boundary

The pure-priority chain is now connectable end-to-end for a supported direct-device
integration:

```text
PathBinding
 -> explicit direct-device realization
 -> Profile/allocation domain builder
 -> route-priority domain coordinator
 -> physical iproute2 backend
```

The next material unit is structural route/RPDB realization:

- Profile terminal guard route;
- payload destination dispatch rules;
- authoritative observation and conflict handling;
- verified apply/cleanup under the structural safety boundary.

nft payload/probe policy remains a separate subsequent unit.

## Final verdict

**PASS.**


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG0007-R7.R3.R2` -> `VPNG9001-R1.R1.R3.R2`

The original IDs in the historical body are intentionally preserved.
