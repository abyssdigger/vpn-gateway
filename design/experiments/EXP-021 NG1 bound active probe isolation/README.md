# EXP-021 — bound active-probe isolation and privilege envelope

**Status:** PREPARED  
**Architecture baseline:** NG1 Draft 5 + EXP-019/020  
**Type:** disposable kernel/userspace probe-path experiment

## Purpose

Before DeviceManager can turn active path evidence into normalized availability, prove that
a probe can test one concrete tunnel-like interface without silently succeeding through a
different healthy path, and determine whether the production ROU service privilege envelope
can execute that probe without adding CAP_NET_RAW.

EXP-019/020 proved that active path probes distinguish retained-generation outages, but the
harnesses ran as root and did not test competing-path isolation.

## Questions

1. With two routes to the same probe target, does `ping -I <interface>` remain constrained
   to that interface even when another lower-metric path is healthy?
2. When the selected path is broken but the alternative remains healthy, does the
   interface-bound probe fail while an unbound probe still succeeds?
3. Can the same interface-bound ICMP probe run with:
   - no-new-privs;
   - CAP_NET_RAW removed from the capability bounding set;
   - no inheritable/ambient capabilities;
   using the hosted-runner kernel's unprivileged ping-socket path?
4. If privilege-reduced probing fails, is the failure a capability limitation rather than
   a routing ambiguity?

## Disposable topology

Three namespaces:

```text
          192.0.2.0/30
       R ---------------- A
       |
       | 192.0.2.4/30
       |
       B

A and B both own probe target 198.18.21.1/32.
R has two routes to that target:
  A metric 10
  B metric 20
```

The duplicate target is intentional: an unbound probe can still succeed through A after B
is broken. A probe explicitly bound to R's B-side interface must not borrow A.

## Procedure

1. create namespaces/veth links and duplicate target addresses;
2. install the two routes on R;
3. prove ordinary unbound ping succeeds;
4. prove `ping -I <B-side-if>` succeeds while B is healthy;
5. break only B's peer link;
6. prove:
   - unbound ping still succeeds through A;
   - the B-bound probe fails;
7. restore B;
8. run the B-bound probe through `setpriv` with no-new-privs and CAP_NET_RAW removed;
9. record the relevant ping-group sysctl and exact reduced-privilege result.

## Interpretation

- If step 6 passes, interface-bound active evidence can distinguish one path from a healthy
  alternative at the command/kernel level.
- If step 8 passes, ICMP probing may be feasible without widening the current service
  capability set on kernels configured for unprivileged ping sockets.
- If step 8 fails, DeviceManager must not silently add CAP_NET_RAW. That would be a
  security-boundary change requiring human agreement; alternatives such as a dedicated
  helper or non-raw protocol-specific probe must be considered.

This experiment does **not** choose probe target, cadence or failure/recovery thresholds.

## Artifact

`exp-021-bound-probe-ci.sh`
