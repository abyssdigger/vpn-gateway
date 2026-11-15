# NG2 milestone review — executable network-policy assembly

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-runtime-assembly-40m`  
**Scope:** whole current NG2 network-policy runtime slice after assembly milestone

## Verdict

**PASS after accepted fixes.**

The reviewed slice now has a coherent executable object graph from normalized availability
configuration through physical probing, payload-priority updates, shared NetworkRules
ownership and protective startup.

No unresolved finding of minor severity or higher remains in the reviewed scope.

## Reviewed components

- `runtime_assembly.py`;
- `runtime_bootstrap.py`;
- `PayloadTrafficManager`;
- `AvailabilityProbeManager`;
- `LinuxProbeExecutionAgent`;
- availability collector/contracts;
- probe rules/transport;
- shared `NetworkRulesAdapter` ownership boundary;
- Linux instance/bootstrap lifecycle;
- active runtime/bootstrap/payload/availability architecture documents.

## F1 — runtime availability projections must be siblings

**Classification:** accepted and fixed.

The first assembly draft derived `AvailabilityPriorityConfig` from
`AvailabilityProbeSetRequest`.

That left physical-probe vocabulary as the source of the payload-facing projection.

Fixed by introducing immutable `RuntimeAvailabilityConfig` as the common explicit input:

```text
RuntimeAvailabilityConfig
    +--> AvailabilityProbeSetCalculator
    +--> AvailabilityPriorityConfigCalculator
```

Neither derived domain contract is now the source of the other.

## F2 — RuntimeAvailabilityConfig must not become a second state engine

**Classification:** reviewed and retained.

The type is justified as the smallest explicit common input currently available before the
general config/selection/binding layer exists.

It owns no:

- availability status;
- counters/latches;
- physical generation;
- route order;
- materialized state;
- historical state.

Removing it now would either couple the two projections again or invent an upstream config
model that the Python reference does not yet have.

## F3 — config fanout object was an unnecessary pseudo-component

**Classification:** accepted and fixed.

The initial `AvailabilityConfigFanout` had no domain/state of its own. It only calculated
two projections and imposed one call order.

It was removed. Ordered fanout is now ordinary
`LinuxAvailabilityRuntimeAssembly.configure()` behavior:

```text
calculate both projections
PayloadTrafficManager.configure_availability(priority)
AvailabilityProbeManager.handle_request(probes)
```

This remains ordered assembly, not a cross-Manager transaction.

## F4 — specialized forwarding ports were unjustified artifacts

**Classification:** accepted and fixed.

Three one-method forwarding wrappers were collapsed into one generic process-local
`CallbackPublisher`.

Publisher callbacks remain synchronous, return values are deliberately ignored, and no
EventEnvelope/revision queue was introduced.

## F5 — protective bootstrap leaked into steady-state assembly

**Classification:** accepted and fixed.

Network-policy bootstrap helpers were initially implemented in `runtime_assembly.py`.

They were moved to `runtime_bootstrap.py`, restoring the established boundary:

```text
runtime_bootstrap.py
    instance/protective startup composition

runtime_assembly.py
    already-created component graph and steady-state lifecycle
```

Current `runtime_assembly.py` is **349 lines / 10 top-level definitions**, down from the
pre-review **492 lines / 17 definitions**.

## F6 — audit of independent owners stopped after peer exception

**Classification:** accepted and fixed.

Probe and payload rules are separate Adapter owner scopes. An unexpected exception while
auditing the probe owner must not prevent an attempt to audit payload owner state.

Outer audit now uses fail-independent sequencing:

```python
try:
    probe_manager.audit()
finally:
    payload_manager.audit()
```

The original exception still propagates; no synthetic global state is invented.

## F7 — runtime could be restarted after terminal cleanup into incoherent state

**Classification:** accepted and fixed.

Previously `stop()` quiesced/cleaned Managers, but the exposed Agent remained technically
restartable. `start()` after stop would therefore create a thread with no coherent
current runtime plan.

Both availability assembly and outer network-policy runtime now treat `stop()` as a
terminal lifecycle boundary:

- `start`, configure/request and audit after stop raise;
- repeated `stop()` remains allowed so idempotent cleanup/retry semantics are preserved.

## F8 — cleanup of one owner must not suppress the other owner cleanup

**Classification:** accepted and covered.

Outer stop always attempts payload cleanup even if probe cleanup:

- returns FAILURE; or
- raises unexpectedly.

The two `ActionResult` values remain separate when both calls return normally.

## F9 — shared Adapter must not collapse Manager ownership

**Classification:** satisfied.

The same owner-composing `NetworkRulesAdapter` instance may serve both Managers, while
each Manager passes its own `self` identity.

Tests prove probe and payload owners remain distinct and are independently audited/cleaned.

## F10 — full-instance startup must preserve protective double-close

**Classification:** satisfied.

The full-instance path remains:

```text
ensure_linux_instance
    -> close + exact infrastructure verify

independent Adapter bootstrap
    -> close + fresh readback verify

build LinuxNetworkPolicyRuntime
```

Rootless existing-instance simulation proves both protective close passes. Runtime exposure
cannot bypass the lower bootstrap result.

## F11 — synchronous dependency graph

**Classification:** PASS.

Current visible synchronous shape is acyclic:

```text
LinuxNetworkPolicyRuntime
    -> PayloadTrafficManager
    -> LinuxAvailabilityRuntimeAssembly
         -> AvailabilityProbeManager
              -> CallbackPublisher
                   -> ProbeExecutionAgent.update_plan

ProbeExecutionAgent workers/timer
    -> CallbackPublisher
         -> PayloadTrafficManager availability ingress
```

PayloadTrafficManager has no synchronous dependency back to ProbeManager/Agent.

The later Agent -> PayloadManager path is producer delivery from the Agent execution flow,
not a synchronous back-edge from a Manager call chain.

## F12 — structural payload projection/status/audit scheduler

**Classification:** not implemented; correctly left outside this milestone.

The Python reference still lacks the upstream structural config/selection/binding model
needed to derive `PayloadTrafficStateRequest` without inventing a new schema.

Likewise final Profile/status semantics and periodic audit cadence policy are not yet
defined strongly enough to justify implementation.

These are remaining review units, not reasons to add placeholder state/event layers to the
current assembly.

## Test history

One CI failure occurred in this cycle:

- run 641: one shutdown regression failed because the test incorrectly assumed
  `start(); stop()` allowed no initial send.

The Agent intentionally schedules an immediate first send. The test was corrected to the
real invariant: send count cannot increase after stop.

No production rollback was required.

Final reviewed code head:

`123cb25c419d8d5dc9543992c44462d925e4cbce`

GitHub Actions `NG2 Python` run **691**:

- compile: PASS;
- **300 rootless unit tests PASS**;
- selective probe-process isolation: PASS;
- EXP-025: PASS;
- EXP-026: PASS;
- EXP-027: PASS;
- nft ICMP selector: PASS;
- Linux instance lifecycle: PASS;
- Linux Adapter: PASS;
- Linux LOCAL_PROCESS: PASS;
- Linux dataplane: PASS.

No new target/kernel claim was introduced; no new external experiment is required.

## Remaining work

Unblocked only when its upstream semantics are explicit:

1. structural config/selection/binding -> `PayloadTrafficStateRequest`;
2. final RuntimeStateManager/ProfileState/status aggregation;
3. probe diagnostic consumption by that status layer;
4. explicit periodic audit/retry cadence policy;
5. production asynchronous Event Delivery only for streams that genuinely require it.

The availability and Linux network-policy object graph itself has no unresolved assembly
finding.
