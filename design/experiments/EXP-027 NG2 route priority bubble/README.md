# EXP-027 — NG2 route-priority bubble

**Status:** COMPLETE — PASS  
**Date:** 2026-11-14  
**Architecture baseline:** NG2 availability route-priority transition  
**Environment:** disposable privileged Linux network namespace in GitHub CI

## Hypothesis

Availability-driven path priority can be rearranged without a second routing table and
without temporarily removing any eligible path from the FIB.

For one routing-domain destination with `N` eligible paths, the transition machinery may
use one currently unused ordinary metric position as a moving free slot.

The only mutation primitive is:

```text
path X currently at Mold
Mfree currently unused

ip route add ... dev X metric Mfree
ip route del ... dev X metric Mold
```

After the add, every eligible path is still present and exactly one path is duplicated.
After the delete, every eligible path is present exactly once and `Mold` becomes the new
free metric.

The free metric is not a route, configuration object, binding, or persistent state.

## Properties to prove

The experiment checks both an ordinary prefix and `default`:

1. one path may simultaneously own two same-destination routes on different metrics;
2. `ip route add` into a free metric preserves the old copy;
3. exact `ip route del ... dev X metric Mold` removes only the old copy;
4. every add phase preserves the full eligible path set and creates exactly one duplicate;
5. every delete phase restores exactly one route per eligible path;
6. terminal blackhole metric 65536 survives every transition;
7. the same primitive covers recovery, demotion, recovery from the final dead position,
   and death from all-live.

## Tested transitions

The dot denotes only an unused metric position.

```text
recovery:
A B G D . V E J
A B V G D . E J

demotion:
A B V G D . E J
A B G D . V E J

last dead path recovers:
A B G D E J . V
A B V G D E J

death from all-live:
A B V G D E J
A B G D E J . V
```

The all-live state has no steady-state gap. The next ordinary metric after the last path is
simply unused and is available to the first make-before-break move.

Harness:

```text
design/NG2/code/python/rou/tests/integration_route_priority_bubble.py
```

## Result

**PASS.**

Privileged CI passed all four transitions for both the ordinary-prefix and default-route
tables:

```text
PASS P1: ABGD.VEJ -> ABVGD.EJ
PASS P2: ABVGD.EJ -> ABGD.VEJ
PASS P3: ABGDEJ.V -> ABVGDEJ
PASS P4: ABVGDEJ -> ABGDEJ.V

PASS D1: ABGD.VEJ -> ABVGD.EJ
PASS D2: ABVGD.EJ -> ABGD.VEJ
PASS D3: ABGDEJ.V -> ABVGDEJ
PASS D4: ABVGDEJ -> ABGDEJ.V
EXP027=PASS
```

The earlier EXP-027 `ip route replace` result remains historical evidence that one path
can coexist at multiple metrics, but it is superseded as the production transition
strategy. Production uses add-duplicate then delete-old so no eligible path is displaced
even temporarily.

## Architectural consequence

NG2 may use one route-priority transactional Executor per Profile/routing-domain.

A transaction:

1. starts from a freshly verified current projection;
2. computes one deterministic move plan;
3. executes each move as add duplicate -> delete old;
4. freshly verifies the final projection;
5. falls back to structural fail-closed rebuild on any failure.

A new availability state for the same Profile must not interleave with an active
transaction. It may replace/coalesce the pending next desired state, but the running move
plan remains immutable until verification completes.

A staging routing table is not required for ordinary path-priority permutation.
