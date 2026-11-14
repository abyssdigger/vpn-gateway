# EXP-027 — NG2 route-priority bubble / persistent EMPTY slot

**Status:** COMPLETE — PASS  
**Date:** 2026-11-14  
**Architecture baseline:** NG2 availability priority with persistent EMPTY route slot  
**Environment:** disposable privileged Linux network namespace in GitHub CI

## Purpose

The first EXP-027 pass proved a useful Linux primitive: the same interface may have owned
routes to one destination at different metrics, and replacing one metric does not remove the
other copy.

The production design was then strengthened. Availability priority changes must not
temporarily remove any eligible path, including a non-confirmed one.

The revised invariant is:

```text
N eligible paths
N + 1 ordinary metric slots
steady state: N routes + exactly one EMPTY slot
move add phase: N + 1 routes + exactly one duplicated path
move delete phase: N routes + exactly one EMPTY slot
```

The EMPTY slot sits immediately after the confirmed-live prefix.

## Elementary move hypothesis

Given path `X` at metric `Mold` and the current EMPTY at `Mempty`:

```text
ip route add ... dev X metric Mempty
ip route del ... dev X metric Mold
```

must have these properties:

1. add creates a second copy of `X` without removing its old route;
2. every eligible path remains represented after add;
3. exactly one path is duplicated after add;
4. exact delete removes only the old copy;
5. the old metric becomes the new EMPTY;
6. terminal blackhole remains intact.

No `ip route replace` is required by the production transition.

## Cases

The harness checks both an ordinary prefix and `default`.

### Recovery from inside the dead tail

```text
A B G D . V E J
        ->
A B V G D . E J
```

Completed moves:

```text
D 40 -> 50
G 30 -> 40
V 60 -> 30
```

### Reverse demotion

```text
A B V G D . E J
        ->
A B G D . V E J
```

Completed moves:

```text
V 30 -> 60
G 40 -> 30
D 50 -> 40
```

### Recovery from the far-right slot

```text
A B G D E J . V
        ->
A B V G D E J .
```

Completed moves:

```text
J 60 -> 70
E 50 -> 60
D 40 -> 50
G 30 -> 40
V 80 -> 30
```

The far-right recovered path is therefore not a special case.

## Harness

```text
design/NG2/code/python/rou/tests/integration_route_priority_bubble.py
```

For every elementary move the harness validates the FIB after both the add and delete
phases. It checks the complete eligible path set, duplicate count, EMPTY movement and
terminal blackhole.

## Result

**PASS.**

Observed for both ordinary prefix and `default`:

```text
PASS P1: recovery ABGD.VEJ -> ABVGD.EJ kept every path
PASS P2: demotion ABVGD.EJ -> ABGD.VEJ kept every path
PASS P3: recovery ABGDEJ.V -> ABVGDEJ. kept every path
PASS D1: recovery ABGD.VEJ -> ABVGD.EJ kept every path
PASS D2: demotion ABVGD.EJ -> ABGD.VEJ kept every path
PASS D3: recovery ABGDEJ.V -> ABVGDEJ. kept every path
EXP027=PASS
```

## Architectural consequence

NG2 may use one persistent EMPTY metric slot per payload routing-domain destination and
materialize pure priority permutations as repeated:

```text
add duplicate into EMPTY
delete old copy
```

This keeps the complete eligible route set present throughout the transition. A second
routing table and a forwarding barrier are not required for this narrow case.

Any broader diff, failed precondition, failed mutation or failed final verification falls
back to the existing structural fail-closed rebuild.

## Historical note

The first harness attempt used dummy links and failed before route setup; it produced no
routing evidence. The second, veth-based version proved fixed-metric `replace` mechanics.

That earlier PASS remains valid kernel evidence, but its top-down replacement sequence is
superseded as the production strategy by the stronger persistent-EMPTY experiment above.
