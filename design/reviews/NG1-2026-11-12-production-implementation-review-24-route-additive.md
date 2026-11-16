# Production implementation review 24 — route-additive transition

Date: 2026-11-12

Role: external expert review focused on route transition safety, fail-close continuity,
metric-lifecycle semantics and Rust migration.

## Trigger

The full disposable production cycle proved:

- initial structural reconcile PASS;
- same-name/new-ifindex lifecycle PASS without global barrier;
- the mandatory second metric-promotion pass unexpectedly entered the global barrier.

## Root cause

This was not a kernel problem. The transition classifier recognized only binding-set
changes as incremental.

After the verified removal commit, the old metric reservation is deliberately released.
The next projection may assign that normal slot to the already-bound fresh generation.
Bindings, firewall, NAT and RPDB no longer change; only a missing desired route is added.

Treating that known second step as structural defeats the documented two-commit metric
lifecycle.

## Accepted model

Introduce an explicit route-additive incremental transition.

It is proven only when all of the following hold:

1. bound interface generation set is unchanged;
2. previous and desired kernel generations are identical;
3. owned RPDB is exactly desired;
4. nft filter and NAT are exactly desired verified generations;
5. nft ruleset ownership is exclusive;
6. observed owned routes are a **strict subset** of desired routes;
7. every terminal Profile blackhole remains installed;
8. there is no extra/stale owned route.

Under those conditions the repair only adds desired route state. The terminal blackhole
prevents broader-rule fall-through while the route is absent, and `ip route add` installs
the route atomically. Global `ip_forward=0` buys no additional fail-open protection.

This model also safely repairs an unexpectedly missing normal route with otherwise exact
state. It does **not** generalize structural drift into incremental repair: any extra route,
missing blackhole, RPDB difference or policy-generation uncertainty remains structural.

## Findings

### F1 — route-only promotion needed an explicit transition category

Severity: medium/high liveness/availability.

Disposition: fixed with `TransitionKind.ROUTE_ADDITIVE`.

### F2 — architecture only described binding/availability incremental transitions

Severity: medium documentation/maintenance.

Disposition: fixed with invariant 79 defining the exact route-additive proof boundary.

## Rust-alignment review

The transition is represented as an explicit enum variant backed by pure proof predicates.
A Rust port can preserve the same closed transition algebra rather than infer behavior from
mutation contents.

## Verdict

Approved after F1/F2 corrections. No remaining recommendation in this transition scope.

The full production-cycle kernel integration remains the evidence gate.
