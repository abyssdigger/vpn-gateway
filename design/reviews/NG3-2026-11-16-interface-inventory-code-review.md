# VPN-GATE NG3 — Authoritative interface inventory code review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-post-closure-implementation-readiness-40m`

## Scope

Reviewed:

- `design/NG3/code/python/rou/interface_identity.py`;
- `design/NG3/code/python/rou/interface_inventory.py`;
- `design/NG3/code/python/rou/tests/test_interface_inventory.py`;
- interface-inventory implementation gate.

## Evidence

Combined rootless suite after accepted fix:

```text
43 tests
PASS
```

Python compilation also passed.

## 1. Authoritative interface source

PASS.

The parser consumes full ordered `ip -j link show` JSON.

It does not infer interface presence from IPv4-address output, preserving the EXP-002/002A
finding that an existing interface may have no IPv4 address.

## 2. Ordered snapshot semantics

PASS.

Authoritative JSON array order is preserved exactly and can be consumed by stable-slot binding
admission.

No lexical ifname sort is introduced.

## 3. Observation failure versus valid absence

PASS.

`[]` is a valid authoritative empty snapshot.

Malformed JSON, invalid shape or invalid/ambiguous identity raises
`InterfaceInventoryError`; it is not normalized to empty inventory.

Therefore observation failure cannot masquerade as mass endpoint disappearance.

## 4. Identity validation

PASS after one fix.

The parser rejects duplicate ifname, duplicate ifindex, non-positive/non-integer ifindex,
empty/oversized ifname.

### Finding — InterfaceIdentity admitted bool when constructed outside parser

**Severity:** contract-local typing defect  
**Disposition:** fixed

Python `bool` is an `int` subclass. Initial `InterfaceIdentity.__post_init__` only checked
`<= 0`, so direct `InterfaceIdentity("vpn0", True)` would pass even though parser rejected
it.

Fix:

- `ifname` must be actual non-empty string;
- `ifindex` must satisfy `type(value) is int and value > 0`.

Regression added.

## 5. Same-name/new-ifindex

PASS.

Separate valid snapshots may contain the same ifname with a different ifindex, producing a
different `InterfaceIdentity`.

Within one snapshot duplicate ifname remains invalid.

## 6. Component boundary

The implementation remains technical observation machinery inside `VPNPathAdapter`.

It does not introduce:

- Netlink state;
- scheduler;
- retry policy;
- address/route/global EnvironmentSnapshot aggregation;
- binding state.

Events remain wakeups; this parser represents the fresh observation boundary.

## Verdict

**PASS — AUTHORITATIVE INTERFACE INVENTORY PARSER ACCEPTED.**
