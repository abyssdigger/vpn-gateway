# EXP-027 — NG2 route-priority bubble

**Status:** COMPLETE — PASS  
**Date:** 2026-11-14  
**Architecture baseline:** NG2 availability bubble candidate  
**Environment:** disposable privileged Linux network namespace in GitHub CI

## Hypothesis

NG2 can materialize an availability-driven path permutation without a second routing table
or full forwarding barrier by treating each normal route metric as a replaceable slot.

For:

```text
A B C D
- + + -
```

the semantic target is:

```text
B C A D
```

The proposed kernel sequence is:

```text
A10 B20 C30 D40
B10 B20 C30 D40
B10 C20 C30 D40
B10 C20 A30 D40
```

The temporary duplicate path is intentional. A displaced non-confirmed path may be absent
from its old slot while a confirmed-live replacement is already present.

## Properties to prove

The experiment checks both an ordinary prefix and `default`:

1. `ip route replace` can replace one fixed-metric unicast slot with another interface;
2. an existing route for the replacement interface at a different metric survives;
3. repeated slot replacement converges to the desired bubble permutation;
4. the terminal blackhole at metric 65536 survives every transition;
5. no delete-then-add gap is required by the userspace mutation sequence.

The experiment does not claim multi-command kernel transaction atomicity. It proves the
smaller property required by the design: each promoted slot is installed by one route
replace operation before the next slot is changed.

## Procedure

The CI harness creates one namespace and four dummy interfaces, then builds independent
tables for:

- `198.51.100.0/24`;
- `default`.

Each table starts with normal routes at metrics 10/20/30/40 and a terminal blackhole at
65536. The harness applies the three replacements above and validates the complete JSON FIB
projection after every step.

Harness:

```text
design/NG2/code/python/rou/tests/integration_route_priority_bubble.py
```

## Architectural consequence

If PASS, NG2 may implement a narrow route-priority fast path using fixed metric slots and
make-before-displace bubble replacement. Staging routing tables are not required for
ordinary availability priority changes.

If FAIL, the exact observed route semantics are retained here and the route transition
design must be revised before implementation.


## Attempt 1 — harness failure

GitHub privileged CI reached EXP-027 but failed before route setup while creating a
`dummy` link in the disposable namespace. No route replacement command ran, therefore
this is **not** evidence for or against the routing hypothesis.

Disposition: replace dummy links with veth pairs. Veth is already exercised successfully by
the existing NG2 privileged integration suite on the same runner class.


## Successful run

Privileged GitHub CI completed the veth-based second attempt:

```text
PASS P1: metric-10 slot replaced A->B while B metric-20 survived
PASS P2: metric-20 slot replaced B->C while C metric-30 survived
PASS P3: bubble transition converged A,B,C,D -> B,C,A,D
PASS D1: metric-10 slot replaced A->B while B metric-20 survived
PASS D2: metric-20 slot replaced B->C while C metric-30 survived
PASS D3: bubble transition converged A,B,C,D -> B,C,A,D
EXP027=PASS
```

`P` is the ordinary-prefix table and `D` is the default-route table.

The terminal blackhole remained present after every checked transition because every
intermediate projection was validated before the next replacement.

## Result

**PASS.**

For the tested Linux/iproute2 environment, fixed metric positions can be treated as route
slots for a pure path-order permutation. `ip route replace` changes one slot without
removing the same interface from another metric, so the bubble transition needs neither a
staging routing table nor delete-before-add of the promoted path.

Production code still requires fresh pre/post verification and must fall back to the
structural fail-closed path when the requested change is not a pure path-order permutation.
