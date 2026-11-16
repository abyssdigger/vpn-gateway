# NG2 review — availability simplification migration

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-availability-simplification-40m`  
**Scope:** complete executable availability path from ProbeRules through route priority

## Review question

Did the new `availability_problems` model actually remove the obsolete availability
machinery, or merely move the same complexity into different classes?

## Result

**PASS.**

The availability path is materially smaller in both concepts and code. The old
window/evidence/runtime-mediation architecture is deleted rather than wrapped.

## Findings

### F1 — AvailabilityProbeManager still owned routing evidence/window state

**Disposition:** accepted and fixed.

The Manager was reduced to:

- ProbeRules/readiness;
- physical `ProbeObservationGeneration`;
- `ProbeExecutionPlan | None` publication.

Removed from it:

- AvailabilityProbeStateInfo publication;
- good-news handling;
- window state;
- boundary handling;
- logical evidence epochs;
- routing hysteresis.

### F2 — ProbeExecutionAgent still implemented logical observation windows

**Disposition:** accepted and fixed.

Execution now schedules only:

- deduplicated physical sends;
- one logical tick cadence per channel.

Removed:

- LogicalProbeWindow;
- ProbeWindowBoundaryInfo;
- evidence_epoch;
- elapsed_intervals;
- boundary catch-up;
- boundary-before-send semantic ordering;
- the good-news/window source-order lock.

Delayed wake-up emits at most one current tick and one current physical send.

### F3 — routing availability still crossed RuntimeStateManager through derived evidence

**Disposition:** accepted and fixed.

Deleted executable artifacts:

- `availability_routing.py`;
- `payload_traffic_intent.py`;
- the old availability-specific `runtime_state_manager.py` slice.

`PayloadTrafficManager` now owns the bounded collector and directly derives route
priority from current `availability_problems`.

### F4 — stale logical callbacks still need rejection, but not an epoch

**Disposition:** accepted and fixed without reintroducing version machinery.

`ProbeGoodNewsInfo` and `ProbeTickInfo` carry the complete immutable current
`LogicalProbeChannel` descriptor. PayloadTrafficManager accepts input only if that
descriptor still matches the current logical probe definition.

The only retained generation token is `ProbeObservationGeneration`, scoped to physical
stale-worker rejection.

### F5 — repeated identical payload intent unnecessarily re-materialized

**Disposition:** accepted and fixed.

`PayloadTrafficManager` now suppresses materialization when the calculated effective
payload request is unchanged. Drift detection belongs to `audit()`, not to replaying an
identical RequestEvent.

Two old tests that depended on duplicate-request side effects were corrected accordingly.

### F6 — multiple probes assigned to one path could make negative evidence too aggressive

**Finding:** the first integration draft marked a path problematic if any assigned enabled
probe had problems.

That contradicted the earlier positive-evidence behavior: one functioning probe path
should be sufficient not to demote the payload path.

**Disposition:** accepted and fixed.

For one Profile/path, the path-level problem flag is true only if **all enabled assigned
logical probes for that path** currently have `availability_problems=true`.

A dedicated regression covers this.

### F7 — terminology still exposed the superseded confirmed-live model

**Disposition:** accepted and fixed.

Runtime/materialization field:

```text
confirmed_live_prefix_length
```

was renamed to:

```text
no_problem_prefix_length
```

across payload rules, common network rules, Linux routing/network projection, unit tests
and privileged integration scripts.

Active architecture documents were rewritten around `availability_problems`.

### F8 — collector required no separate thread or queue

**Disposition:** intentional simplification retained.

Producer ingress updates bounded state under the Manager's short serial lock.

- if the sole reconcile executor is busy, ingress returns after recording the fact;
- if it is idle, that caller can become the executor and drain the collector
  synchronously.

No dedicated collector thread, ping queue, tick queue, materializer-ready notification or
availability route-plan queue is required.

This depends on the explicitly accepted operating assumption that route-priority
materialization is millisecond-scale while probe cadence is second-scale.

## Removed artifacts

Production modules removed:

1. `availability_routing.py`;
2. `payload_traffic_intent.py`;
3. old availability-specific `runtime_state_manager.py`.

Obsolete flow/test artifacts removed:

1. `test_availability_routing.py`;
2. `test_availability_runtime_flow.py`;
3. `test_payload_traffic_intent.py`;
4. `test_probe_execution_flow.py`;
5. `test_runtime_state_manager.py`.

The remaining `availability_probe_state.py` contains only the physical generation guard.

## Code-size evidence

Compared with cycle base
`4fe5af43b8891505bfbaae0f27b8a0c70b4471c6`, the final tested code baseline
`857ea3192bfe9f63e8567bf3f598b1b00f30c5d7` changes executable Python by:

```text
production: +671 / -1310  => net -639 lines
tests:      +614 / -2535  => net -1921 lines
```

The larger `PayloadTrafficManager` is therefore not a relocation of equal complexity:
overall executable production code is substantially smaller, while multiple state/event
layers disappeared.

## Evidence

Final code-bearing CI:

- workflow: `NG2 Python`
- run: **579**
- compile: PASS
- rootless unit suite: **278 tests PASS**
- privileged Linux integration: PASS
- selective probe-process isolation: PASS
- EXP-025 stale probe conntrack generation: PASS
- EXP-026 probe-class conntrack cleanup: PASS
- EXP-027 route-priority transition: PASS
- Linux nft ICMP selector: PASS
- Linux instance lifecycle: PASS
- Linux Adapter: PASS
- Linux LOCAL_PROCESS: PASS
- Linux dataplane: PASS

No new kernel behavior was introduced; no new target experiment is required.

## Remaining work

Not availability-state machinery:

- runtime assembly/fanout of structural payload + probe assignment configuration;
- connection of ProbeExecutionAgent good-news/tick publishers to PayloadTrafficManager
  ingress;
- status projection of probe execution diagnostics;
- general Event Delivery ordering only for other asynchronous streams that need it.

No unresolved finding remains in this review unit.
