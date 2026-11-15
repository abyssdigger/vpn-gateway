# NG2 review — executable Linux availability runtime wiring

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-runtime-assembly-40m`  
**Scope:** concrete object graph wiring for current probe execution and payload priority

## Verdict

**PASS after one test correction.**

## Implemented

`runtime_assembly.py` now exposes:

```text
build_linux_availability_runtime(...)
    -> LinuxAvailabilityRuntimeAssembly
```

The builder wires:

```text
AvailabilityProbeManager
    -> ProbeExecutionPlanPort
    -> LinuxProbeExecutionAgent
         +-> AvailabilityGoodNewsPort
         |      -> PayloadTrafficManager
         |
         +-> AvailabilityTickPort
                -> PayloadTrafficManager
```

The same normalized `RuntimeAvailabilityConfig` is fanned out through the two independent
Calculators before the probe Manager may publish a new execution plan.

## F1 — lifecycle ownership must be explicit

**Classification:** accepted and satisfied.

`LinuxAvailabilityRuntimeAssembly` owns:

- the `AvailabilityProbeManager` instance it constructs;
- the `LinuxProbeExecutionAgent` instance it constructs;
- the config fanout between them and the externally owned PayloadTrafficManager.

It does **not** claim ownership of PayloadTrafficManager lifecycle.

`stop()` therefore:

1. shuts down AvailabilityProbeManager;
2. its synchronous plan publisher sends `None` to the Agent before probe-rule cleanup;
3. always stops the Agent in `finally`;
4. returns the probe Manager cleanup ActionResult.

PayloadTrafficManager shutdown remains the responsibility of the outer runtime owner.

## F2 — shutdown must not allow later scheduled sends

**Classification:** accepted and tested.

The first version of the regression incorrectly expected zero sends total after
`start(); stop()`. That is false because an active plan intentionally schedules an
immediate initial send.

The test was corrected to the actual invariant:

> after `stop()` returns, calling `process_due()` cannot increase the send count.

This is a test correction; production behavior was already correct.

## F3 — in-flight worker result after shutdown

**Classification:** satisfied by existing lower tests/contracts.

ProbeManager shutdown invalidates the physical generation and publishes plan `None`
before cleanup. Agent completion checks require the same active generation/plane before
publishing good news.

Existing stale-generation regressions already cover the worker-result guard. No duplicate
assembly-specific worker-race mechanism is justified.

## F4 — shared NetworkRulesAdapter ownership

**Classification:** satisfied.

The builder accepts an explicit `NetworkRulesAdapter` for the probe Manager. Production
may pass the same owner-composing Adapter used by PayloadTrafficManager or another
compatible Adapter.

Ownership remains Manager-instance-scoped because each Manager calls the Adapter with
`owner=self`. The assembly does not synthesize or share an owner identity.

## F5 — no new asynchronous bus

**Classification:** satisfied.

All new edges are synchronous typed calls. The only long-lived asynchronous behavior
remains inside LinuxProbeExecutionAgent's already-reviewed scheduler/workers.

No queue, EventEnvelope, epoch/revision or runtime evidence cache was introduced.

## Evidence

Final code head for this unit:

`b08e9aa1c3a94b7156c02933b145faeb731e59f7`

GitHub Actions `NG2 Python` run **643**:

- compile: PASS;
- **288 rootless unit tests PASS**;
- selective probe-process isolation: PASS;
- EXP-025: PASS;
- EXP-026: PASS;
- EXP-027: PASS;
- nft ICMP selector: PASS;
- Linux instance lifecycle: PASS;
- Linux Adapter: PASS;
- Linux LOCAL_PROCESS: PASS;
- Linux dataplane: PASS.

No new target/kernel experiment is required.

## Remaining boundary

This unit closes executable availability wiring.

Still outside it:

- outer runtime ownership of PayloadTrafficManager lifecycle;
- probe diagnostic/status aggregation;
- structural payload/config/binding projection;
- audit/retry scheduling.

No unresolved finding remains in this unit.
