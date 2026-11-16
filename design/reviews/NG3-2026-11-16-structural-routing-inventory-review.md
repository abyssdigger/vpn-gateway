# VPN-GATE NG3 — Structural Route/RPDB Inventory Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-lower-policy-layout-40m`  
**Evidence baseline:** EXP-029  
**Implementation/fix commits reviewed:**  
- `432283b04bbbd510d42f0a71b225c62b24ce06b3`
- `96469e0f4d75e6fa981bfb302ad3654746259a85`

## Scope

The unit implements read-only authoritative normalization of the entire VPN-GATE reserved
IPv4 routing-table and RPDB priority namespaces.

It consumes:

- full numeric `ip -j -N -4 route show table all` JSON;
- full numeric `ip -j -N -4 rule show` JSON;
- one fresh current `InterfaceIdentity` inventory;
- the accepted `NetworkPolicyPlatformSpace`.

It returns:

- recognized managed routes;
- recognized managed rules;
- explicit conflicts for reserved objects whose semantics are not representable by the
  accepted lower contract.

Rows outside VPN-GATE reserved pools are ignored.

## Evidence gate

PASS.

EXP-029 is now hardened to assert the exact semantic JSON facts the parser relies on, not
only row counts.

The same workflow run that exercises the parser also reruns EXP-029 against the current
GitHub Linux runner.

## Ownership/conflict behavior

PASS.

A reserved table/priority is **not** treated as sufficient proof of ownership.

Examples that become explicit conflicts:

- unknown route protocol role;
- unsupported route type;
- multipath/nexthop/structured-via shape;
- unrepresented route flags;
- unrepresented route semantic fields;
- managed route referring to an absent current interface;
- payload rule pointing at probe table space;
- unknown RPDB selector/action fields;
- malformed reserved payload/probe rule shapes;
- duplicate normalized reserved objects.

This preserves the architecture rule that reserved namespace membership enables
classification, not blind cleanup.

## Route normalization

PASS.

The parser normalizes EXP-029 forms:

- decimal-string table/protocol;
- omitted unicast type;
- blackhole `"6"`;
- bare host destination -> `/32`;
- `default` -> `0.0.0.0/0`;
- optional IPv4 gateway;
- `onlink` from flags.

Managed `dev` is resolved through the supplied current interface snapshot, so actual
observation retains concrete `(ifname, ifindex)` identity.

## Finding F1 — route scope would have been erased from authoritative observation

**Severity:** material evidence-fidelity hardening  
**Disposition:** fixed in `96469e0f`

The first parser ignored the kernel `scope` field.

Historical RC code intentionally excluded scope from route identity because the kernel
normally derives it from route shape. That does not justify erasing the fact from an NG3
authoritative observation.

The fixed observer retains normalized optional scope (`0..255`) in
`ObservedManagedRoute`.

This does not yet make scope a user/config field or a desired command parameter. It simply
prevents authoritative observation from losing lower-state evidence before comparison.

## Finding F2 — arbitrary extra route fields were initially ignored

**Severity:** material ownership-shape hardening  
**Disposition:** fixed in `96469e0f`

A reserved row carrying additional semantics such as `prefsrc` could otherwise normalize
to the same simplified object as a VPN-GATE route.

The parser now uses an explicit representable field set and reports unknown reserved route
fields as conflicts.

Known structurally unsupported fields such as `nexthops`, `nhid`, `multipath` and
structured `via` remain explicit conflicts.

## Observation failure versus conflict

PASS.

Malformed JSON or an ambiguous interface inventory raises
`StructuralRoutingInventoryError`: no authoritative observation exists.

A syntactically observable but unexpected object **inside** a reserved namespace is returned
as `ReservedPolicyConflict`.

A valid empty reserved inventory is therefore distinct from both cases.

## Evidence

GitHub Actions run:

```text
run:      43828578727
commit:   96469e0f4d75e6fa981bfb302ad3654746259a85
unit:     210 tests, OK
linux-structural-inventory-shape / EXP-029: PASS
linux-policy-platform / EXP-028: PASS
linux-route-priority: PASS
overall:  success
```

## Residual boundary

The unit is deliberately read-only.

The next bounded step is a pure actual-vs-desired structural routing comparison that can
classify:

- confirmed desired objects;
- missing desired objects;
- stale recognized managed objects;
- reserved ownership conflicts.

Physical preparation/activation remains gated on the route+nft structural barrier.

## Final verdict

**PASS AFTER FIXES.**
