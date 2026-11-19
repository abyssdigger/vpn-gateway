# NG3 2026-11-19 — continuous availability loop 35m CD checkpoint

**Cycle:** `ng3-design-cycle-20261119-probe-continuous-availability-loop-35m`  
**CYCLE_INTERVAL:** 35m  
**Base:** Main snapshot 115 `d88acb4797086025a68b1b4ce573ce5264d0c3fc`

## Verdict

**PASS — the Release-1 ICMP availability path is assembled continuously in the Python alpha
and has real two-path failover/recovery evidence.**

No product decision was required during the cycle.

## Snapshot sequence

### Main snapshot 116 — evidence to effective order

`76e06117b77e04f2b445349cecab012718324ea1`

Added bounded `AvailabilityManager` composition:

```text
fresh current ProbeEvidence
    -> degradation/recovery confirmation
    -> established problem owners
    -> sticky/reserve Profile effective order
```

Context replacement resets confirmation progress and stale evidence is rejected again at the
Manager boundary.

### Main snapshot 117 — effective order to route priority

`162617021193f7cb2f4a0087919bc197cef09af3`

Mapped effective Profile order into the existing shared payload metric allocation and
make-before-break route-priority Executor. No availability-specific routing engine, metric
namespace or mutation backend was introduced.

### Main snapshot 118 — bounded observation tick

`ef4355743339eaee531e1b8ed09704ce3bf14d48`

Added one externally triggered observation tick:

- synchronize current subjects;
- require exact probe readiness;
- execute at most one physical check per current subject;
- emit no negative evidence for a local readiness defect;
- apply only fresh evidence to availability state.

No internal scheduler/retry loop was added.

### Main snapshot 119 — continuous alpha assembly

`537dd5a064fff8615f7fde3e1ea113f03a43d01a`

Assembled the Python alpha path:

```text
periodic Manager audit
    -> fresh bindings
    -> Device-default/Profile-override probe intent
    -> shared payload/probe layout
    -> shared composite probe-local nft owner
    -> fail-closed probe route/RPDB convergence
    -> exact readiness
    -> bounded ICMP attempts
    -> confirmation
    -> sticky/reserve effective order
    -> make-before-break route-priority convergence
    -> current status
```

A critical in-cycle correction prevents the structural reconcile from restoring baseline
metrics after availability failover: baseline order is retained as policy input, while
structural desired state is rebuilt from the current effective order.

The alpha now accepts canonical `availability_check`; `+snat` remains independently
unmaterialized and fail-fast.

Current status reports `disabled`, `unconfirmed`, `monitoring` or `problem` rather than
leaving successful availability operation permanently `unconfirmed`.

### Main snapshot 120 — privileged two-path proof

`c5a231cd3e947eea63776e40c4023334f3ba56c9`

EXP-068 proves the assembled loop with two real namespace paths.

Observed:

```text
healthy:
    path0 metric 1
    path1 metric 2

remote path0 ICMP failure:
    path1 metric 1
    path0 metric 2

path0 recovery:
    path1 metric 1
    path0 metric 2
```

The last state proves ordinary-path sticky recovery rather than automatic failback.

## Findings fixed in-cycle

### Probe-local nft ICMP representation portability

The first EXP-068 run reached exact probe routing but failed local readiness because current
Ubuntu 26.04 / nftables 1.1.6 represented the IPv4 protocol constant as symbolic `"icmp"`,
while the EXP-066-era decoder accepted only numeric `1`.

The observer now accepts exactly those two equivalent encodings and rejects all other
protocols. Focused unit coverage and the privileged rerun both pass.

### Stale architecture gates

The cycle removed active wording that incorrectly still described:

- the repaired probe `oif` discriminator as broken;
- target derivation as pending;
- outbound per-flow affinity as a Release-1 availability prerequisite;
- probe-local materialization as absent;
- availability runtime assembly as missing;
- RuntimeStatusAgent as disconnected from alpha.

Historical reviews/evidence remain preserved as history.

## CI / evidence

### Continuous runtime integration

NG3 Python run `44506638238`:

- `unit`: PASS;
- `linux-probe-runtime`: PASS;
- `linux-structural-inventory-shape`: PASS;
- `linux-route-priority`: PASS;
- `linux-alpha-smoke`: PASS.

Later status-strengthening run `44507061397` also passed the changed-scope jobs; its overall
failure was only the pre-existing baseline set:

- `linux-nft-marked-host-bootstrap`;
- `linux-profile-gateway-nat-association`;
- `linux-selected-host-bootstrap-backend`.

### EXP-068

NG3 Python run `44508182776`, job `linux-probe-runtime`
(`135505297700`), source `15f8c735d1c0fd667487fe2ff6258d33a934a5d7`:

- `unit`: PASS;
- `linux-structural-inventory-shape`: PASS;
- `linux-probe-runtime`: PASS;
- EXP-067: PASS;
- EXP-068: PASS.

Exact EXP-068 output:

```text
EXP068_HEALTHY_METRICS={'path0': 1, 'path1': 2}
EXP068_FAILOVER_METRICS={'path1': 1, 'path0': 2}
EXP068_RECOVERY_STICKY_METRICS={'path1': 1, 'path0': 2}
EXP068_RESULT=PASS
```

## Requirement-state inventory

No normative requirement changed in this cycle.

### decomp

All accumulated occurrences remain resolved:

- `VPNG0005-R5 -> VPNG0005-R5.R6`;
- `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`;
- `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`;
- `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`.

Repeated occurrences have the same resolved status.

### unreal

none

### broken

none

### rejected_closure

none

## Simplification result

This cycle did **not** introduce:

- a generic probe framework;
- a second nft writer;
- an availability-specific routing engine;
- a second metric/table namespace;
- a global scheduler;
- a retry queue or event journal;
- user-facing timing/hysteresis knobs;
- outbound per-flow affinity solely for availability.

The alpha reuses its existing periodic Manager wakeup and every lower mutation reuses an
already accepted owner/convergence boundary.

## Remaining probing scope

The basic Release-1 ICMP probing loop is no longer an open implementation seam.

Remaining work around availability/probing is now secondary scope, for example:

- production Rust implementation/migration of the accepted runtime behavior;
- stable external status/API packaging beyond the replaceable alpha JSON surface;
- future non-ICMP probe mechanisms only if separately required;
- optional stronger probe-generation conntrack cleanup only if future evidence re-enters
  EXP-026.

These are not blockers for the current Python-alpha Release-1 ICMP availability behavior.

## Conclusion

The cycle began from a safe one-shot probe and ends with a continuously driven, bounded,
Profile/path-scoped ICMP availability loop that has real two-path Linux evidence for failure,
route-priority failover and sticky recovery.
