# VPN-GATE NG3 — Route-Priority Domain Builder Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-lower-policy-layout-40m`  
**Implementation/fix commits reviewed:**  
- `a3d32ae7108c3400feb28e5b7d518fedffe575c5`
- `800850e2564fdfead671c1fdbdd5b4b562712dfa`

## Scope

This unit closes the pure bridge between already accepted semantic payload policy and the
already accepted physical pure-priority route-domain contract.

Inputs:

- one `PayloadProfileRequest`;
- its current `PayloadPolicyAllocation`;
- already verified lower `RoutePriorityPathRoute` realizations.

Output:

- one `RoutePriorityDomainRealization` per Profile destination.

The builder intentionally does **not** infer endpoint, gateway or `onlink` semantics. Those
facts remain the responsibility of the VPN integration/lower path-realization contract.

## Requirement / architecture gate

PASS.

The unit preserves the accepted boundaries:

- Profile remains semantic policy;
- Linux table/protocol/metric allocation remains below NetworkPolicyAdapter;
- current concrete route shape is supplied by lower integration facts rather than guessed
  from Profile intent;
- zero-path Profiles remain structural fail-closed domains but have no pure-priority
  route-key domain to mutate.

No user-visible field or new product promise was introduced.

## Accepted behavior

For a non-empty Profile, the builder:

1. requires exact Profile/allocation identity;
2. requires exact logical-path membership equality between semantic order and physical path
   realizations;
3. reorders supplied physical path facts into the semantic `ordered_paths` order;
4. requires one current preference metric slot per semantic path;
5. creates one domain per destination using the same Profile table, route protocol and
   metric space;
6. validates desired metric assignment immediately.

Destination collection order is normalized so an incidental input order does not become
lower mutation policy.

For a zero-path Profile, the builder returns no pure-priority domains. The Profile's table
and terminal fail-closed guard remain structural-policy responsibilities.

## Finding F1 — stale allocation cardinality could cross a structural config change

**Severity:** material boundary defect  
**Disposition:** accepted and fixed in `800850e2`

The first version required path-membership equality with supplied physical path routes but
did not require the allocation's preference-slot count to equal the current semantic path
count.

A stale allocation from the same Profile ID but an older path membership could therefore
contain additional preference slots and still be accepted.

The fixed builder requires:

```text
len(current semantic paths)
==
len(current allocation preference slots)
```

A mismatch is rejected. It cannot silently enter the pure-priority path.

This enforces the architecture rule that a path-membership/configuration change is
**structural** and must pass through structural reconciliation/allocation, not reuse a stale
priority-only realization.

## Finding F2 — direct construction could bypass destination completeness

**Severity:** local contract hardening  
**Disposition:** accepted and fixed in `800850e2`

The normal configuration pipeline already requires non-empty unique destinations, but this
builder is an exported internal boundary.

It now independently rejects:

- empty destination sets;
- exact duplicate destinations.

This prevents a malformed direct caller from constructing an incomplete lower domain set.

## Gateway/onlink disposition

The builder copies `RoutePriorityPathRoute` exactly.

It does not convert every bound VPN interface into `gateway=None, onlink=False`.

Historical EXP-009 proves direct-device routing for the tested OpenConnect path and shows
that WireGuard peer selection is governed by `AllowedIPs`, but the NG3 requirement permits
multiple supported external integration contracts.

Therefore route-shape selection remains integration-specific lower evidence, not a hidden
global assumption of this builder.

## Evidence

GitHub Actions run:

```text
run:      43826197193
commit:   800850e2564fdfead671c1fdbdd5b4b562712dfa
unit:     182 tests, OK
linux-route-priority: PASS
linux-policy-platform / EXP-028: PASS
overall:  success
```

## Residual boundary

The next implementation boundary is the lower VPN-path route-realization source:

```text
current PathBinding
+ supported VPN integration contract/topology
    ->
RoutePriorityPathRoute
```

That boundary must preserve integration-specific semantics. A direct-device helper may be
accepted for integrations whose onboarding/evidence proves it, but it must not silently
become a universal requirement for every future VPN channel type.

After that, the larger structural NetworkPolicyExecutor still needs:

- terminal guard routes;
- RPDB Profile dispatch;
- nft payload/probe policy;
- guarded structural convergence/cleanup.

## Final verdict

**PASS AFTER FIXES.**
