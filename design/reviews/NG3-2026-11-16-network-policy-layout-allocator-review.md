# VPN-GATE NG3 — Lower Network-Policy Allocator Code Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-lower-policy-layout-40m`  
**Implementation/fix commits reviewed:**  
- `07588399a1f844a231fc3c7da5a64b57e509c0b2`
- `e43fc15d44111092504e9ce473d7880819bd9849`

## Scope

The unit implements the shared lower ownership/allocation layout as a pure deterministic
allocator over an injected `NetworkPolicyPlatformSpace`.

It deliberately does **not** select production Linux numeric constants.

Inputs are current normalized semantic owners:

- enabled `PayloadProfileRequest` objects;
- explicit `ProbeRoutingDemand` objects only for probe subjects whose selected physical
  mechanism needs independent routing resources.

Output includes:

- per-Profile table allocation;
- payload destination dispatch rules and priorities;
- Profile-local route-priority metric spaces;
- probe table/rule allocation;
- shared route marker roles;
- dedicated nftables namespace identity.

## Requirement/design gate

PASS.

The implementation keeps Linux resource numbers below NetworkPolicyAdapter and does not
modify the human-facing schema.

Zero-path Profiles still receive a payload routing-table allocation and terminal guard tier.

Probe semantic identity is explicit without allocating unused probe machinery.

## Determinism

PASS.

Allocation is independent of input collection order:

- payload tables: Profile ID ascending;
- probe resources: `(profile_id, logical_path_id)` ascending;
- dispatch: prefix length descending, network address ascending, Profile ID final tie-break.

The accepted ID grammar is lowercase ASCII/hyphen, so Python string ordering is stable for
the normalized Profile IDs used by this contract.

## Resource separation

PASS after validation hardening.

The platform contract enforces:

- disjoint payload/probe table pools;
- no table pool overlap with Linux table IDs 0/253/254/255;
- disjoint probe/payload RPDB pools;
- probe rule priorities numerically before payload priorities;
- payload priorities before the declared ambient/main rule;
- RPDB priority 0 is not claimable by VPN-GATE;
- path and guard route protocol markers are distinct roles;
- one fixed lower nft namespace rather than user-derived kernel names.

## Metric allocation

PASS.

For a Profile with N paths:

- N consecutive strictly increasing preference metrics are allocated;
- one additional scratch metric is allocated when N > 1;
- all are strictly preferred to the terminal guard metric;
- zero paths allocate no preference/scratch space;
- every Profile table may reuse the same metric values because the table is an independent
  metric namespace.

Capacity failure is reported before a layout is returned.

## Stale-resource cleanup property

PASS.

The resource pools are stable platform objects with `contains()` classification independent
of the current owner allocation map.

A config transition may therefore shift Profile table numbers while an old table remains
recognizable as belonging to the reserved payload table namespace.

This is necessary for cleanup/reconciliation without a durable allocation journal.

## Finding F1 — precedence regression test accidentally overlapped pools

**Severity:** test-only  
**Disposition:** fixed in `e43fc15d`

The initial negative test intended to exercise wrong probe/payload precedence but supplied
overlapping pools. The implementation correctly rejected overlap first.

The test now uses disjoint pools with reversed precedence, so the intended precedence
invariant is tested directly.

## Finding F2 — Linux local rule priority 0 was not explicitly excluded

**Severity:** internal safety hardening  
**Disposition:** fixed in `e43fc15d`

Priority 0 is the Linux local-rule slot and should not be claimable by VPN-GATE's injected
platform pool.

The platform validator now rejects payload or probe pools starting at 0.

## Finding F3 — direct construction could supply an empty Profile ID

**Severity:** local contract hardening  
**Disposition:** fixed in `e43fc15d`

The normal config pipeline already enforces the ID grammar, but the allocator is an exported
internal contract. It now independently requires a non-empty Profile ID before sorting or
allocating resources.

## Evidence

Final GitHub Actions run:

```text
workflow: NG3 Python
run:      43824742458
commit:   e43fc15d44111092504e9ce473d7880819bd9849
unit:     171 tests, OK
linux-route-priority: PASS
overall:  success
```

The existing privileged Linux route-priority integration remains green.

## Residual boundary

The next review unit selects and proves one concrete Linux
`NetworkPolicyPlatformSpace`:

- payload/probe table ranges;
- probe/payload RPDB priority ranges;
- path/guard route protocol markers;
- Profile metric start/terminal guard values;
- nft family/table namespace.

Selection must be validated with privileged Linux evidence rather than inherited from
historical constants by convention.

## Final verdict

**PASS AFTER FIXES.**
