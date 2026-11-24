# NG3 2026-11-18 — bounded availability routing-state review

## Verdict

**PASS for the Manager-owned active-route state projection slice.**

## Scope

This review covers the missing bounded state transition between:

- confirmed current problem-path identities;
- the pure sticky/reserve `AvailabilityPriorityCalculator`;
- one remembered current active logical path for one Profile.

It does not activate probing or availability end to end in the alpha runtime.

## Implementation

`availability_routing_state.py` adds two small immutable values:

```text
AvailabilityRoutingState
    active_path: LogicalPathId | None

AvailabilityRoutingProjection
    next_state
    effective_order
```

and one pure transition:

```text
project_availability_routing(
    configured_paths,
    problem_paths,
    previous_state,
    reserve_device_ids,
)
```

The transition delegates ordering to the already reviewed
`calculate_effective_path_order()` and derives the next active identity from the first
currently usable path in that effective order.

## State semantics

Reviewed transitions:

```text
no previous active + usable paths
    -> first usable baseline path becomes active

active becomes problematic
    -> next usable effective path becomes active

ordinary active remains usable while a higher-baseline path recovers
    -> active identity stays unchanged

reserve active remains usable while a higher-baseline path recovers
    -> recovered higher-baseline path becomes active

previous active disappears from current structural membership
    -> stale active identity is discarded
    -> first current usable path becomes active

all current paths problematic / no current paths
    -> active identity becomes None
```

A disappeared previous active path is intentionally not passed as malformed current input to
the strict priority calculator. By contrast, stale/foreign problem-path identities remain a
caller error and are still rejected by the calculator.

## Simplification review

The state added by this slice is exactly one optional `LogicalPathId` per Profile.

It does not add:

- per-flow state;
- source/destination tuple tracking;
- conntrack ownership;
- timeout/GC lifecycle;
- packet history;
- transport-session migration state;
- a new asynchronous Manager or Engine.

The helper is pure state-transition logic inside existing `PayloadTrafficManager` ownership,
following the same pattern as the existing availability confirmation helper.

## Tests

`test_availability_routing_state.py` covers:

- initial active selection;
- active-path failure;
- sticky ordinary recovery;
- reserve failback;
- disappeared active identity;
- all-paths-problematic state;
- empty current membership.

GitHub Actions run `44398922372` on implementation commit
`bf8b993a7b8beedef768db3c22aa746697140c29` reports the `unit` job **PASS**.

The consolidated EXP-060 privileged evidence job retains its already documented pre-existing
runtime failure and is unrelated to this pure state projection.

## Architecture fit

The executable architecture trace now maps
`availability_confirmation.py` plus `availability_routing_state.py` to the bounded
availability state owned by `PayloadTrafficManager`.

The state projection supplies exactly the `current_active_path` ownership required by the
accepted sticky/reserve design. Physical route realization remains below the Manager, and
probing/confirmation remains a separate concern.

## Requirement-state inventory

This slice creates no active:

- `decomp`;
- `unreal`;
- `broken`;
- `[rejected_closure]`.

## Remaining boundary

Release-1 alpha still explicitly rejects `availability_check` because probe execution,
confirmation-state orchestration and route-priority convergence have not yet been assembled
into one runtime loop.

That integration is a separate implementation unit. The active-route state model itself is no
longer missing and does not require flow tracking.

## Conclusion

The accepted recovery semantics now have an executable bounded state owner:

```text
confirmed path health
    + previous Profile active identity
    + Profile-local reserve Device IDs
        -> effective order
        -> next Profile active identity
```

The result stays at Profile/path scale and preserves the simplification that motivated the
sticky-route refactor.
