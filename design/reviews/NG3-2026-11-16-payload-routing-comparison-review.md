# VPN-GATE NG3 — Payload Routing Actual-vs-Desired Comparison Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-lower-policy-layout-40m`  
**Implementation/fix commits reviewed:**  
- `d9f14afa01608bb45a6da225e3c5cb93e2c83841`
- `1fcf8f2f395f49ec4aa8f4dba10632ad3ad3b62d`

## Scope

This unit adds the pure comparison layer between complete desired payload route/RPDB state
and authoritative whole-reserved structural observation.

It performs no Linux mutation.

The result explicitly separates:

```text
confirmed desired routes
missing desired routes
stale recognized payload routes

confirmed desired rules
missing desired rules
stale recognized payload rules

payload-owner reserved conflicts
```

`confirmed == true` only when every missing/stale/conflict set is empty.

## Owner-scope isolation

PASS after one contract extension.

The whole-reserved observer sees both payload and probe resources. A payload comparison must
not fail merely because an independent probe-owner object is stale/conflicting.

`ReservedPolicyConflict` therefore preserves `owner = payload | probe` from the reserved
table/priority pool where the conflict was observed.

The payload comparator:

- compares only payload table space;
- compares only payload RPDB priority space;
- includes only payload-owner conflicts;
- leaves probe state to its independent owner reconciliation.

This preserves the accepted shared-Adapter / separate-semantic-owner model.

## Physical route identity

The comparator matches desired and observed routes on:

- table;
- destination;
- route type;
- protocol role;
- metric;
- effective scope;
- current endpoint `(ifname, ifindex)`;
- gateway;
- onlink.

Logical path ID itself is not a kernel route field and is not part of physical actual-state
identity. The desired-state builder already forbids two current payload paths from collapsing
onto one endpoint realization.

### Scope handling

Observed scope is retained from authoritative inventory.

For the currently accepted Linux forms the comparator uses effective scope:

```text
BLACKHOLE                     -> universe (0)
UNICAST with gateway          -> universe (0)
direct-device UNICAST         -> link (253)
```

Omitted universe scope is normalized as 0.

EXP-029 directly proves the current direct-device `scope=253` and blackhole representation.
A future integration whose gateway route requires materially different scope semantics must
extend/evidence its lower realization before relying on this generic comparison.

## Interface replacement

PASS.

Same-name/new-ifindex actual state does not confirm a desired route bound to the old
InterfaceIdentity.

It is reported as one missing desired route plus one stale recognized actual route.

## Rule identity

Payload rule comparison includes priority, table, full current ingress InterfaceIdentity
and destination prefix.

Probe mark selectors are excluded by owner scope rather than conflated with payload dispatch.

## Finding F1 — conflict records initially had no semantic owner

**Severity:** material reconciliation-boundary defect  
**Disposition:** fixed in `d9f14afa`

Without owner scope a payload reconciler would have to treat every probe conflict as a
payload failure or parse human-readable conflict strings.

The typed `ReservedOwnerKind` now carries the required owner partition.

## Finding F2 — missing Enum import broke package import

**Severity:** implementation regression  
**Disposition:** fixed in `1fcf8f2f`

The first comparator commit added `ReservedOwnerKind(str, Enum)` but omitted the Enum
import, causing unit/package and physical route integration import failures.

The fix is local and followed by a complete green workflow run.

## Evidence

```text
run:      43829159828
commit:   1fcf8f2f395f49ec4aa8f4dba10632ad3ad3b62d
unit:     217 tests, OK
linux-structural-inventory-shape / EXP-029: PASS
linux-policy-platform / EXP-028: PASS
linux-route-priority: PASS
overall:  success
```

## Residual boundary

The structural routing stack now has pure desired construction, authoritative observation
and actual-vs-desired comparison.

It still has **no physical structural mutation**.

The next material implementation unit remains the shared restrictive barrier / nft
structural transaction. Route-table preparation and RPDB activation must not be implemented
as an unsafe standalone activation path.

## Final verdict

**PASS AFTER FIX.**
