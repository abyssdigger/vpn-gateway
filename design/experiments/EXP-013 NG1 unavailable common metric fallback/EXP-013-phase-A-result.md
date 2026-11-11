# EXP-013 Phase A — successful rerun

Date: **2026-11-11**

Status: **PHASE A PASS**

Reported artifact directory:

```text
vpn-gateway-exp-013-20261111-154610Z
```

Harness summary:

```text
A1 direct-dev multipath: PASS
A2 metric ordering: PASS
A3 one nexthop interface deleted: OBSERVED
A4 same-name/new-ifindex return: PASS old=2 new=4
A5 /0 metric ordering: PASS
PHASE_A=PASS
Artifacts: vpn-gateway-exp-013-20261111-154610Z
```

## Established by this run

- Linux accepted one direct-device multipath route containing two nexthops at one common metric.
- The tested metric ordering behaved as required:
  `normal < UNAVAILABLE_METRIC < BLACKHOLE_METRIC`.
- The same ordering passed for the `default` / `0.0.0.0/0` case.
- Deleting one nexthop interface reached the intended A3 observation point.
- Recreating the same interface name produced a fresh identity:
  `ifindex 2 -> ifindex 4`.
- Phase A completed cleanly.

## Still to extract from Phase A artifacts

A3 is intentionally an observation rather than a yes/no assertion. Before Phase B is
finalized, inspect:

- `a3-after-delete-routes.txt`
- `a3-after-delete-routes.json`
- `a3-after-delete-lookup.txt`
- `a3-after-delete-fibmatch.txt`
- corresponding return-code files

The exact kernel behavior after one multipath nexthop interface disappears determines the
TrafficEngine reconciliation expectation.

Phase A closes the **kernel/FIB construction and metric-tail** prerequisite. It does not
close the full EXP-013 gate: Phase B still has to prove the real-VPN/payload semantics,
especially a dead path whose interface remains present.
