# VPN-GATE NG3 — Payload Routing Desired-State Projection Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-lower-policy-layout-40m`  
**Implementation/fix commits reviewed:**  
- `c819acfe39db5874596f2baccf812f1b7925ccbf`
- `c4713f0d6c5e34c6d18c6aeae11efca1688c0071`
- `cee67cb5233cb870ce26daeee0e1e6beba9421fd`

## Scope

The unit constructs a **complete immutable payload routing desired state** without mutating
Linux.

Inputs:

- the complete current `PayloadProfileRequest` set;
- the current accepted `NetworkPolicyLayout`;
- the complete current lower `RoutePriorityPathRoute` set;
- the verified managed host-boundary `InterfaceIdentity`.

Output:

- one terminal blackhole guard per Profile table;
- one ordinary desired route for each Profile destination × current logical path;
- one host-boundary RPDB destination dispatch rule per Profile destination.

## Requirement / safety gate

PASS.

The unit is pure data construction and therefore does not violate the structural activation
barrier.

It explicitly implements the zero-path invariant:

```text
Profile with paths = 0
    ->
allocated Profile table
+ terminal BLACKHOLE default
+ Profile destination dispatch rules
+ no ordinary path routes
```

A later physical Executor can therefore verify that managed destinations terminate
fail-closed instead of falling through to ambient/main routing.

## Desired route identity

PASS.

Ordinary route specs retain:

- Profile table;
- strict destination;
- path route protocol marker;
- semantic preference metric;
- logical path identity;
- exact current `InterfaceIdentity`;
- integration-supplied gateway/onlink semantics.

Terminal guards have no path/endpoint/gateway identity and use the guard role protocol plus
terminal metric.

A Profile whose destination is `0.0.0.0/0` correctly contains both:

- ordinary default route(s) at preferred metrics;
- terminal blackhole default at `0xffffffff`.

## Finding F1 — complete projection initially ignored extra stale path realization

**Severity:** material stale-state boundary  
**Disposition:** fixed in `c4713f0d`

The first builder rejected missing path facts but could accept additional stale
`RoutePriorityPathRoute` values that were no longer part of the current semantic payload
path set.

Because this function claims a complete current payload desired projection, silently
ignoring stale lower realization would weaken the structural config-change boundary.

The fixed builder requires exact equality:

```text
set(path route realizations)
==
union(current semantic payload logical paths)
```

It also rejects one endpoint realized for multiple logical paths.

## Finding F2 — direct-constructed dispatch layout could bypass allocator ordering invariants

**Severity:** internal boundary hardening  
**Disposition:** fixed in `c4713f0d`

The allocator already emits canonical dispatch, but the desired-state builder is an exported
internal contract and must not blindly trust a hand-constructed `NetworkPolicyLayout`.

It now verifies:

- exact `(Profile, destination)` dispatch membership;
- matching current Profile table;
- canonical longest-prefix-first rule order;
- valid, unique priorities;
- monotonically increasing priority values along canonical dispatch order.

Thus a malformed/stale layout cannot be converted into physical desired policy.

## Finding F3 — negative test retained the pre-hardening error text

**Severity:** test-only  
**Disposition:** fixed in `cee67cb5`

The missing-path test now expects the stronger exact-set rejection.

## Host-boundary identity

PASS.

The desired RPDB rule retains full current `InterfaceIdentity`, not only an ifname string.

The later physical observation/apply layer must verify that the same-name interface has not
been replaced before treating the rule as current/owned.

## Evidence

Final GitHub Actions run:

```text
run:      43827456373
commit:   cee67cb5233cb870ce26daeee0e1e6beba9421fd
unit:     198 tests, OK
linux-route-priority: PASS
linux-policy-platform / EXP-028: PASS
overall:  success
```

## Residual boundary

The desired state is not an activation plan.

Next safe implementation work may observe and normalize current owned route/RPDB state for
comparison with this desired value.

Actual structural mutation remains gated on the shared route+nft restrictive barrier:

```text
barrier verified
 -> prepare routes
 -> prepare nft
 -> switch RPDB
 -> complete verify
 -> release barrier
```

## Final verdict

**PASS AFTER FIXES.**
