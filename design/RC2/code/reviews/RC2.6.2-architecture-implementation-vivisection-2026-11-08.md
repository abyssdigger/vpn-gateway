# Independent vivisection — RC2.6.2 implementation/data-model feasibility

**Date:** 2026-11-08  
**Reviewed commit:** `b5a4a3de029709bf1ddd17c457f5910524565150`  
**Scope:** implementability, typed boundaries, migration from RC2.5.1, test seams

## V1 — architecture is implementable without fake selector resources

**PASS.**

The key model boundary is now unambiguous:

```text
InterfaceSelector
-> InterfaceResolution
-> concrete binding
-> RouteSpec / exact iptables / exact NAT
```

No implementation needs to create a temporary `RouteSpec(interface="vpns%")` or rewrite
kernel objects after the fact.

This removes the largest modeling hazard from the old single-static-interface design.

## V2 — ReconciliationSnapshot scope

**PASS with implementation discipline.**

The architecture uses one immutable desired interpretation per pass:

- interface inventory;
- selector resolutions;
- readiness;
- desired routes;
- full desired policy.

ACTUAL kernel inventories are still fresh at verify boundaries and are not described as
frozen inside this desired snapshot.

Implementation should preserve that distinction explicitly, preferably through type/API
shape rather than comments only.

No architecture correction is required.

## V3 — isolation and full policy should have different callable surfaces

**RECOMMENDATION, not blocker.**

RC2.6.2 now has a strong semantic distinction between:

```text
isolation filter verified
full desired firewall/NAT SAFE
```

The implementation should make accidental substitution difficult.

A clean package design would use distinct policy/value/result objects or distinct verifier
entry points rather than one generic boolean `safe=True`.

Exact class names remain implementation-level.

## V4 — policy replacement semantics are now sufficient

**PASS.**

The phrase “complete daemon-owned filter desired state for this stage” is enough to require
canonical replacement of stale owned ACCEPT state.

The existing structural parser/restore model can support this: expected owned chain contents
are rebuilt from one policy source, compared, and restored atomically per filter table.

No ad-hoc delete-rule algorithm is needed for normal repair.

## V5 — selector overlap implementation

**PASS architecturally; test-heavy implementation required.**

The validator must implement semantic set intersection, not string prefix alone.

Minimum corner cases remain:

```text
vpns%    vs vpns0    -> overlap
vpns%    vs vpns1%   -> overlap
vpns1%   vs vpns12%  -> overlap
vpns1%   vs vpns2%   -> disjoint
vpns%    vs VPNS%    -> disjoint
```

with the 15-character concrete ifname bound.

This is a pure-function unit-test problem, not an architecture gap.

## V6 — kernel interface inventory

**PASS.**

The required record `name + ifindex + IPv4` is sufficient for current binding semantics.

Duplicate same-name records may be merged only with consistent ifindex; conflicting identity
is a kernel inventory error.

No operstate/LOWER_UP field is required because readiness intentionally excludes it.

## V7 — selective route cleanup

**PASS.**

A separate marker-filtered inventory API is justified.

Implementation must not share a parser mode that silently skips unsupported selected
proto-201/202 routes. The filtered query narrows unrelated input; it does not weaken
strictness within the reserved marker namespace.

## V8 — package split

**APPROVE.**

At the current code size, splitting by responsibility is preferable to expanding the
single RC2.5.1 source further.

A reasonable first target remains:

```text
vpn_gateway/
    model.py
    config.py
    policy.py
    kernel.py
    daemon.py
vpn-gatewayd
```

The exact names are not normative.

Migration should preserve one source of truth at every commit. In particular, do not leave
the old `_fixed_firewall_model()` active beside a second authoritative policy builder.

## V9 — implementation sequencing

Recommended staged order:

1. package skeleton + move behavior without semantic change where practical;
2. typed `InterfaceSelector`, `InterfaceRecord`, `InterfaceResolution`;
3. selector parsing/overlap tests;
4. interface inventory with ifindex;
5. desired `ReconciliationSnapshot` and config-only isolation policy;
6. full dynamic policy builder;
7. marker-selective cleanup inventory + runtime-directory security + accepted
   read-before-write fixes;
8. daemon deny-first orchestration;
9. Netlink/periodic event loop and runtime reconciliation;
10. live lifecycle/binding experiments.

However, step 1 must not create a long-lived branch where duplicated old/new policy logic is
both authoritative.

## V10 — required experiment before family guard implementation

**BLOCKS only that specific feature, not the architecture.**

Before encoding the deny-only family INPUT guard, validate on target Debian:

- exact iptables interface-prefix syntax accepted by iptables-nft 1.8.11;
- what names it actually matches;
- canonical `iptables-save` representation;
- restore/save stability;
- behavior with exact profile rule before the family guard.

Until then, code must not guess that `vpns+` is equivalent to numeric selector
`^vpns[0-9]+$`.

## Implementation verdict

**APPROVE RC2.6.2 as an implementation contract.**

No architecture-level implementability blocker remains.

The next technical gate should be the small target experiment for the deny-only family
interface match, followed by staged RC2.6.x implementation with focused unit tests.
