# NG3 combined probe-plane alpha runtime review — 2026-11-25

**Review unit:** production alpha lower convergence for combined A.007 + D.002 probe owners  
**Reviewed implementation head:** `4ae8735965970103690780e134f93ee4e64deee3`  
**Requirement:** `VPNG-U001-R1.R3.R8`  
**Architecture:** A.001, A.007, C.001, D.002  
**Evidence:** `EV-00210`

## Verdict

**PASS — production alpha now materializes one complete A.007+D.002 physical probe plane while
A.007 continues to execute and publish evidence only for its own semantic owners.**

This review does not claim D.002 production scheduling, D.002 status publication or
A.007/D.002 generation coupling. Those remain the next runtime frontier.

## Findings and dispositions

### F1 — only current managed-WireGuard paths may demand D.002 lower probe state

**Decision:** accepted.

Normalized WireGuard groups are projected against the current payload Profile paths. An absent
Device path contributes no peer/group probe demand. More than one current logical path for one
managed WireGuard Device is rejected as ambiguous instead of choosing one implicitly. Peer
technical intent is de-duplicated by stable `(device_id, peer_id)`; group intent retains stable
`(profile_id, device_id)`.

### F2 — production alpha must use the same allocation for payload and every probe owner

**Decision:** accepted.

`AlphaPreparedPolicy.build_current()` now resolves A.007 intents, projects current D.002
peer/group intents and calls `build_probe_plane_desired_assembly()` once. Its layout is used by
payload policy, and its complete local probe rules enter the structural nft desired state.

### F3 — probe routing/readiness must use the full accepted union

**Decision:** accepted.

`run_linux_availability_cycle_once()` converges `assembly.probe` as the full routing union.
For a combined assembly it then uses
`verify_probe_execution_precondition_scoped(snapshot, full_desired, A007_owners, platform)`.
Thus missing sibling lower state does not fabricate A.007 remote failure, while stale/conflicting
owned physical state outside the full union remains globally blocking.

### F4 — lower materialization must not execute D.002 from the A.007 Agent

**Decision:** accepted and directly tested.

Both `AlphaPreparedPolicy` and the observation tick configure
`AvailabilityProbeRuntime` only with `availability_intents`. The focused combined-tick test
contains a D.002 peer owner in the full desired union but observes attempts only for A.007
Profile owners.

### F5 — existing A.007-only direct experiment/test seam remains valid

**Decision:** accepted.

`run_linux_availability_cycle_once()` and `run_availability_observation_tick()` retain
`ProbeDesiredAssembly` compatibility. Legacy callers keep whole-scope readiness semantics;
production alpha uses `ProbePlaneDesiredAssembly`.

### F6 — generation/status responsibilities are not silently pulled into C.001

**Decision:** accepted as remaining scope.

No D.002 Manager trigger, ownership decision, peer/group physical attempt or status projection
was added here. A.007 current evidence still lacks D.002 generation in its freshness key; that
must be solved after production Manager reconciliation exists.

## Evidence

- runtime wiring: `bae3cbbee7808ffb3ae02f88465c4705f592d68f`;
- scoped-consumption test: `ede34c95f722b9fd2c270bb9b5578f2221f573f3`;
- test import correction: `4ae8735965970103690780e134f93ee4e64deee3`;
- run `45583717575`, unit job `139100000005` — **PASS**;
- actual-main lineage run `45583717414` — **PASS**.

## Remaining frontier

Instantiate and retain D.002 Manager(s) for current managed WireGuard Devices, provide one
bounded periodic/explicit production reconciliation trigger using the already materialized
peer/group probe contexts, and publish truthful current D.002 realization/status. After that,
extend A.007 context freshness with the applicable D.002 generation so ownership transfer
invalidates older Profile evidence even when `LogicalPathId`, interface name and ifindex stay
unchanged.
