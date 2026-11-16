# EXP-027 — result

Date: 2026-11-14

Result: **PASS**

Environment:

- GitHub privileged Linux runner;
- disposable network namespace;
- veth path interfaces;
- one table for `198.51.100.0/24`;
- one table for `default`;
- owned unicast protocol 202;
- terminal blackhole protocol 201, metric 65536.

Verified primitive:

```text
add moving path at currently unused metric
delete only its old route
```

Observed invariants:

- the complete eligible path set remained present at every checked step;
- between add and delete exactly one path had two route copies;
- after delete every path again had exactly one copy;
- the deleted source metric became the next free metric;
- terminal blackhole remained present;
- ordinary-prefix and default-route behavior matched.

Passed transition classes:

```text
ABGD.VEJ -> ABVGD.EJ
ABVGD.EJ -> ABGD.VEJ
ABGDEJ.V -> ABVGDEJ
ABVGDEJ -> ABGDEJ.V
```

The fourth case proves that an all-live steady state does not need a materialized or
configured gap: the next unused ordinary metric is sufficient for the first move.

Architectural consequence:

- no eligible route is intentionally removed as scratch space;
- no dedicated transition route/table is required;
- the free metric is inferred operationally, not stored as a semantic object;
- one active route-priority transaction per Profile/routing-domain must complete and verify
  before another desired priority state can start materialization.
