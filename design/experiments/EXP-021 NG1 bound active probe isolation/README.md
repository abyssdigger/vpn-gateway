# EXP-021 — bound active-probe isolation and privilege envelope

**Status:** PASS  
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


## Attempt history

### Attempt 1 — PASS for path isolation, privilege result ambiguous

Observed:

```text
PASS A: ordinary and B-bound probes succeed while both paths are healthy
PASS B: bound probe fails on broken B while unbound probe still succeeds via A
PING_GROUP_RANGE=1 0
REDUCED_PRIVILEGE_BOUND_PING=FAIL
EXP_021_BOUND_PROBE_ISOLATION=PASS
```

The routing hypothesis passed. The privilege result was not yet interpretable because the
first harness also manipulated the capability bounding set and did not prove that the
wrapped command itself reached ping.

### Attempt 2 — HARNESS RECOVERY RACE

The privilege harness was simplified and a namespace-local permissive ping_group_range
check was added. The run then failed immediately after restoring B because the harness
required one instant recovery ping. No privilege conclusion was drawn.

A bounded recovery wait replaced that single probe.

### Attempt 3 — PASS

Final observed result:

```text
PASS A: ordinary and B-bound probes succeed while both paths are healthy
PASS B: bound probe fails on broken B while unbound probe still succeeds via A
PASS C0: B-bound probe recovered after peer link restore
HOST_PING_GROUP_RANGE_BEFORE=1 0
NS_PING_GROUP_RANGE_BEFORE=1 0
UNPRIVILEGED_BOUND_PING_INITIAL=PASS
NS_PING_GROUP_RANGE_AFTER=0 2147483647
HOST_PING_GROUP_RANGE_AFTER=1 0
PASS C: ping_group_range change stayed inside probe namespace
UNPRIVILEGED_BOUND_PING_PERMISSIVE_RANGE=PASS
UNPRIVILEGED_CAP_EFF=0000000000000000
PASS D: ordinary unprivileged ping works with permissive ping_group_range
UNPRIVILEGED_SOURCE_BOUND_PING_HEALTHY=FAIL
EXP_021_BOUND_PROBE_ISOLATION=PASS
```

## Result and architectural consequence

EXP-021 establishes:

1. interface-bound active probing can test one concrete path without silently borrowing a
   different healthy lower-metric route;
2. an ordinary unbound probe is unsuitable as Device availability evidence in a
   multi-path ROU because it can succeed through another Device;
3. source-address-only binding is not a reliable substitute for interface binding in the
   tested competing-route topology;
4. on the hosted runner, interface-bound ping executed successfully from a wrapper with
   zero effective capabilities and no-new-privs;
5. net.ipv4.ping_group_range is namespace-local on the tested kernel.

The experiment therefore does **not** justify adding CAP_NET_RAW to the production service.
The exact target Debian/systemd sandbox must still prove whichever probe implementation is
selected; EXP-018 remains the deployment capability gate.

Future DeviceManager active evidence should bind explicitly to the concrete interface and
must verify that the interface generation observed before and after probing is still the
generation being classified.

Probe target, cadence, timeout and failure/recovery thresholds remain product-policy
questions and are not selected by this experiment.
