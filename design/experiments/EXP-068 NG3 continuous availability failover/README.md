# EXP-068 — continuous Release-1 availability failover

## Purpose

Prove the assembled NG3 Release-1 ICMP availability loop on real Linux networking objects,
not only pure/unit composition.

The experiment exercises two simultaneously available logical VPN-path surrogates that have
different ICMP availability targets and one outbound Profile with baseline preference A > B.

## Topology

Three disposable network namespaces are used:

```text
managed
  path0 192.0.2.1/24     <-> remote-a peer0 192.0.2.2/24
  path1 198.51.100.1/24  <-> remote-b peer1 198.51.100.2/24
```

Profile payload destination:

```text
10.77.0.0/16
```

Baseline payload route metrics:

```text
path0 -> metric 1
path1 -> metric 2
```

Availability config:

- Device A default: ICMP to `192.0.2.2`;
- Device B default: ICMP to `198.51.100.2`;
- Profile selects `availability_check = "default"`.

The experiment uses the real NG3 executable contracts:

- `build_probe_desired_assembly`;
- shared Linux probe allocation;
- EXP-066 probe-local nft renderer;
- fail-closed probe route/RPDB convergence;
- exact readiness;
- bound one-shot Linux ICMP Driver;
- `AvailabilityManager`;
- make-before-break route-priority convergence.

For compact evidence, degradation/recovery thresholds are 1/1. This is an experiment-local
choice and does not change the alpha/reference 2/2 runtime policy.

## Sequence

1. Materialize the two payload routes and probe-local nft owner.
2. Run one healthy availability cycle.
   - both probes reply;
   - payload metrics remain A=1, B=2.
3. Install a remote-side nft rule in `remote-a` that drops ICMP.
4. Run one availability cycle.
   - A produces valid negative evidence;
   - B remains positive;
   - effective order changes to B > A;
   - physical metrics converge to A=2, B=1.
5. Remove the remote-side drop.
6. Run one recovery cycle.
   - A produces positive evidence and leaves problem state;
   - B is the current ordinary active path;
   - sticky Release-1 semantics retain B > A;
   - physical metrics remain A=2, B=1.

## Safety

All network, RPDB, route, nft and conntrack state is contained in disposable network
namespaces and removed in `finally`.

The experiment does not modify host routing or host nft policy.

## Pass criteria

The script must print:

```text
EXP068_HEALTHY_METRICS={'path0': 1, 'path1': 2}
EXP068_FAILOVER_METRICS={'path0': 2, 'path1': 1}
EXP068_RECOVERY_STICKY_METRICS={'path0': 2, 'path1': 1}
EXP068_RESULT=PASS
```

Equivalent dictionary formatting/order is acceptable; semantic metric assignments are exact.
