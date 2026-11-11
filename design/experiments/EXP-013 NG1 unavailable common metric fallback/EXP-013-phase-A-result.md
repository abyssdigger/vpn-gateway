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

## A3 interpretation

The uploaded A3 artifacts establish the tested kernel behavior precisely.

After deleting `path-a`:

- `path-b` remained present and UP with ifindex 3;
- the entire common-metric multipath route disappeared from table 313;
- the only route left for the target was the terminal blackhole at metric 65536;
- ordinary and `fibmatch` lookups both returned rc=2 / `Invalid argument`, consistent
  with the blackhole being the terminal result.

Therefore this kernel does **not** automatically shrink the direct-dev multipath route to
its surviving nexthop when one member interface disappears.

TrafficEngine must treat that disappearance as a safe binding-lifecycle transition:
temporary blackhole-only state is fail-closed, and reconciliation must rebuild fallback
membership from the fresh surviving binding set.

The candidate production shape for Phase B is consequently:

- maintain one **shadow fallback** at `UNAVAILABLE_METRIC` for all currently bound
  interfaces;
- availability changes add/remove only each interface's normal route;
- binding ADD/REMOVE rebuilds fallback membership;
- one bound interface uses a plain direct-dev fallback route;
- two or more bound interfaces use one direct-dev multipath fallback route.

Phase A closes the **kernel/FIB construction and metric-tail** prerequisite. It does not
close the full EXP-013 gate: Phase B still has to prove this shadow-fallback model on real
VPN interfaces/payload, especially a dead path whose interface remains present.
