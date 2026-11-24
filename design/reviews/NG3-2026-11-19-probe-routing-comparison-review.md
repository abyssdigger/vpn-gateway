# NG3 2026-11-19 — probe routing comparison review

## Verdict

**PASS for pure probe route/RPDB actual-vs-desired comparison.**

## Scope

This unit starts from two already reviewed values:

```text
ProbeNetworkPolicyDesiredState
StructuralRoutingObservation
```

and classifies only the reserved probe route/RPDB owner state. It performs no Linux mutation
and does not inspect/compare probe local nft admission yet.

## Implementation

New `probe_routing_compare.py` provides:

```text
compare_probe_routing(
    desired,
    observed,
    platform,
)
    ->
ProbeRoutingComparison
```

The result contains:

- confirmed routes;
- missing routes;
- stale routes;
- confirmed RPDB rules;
- missing RPDB rules;
- stale RPDB rules;
- reserved probe conflicts.

`confirmed` is true only when all six difference/conflict sets are empty.

## Exact physical identities

Probe routes reuse the shared `ManagedRouteSpec` key:

```text
table
destination
route type
protocol
metric
effective scope
current ifname + ifindex
gateway
onlink
```

Therefore same-name interface replacement with a new ifindex does not accidentally confirm a
stale probe path.

Probe RPDB identity is:

```text
priority
table
exact target /32
uid_start = process_uid
uid_end   = process_uid
ipproto   = 1 (ICMP)
no fwmark/fwmask selector
```

This matches EXP-065 and the selected EXP-022 routing discriminator.

## Owner isolation

The comparison consumes from the shared authoritative structural snapshot but filters by the
reserved owner spaces:

```text
probe tables
probe RPDB priorities
probe conflicts
```

Payload tables, payload priorities and payload-only conflicts do not affect probe
confirmation.

This preserves one authoritative lower inventory without merging payload and probe semantic
ownership.

## Verification

GitHub Actions run:

```text
run: 44460178941
head: 9c00ec63575f257c7c96dfbb3bfc774e78900652
unit: PASS — 734 tests
linux-structural-inventory-shape: PASS
```

New tests cover:

- exact probe state;
- UID drift -> missing + stale rule;
- target drift -> missing + stale rule;
- same-name/new-ifindex path replacement;
- explicit probe conflict;
- payload state/conflict non-pollution;
- completely missing probe state.

The known unrelated privileged EXP-057/060/063 failures remain outside this unit.

## Simplification review

No independent observer or duplicate Linux inventory was introduced. Probe comparison reuses:

- the existing whole-reserved `StructuralRoutingObservation`;
- shared `ManagedRouteSpec`;
- shared lower platform resource pools.

Only probe-specific RPDB semantic identity remains separate.

## Requirement-state inventory

No normative R/C changed and this unit creates no active:

- `decomp`;
- `unreal`;
- `broken`;
- `[rejected_closure]`.

## Next boundary

The next autonomous unit is physical route/RPDB mutation for the now exact probe desired and
observed contracts. The route half can reuse the existing shared lower route Driver; probe
RPDB rule add/delete needs the selected EXP-065 selector shape.

Probe local nft admission remains a separate following unit because its physical ownership,
observation and mutation contract is distinct from route/RPDB.

## Conclusion

Probe routing now has the complete pure loop:

```text
normalized probe intent
    -> desired route/RPDB
    -> authoritative whole-reserved observation
    -> probe-owner exact/missing/stale/conflict comparison
```

No user decision is required for the next lower mutation step.
