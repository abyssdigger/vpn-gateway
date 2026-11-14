# NG2 — persistent EMPTY route transitions review

**Date:** 2026-11-14  
**Branch:** `code-cycle-20261114-live-boundary-empty-slot`  
**Scope:** availability-driven route priority, persistent EMPTY slot, Linux materialization, transaction serialization

## Verdict

**PASS** for the cycle scope.

## Findings

### F1 — fixed-slot replace was too weak for the intended invariant

The first EXP-027 pass proved that one interface can coexist at multiple metrics, but
top-down `ip route replace` could temporarily remove an eligible path from the FIB.

**Resolved.** Production materialization now uses one persistent EMPTY metric slot and only:

```text
add duplicate into EMPTY
delete old copy
```

Every eligible path remains represented throughout a transition.

### F2 — EMPTY position is semantic boundary information

Treating EMPTY as an always-trailing Linux-only scratch slot loses the live/non-confirmed
boundary needed by the agreed bubble model.

**Resolved.** Payload/routing intent carries `priority_prefix_length`. Linux projects one
EMPTY metric immediately after that prefix. Generic non-availability routing domains may
leave the field unset and retain the old compact metric projection.

### F3 — recovery needs both live shifting and dead-tail cleanup

Recovery can have already non-confirmed paths between the boundary and the recovered path.

**Resolved and tested.** The planner handles:

```text
A B G D . E V J
        ->
A B V G D . E J
```

as:

```text
D -> EMPTY
G -> new EMPTY
V -> configured live position
E -> lower-priority EMPTY
```

The final move returns EMPTY to the new live/non-confirmed boundary.

### F4 — route transitions must be single-flight per Profile

A newer availability-derived target must not interleave its route moves with an active
transition of the **same Profile**.

**Post-cycle audit correction.** The original cycle closed this with one global
`PayloadTrafficManager` lock. That prevented interleave but represented the wrong
architectural boundary: the agreed caller-visible transaction belongs to Profile route
ordering, not to the whole payload Manager.

The corrected implementation uses exactly one lazily retained
`ProfileRouteOrderExecutor` per Profile for pure priority changes. Its Direct
`execute(target)` does not return until the lower-domain apply/materialize/fresh
verify/commit attempt has completed. A second target of that Profile waits at the same
Executor gate.

Different Profiles have distinct Executor gates. The shared aggregate NetworkRules owner
still has a lower implementation lock so concurrent Profile transactions cannot lose each
other's committed aggregate state; that lock is not the semantic Profile transaction and
does not claim Linux multi-command atomicity.

Regression tests cover same-Profile non-interleaving, independent per-Profile gates and
decomposition of one multi-Profile priority snapshot into completed Profile transactions.

### F5 — EMPTY consumes metric capacity even though it has no route

An all-live maximum-size domain could otherwise have no legal working slot below terminal
blackhole.

**Resolved.** Availability-managed routing validates capacity for `N+1` ordinary slots,
not only the `N` materialized routes.

### F6 — per-flow pinning is not part of this failover mode

A path demoted by availability policy is intentionally not retained as a flow-affinity
target for existing flows.

**Resolved as architecture**, not a missing capability. Flow pinning remains a separate
feature for other modes/settings.

## Complexity / rudiment audit

No second transition planner is retained. The corrected production path is:

```text
confirmed-live prefix
        ->
ordered_paths + priority_prefix_length
        ->
ProfileRouteOrderExecutor(profile)
        ->
NetworkRulesAdapter.apply()
        ->
route_slots()
        ->
plan_route_slot_moves()
        ->
LinuxNetworkExecutor.materialize_route_priority()
        ->
fresh verify / Adapter commit
        ->
Profile Executor returns
```

No staging table, shadow route tier, transition metric class, dead-slot search algorithm,
per-flow connmark machinery, or special recovery algorithm was introduced.

## Evidence

Latest executable gate for commit `414637f9412ff361137922242b0130aec71073c9`:

- 248 NG2 unit tests: PASS;
- privileged Linux integration: PASS;
- EXP-027 ordinary prefix: PASS P1-P4;
- EXP-027 default: PASS D1-D4;
- Linux Adapter A3 route-only fast path: PASS without forwarding or nft mutation;
- NG1 Python validation: PASS.

## Remaining boundary

Production availability good-news/window delivery is still a separate next unit. It must
feed `ordered_paths + priority_prefix_length` without reintroducing per-attempt semantics.

No blocker remains in the route-transition slice.
