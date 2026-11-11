# EXP-013 Phase B — result

Date: 2026-11-11

Result: **PASS**

Live environment:

- Debian 13 ROU test gateway;
- ROU v0 private network namespace;
- two real OpenConnect/ocserv DTLS bindings;
- bindings observed as `vpns00` and `vpns01`;
- payload target: `172.21.201.19`;
- experiment routing table: 313;
- experiment RPDB priority: 50;
- `UNAVAILABLE_METRIC=65535`;
- `BLACKHOLE_METRIC=65536`.

The payload target was powered on and the external/intermediate firewall was explicitly
opened for the experiment ICMP path before the successful run.

## Successful live run

The harness reported:

```text
PASS B0: two real DTLS bindings A=vpns00 B=vpns01; only controller frozen
PASS B1: normal A wins above persistent shadow fallback
PASS B2: demoting A removes only its normal route; B wins
PASS B3: common fallback carries real payload via vpns01
PASS B4a: fixed flow hits blocked fallback member vpns01 and is not retried
PASS B4: alternate path is healthy; ECMP fallback does not retry failed selected member
PASS B5: promotion restores normal A above unchanged shadow fallback
PASS B6: real-VPN /0 ordering normal > common fallback > blackhole
PHASE_B=PASS
```

Local artifact directory from the successful run, expressed relative to this experiment
directory:

```text
vpn-gateway-exp-013-phase-b-20261111-185309Z/
```

No host username or absolute home path is part of the recorded experiment contract.

## Observed semantics

### B1 — normal tier beats shadow fallback

With normal routes at metrics 10 and 20, plus the persistent common fallback at 65535 and
blackhole at 65536, A won lookup and real payload traversed A.

### B2 — demotion removes only the normal route

After deleting A's normal route, B won at its unchanged normal metric. The common fallback
remained present.

### B3 — all-normal paths removed

After deleting both normal routes, the common equal-cost fallback carried real payload.
The observed selected member was `vpns01`.

### B4 — ECMP is not sequential failover

The selected fallback member was blocked only for the experiment payload while the
interface remained present.

The fixed flow failed on that selected member. A temporary normal route through the other
member proved that the alternate member itself was healthy. Returning to the common
fallback selected the same blocked member for the fixed flow and Linux did not retry
through the healthy peer.

Therefore the production semantics are:

> common `UNAVAILABLE_METRIC` fallback is ECMP/hash selection, not ordered or sequential
> failover.

This is acceptable because the tier is a last-resort fallback after all normal paths have
been positively demoted.

### B5 — promotion

Restoring A's normal route returned it to the preferred normal tier without changing the
persistent fallback membership.

### B6 — default route

The same ordering was verified with `default`:

```text
normal < UNAVAILABLE_METRIC < BLACKHOLE_METRIC
```

Real payload followed normal, then common fallback, then failed as expected when only the
blackhole default remained.

## Architecture consequence

EXP-013 is complete.

TrafficEngine is authorized to implement persistent shadow fallback:

- every bound Profile path is continuously represented at `UNAVAILABLE_METRIC`;
- UNKNOWN/AVAILABLE also has its stable normal route;
- UNAVAILABLE removes only its normal route;
- one fallback member uses a direct-device route;
- multiple fallback members use one equal-cost direct-device multipath route;
- disappearance of a member interface requires reconciliation to rebuild the multipath
  route from a fresh binding snapshot;
- no implementation or documentation may describe common fallback as sequential failover.
