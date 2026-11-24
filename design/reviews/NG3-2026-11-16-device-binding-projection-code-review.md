# VPN-GATE NG3 — Stable-slot Device binding projection code review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-post-closure-implementation-readiness-40m`

## Scope

Reviewed:

- `design/NG3/code/python/rou/interface_identity.py`;
- `design/NG3/code/python/rou/binding.py`;
- `design/NG3/code/python/rou/tests/test_binding.py`;
- structural config -> binding seam;
- implementation gate
  `design/reviews/NG3-2026-11-16-device-binding-projection-implementation-gate.md`.

## Evidence

Rootless combined suite:

```text
28 tests
PASS
```

Python compilation check also passed.

## 1. Stable logical slot identity

PASS.

Bound endpoint identity and logical path identity are separate:

```text
InterfaceIdentity = (ifname, ifindex)

LogicalPathId =
    device_id
    + selector_index
    + slot_index
```

A survivor remains in the same slot when fresh inventory ordering changes.

## 2. Delayed waiting-candidate promotion

PASS.

The implementation distinguishes:

- a slot already free in the previous committed projection;
- a slot that becomes free because a bound endpoint disappears in the current proposed
  projection.

Only the first class can be filled in the current pass.

Therefore:

```text
observe disappearance
    -> proposed empty slot + waiting candidate
    -> verify/commit removal projection
    -> later reconcile
    -> waiting candidate may occupy exact freed slot
```

This matches the current architecture and avoids reusing identity/capacity before verified
removal is committed.

## 3. Survivor and waiting order

PASS.

- existing bound survivors keep exact slots;
- previous waiting candidates that remain present keep committed order;
- newly observed candidates append in fresh inventory order;
- newcomers do not evict survivors;
- lexical ifname sorting is not policy.

State remains bounded to current slots and current waiting candidates; no event history or
replay is retained.

## 4. Interface generation

PASS.

Same-name/new-ifindex is a fresh concrete endpoint.

A replacement does not inherit the old concrete binding in the disappearance pass. It joins
the waiting set according to current admission order and can bind only after the old slot
removal is committed.

This is independent from the separate EXP-025 conntrack-generation issue.

## 5. Active/inactive Device state

PASS.

The projector consumes only active `DeviceBindingIntent` values. State for Devices absent
from the current intent set is not retained in the next projection.

No independent Device Engine is introduced.

## 6. Observation validity

PASS for this boundary.

The pure projector rejects:

- duplicate concrete identity;
- repeated ifname with conflicting ifindex;
- repeated ifindex with conflicting ifname;
- an endpoint matching multiple active selectors;
- duplicate Device binding intents.

This prevents the pure projection from guessing ownership.

## 7. Configuration seam

PASS.

A regression test feeds `StructuralConfig.device_binding_intents` directly into the
projector.

It verifies that:

- Device selector position comes from configured `expected_interfaces` order;
- fresh interface inventory order chooses candidates **within** a selector;
- inventory order cannot reorder selector policy;
- generated `LogicalPathId` values preserve selector/slot hierarchy.

## 8. Upstream observation-order dependency

Not a defect in this unit.

The projector intentionally consumes a **fresh ordered authoritative interface inventory**.

The future `VPNPathAdapter` observation boundary remains responsible for:

- obtaining the full authoritative current inventory;
- not treating Netlink event payload as truth;
- target-specific validation of interface facts;
- deterministic fresh observation ordering, including any required ifindex tie handling.

That responsibility must not be duplicated inside the pure binding projector.

## 9. Simplification review

No justification exists here for:

- DeviceManager/DeviceEngine;
- Netlink listener state;
- queue/event history;
- persistent binding journal;
- kernel mutation;
- route allocation;
- availability state;
- retry policy.

The retained state — stable slots and waiting order — is the minimum state required by the
accepted survivor/promotion semantics.

## Verdict

**PASS — STABLE-SLOT DEVICE BINDING PROJECTION ACCEPTED.**

The next independent unit may consume the accepted binding projection to derive
Profile-local ordered logical path membership.
