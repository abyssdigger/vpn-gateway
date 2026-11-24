# VPN-GATE NG3 — VPN Path Route-Realization Boundary Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-lower-policy-layout-40m`

## Trigger

The accepted route-priority domain builder requires one `RoutePriorityPathRoute` for each
current logical path.

The current binding layer provides only:

```text
logical path -> (ifname, ifindex)
```

It does not universally provide Linux `gateway/onlink` semantics.

## Requirement gate

Relevant accepted nodes:

- `VPNG-U001-R1.R3` — supported external VPN channels are usable as managed paths;
- `VPNG-U001-R1.R3.R2` — the logical path has one verified current concrete endpoint;
- `VPNG-U001-R1.R3.C1` / `C1.R1` — external provisioning and onboarding remain
  administrator/integration responsibilities in Release 1;
- `VPNG-U001-R1.R3.C2` / `C2.R1` — the data-plane endpoint must exist inside the managed
  network domain;
- `VPNG-U007-R7.R3.R2` — lower integration details must not leak upward without need.

No requirement says every supported endpoint uses the same Linux next-hop form.

## Decision

Separate endpoint binding from route realization.

The lower integration contract supplies:

```text
PathBinding
+ verified integration topology
    ->
RoutePriorityPathRoute
```

The generic Adapter does not infer `gateway/onlink`.

## Direct-device capability

A narrow direct-device realization is accepted for integrations whose onboarding/evidence
explicitly proves:

```text
route <destination> dev <bound-interface>
```

with no transport next-hop and no `onlink`.

EXP-009 H5 provides real OpenConnect evidence for that shape.

The same helper may be used by another integration only when that integration's own contract
makes direct-device routing valid. For WireGuard, destination ownership remains a
cryptokey-routing/`AllowedIPs` concern; the existence of `wg0` alone is not proof that an
arbitrary Profile destination is routable through it.

## Rejected alternatives

### Infer peer/gateway from interface address inventory

Rejected. A peer address is not a generic route association key; EXP-009 explicitly found
that transport peer semantics and Linux route next-hop semantics are not equivalent.

### Make all matched interfaces direct-device automatically

Rejected. That would silently narrow the supported-integration model without a requirement.

### Add gateway/onlink to user Device/Profile configuration now

Rejected. The need is lower integration realization, not user policy. Exposing Linux
next-hop mechanics would violate the current configuration boundary without product value.

## Implementation unit

Add an explicit pure direct-device realizer that:

- consumes already verified `PathBinding` objects;
- emits `RoutePriorityPathRoute(gateway=None, onlink=False)`;
- is named/called as an integration capability rather than as the generic binding
  projection;
- rejects malformed/duplicate binding input.

Do not wire it universally into `PayloadProfileRequest` or ConfigurationAdapter.

## Verdict

**PASS — route realization remains integration-specific; direct-device is a narrow explicit
capability.**


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U007-R7.R3.R2` -> `VPNG-D001-R1.R1.R3.R2`

The original IDs in the historical body are intentionally preserved.
