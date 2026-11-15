# NG2 review — process-local publication and dual-owner failure semantics

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-publisher-failure-recovery-40m`  
**Scope:** adjacent Manager publication boundaries and outer network-policy owner failures

## Verdict

**PASS after two accepted fixes.**

## F1 — PayloadTrafficManager state publication failure

**Disposition:** existing behavior verified; regression added.

A PayloadTrafficStateInfo publisher exception:

- remains visible to the caller;
- does not leave the serialized executor permanently owned;
- does not mark the state as successfully published;
- can be retried by a later `audit()`;
- does not require re-materializing already matched NetworkRules.

The regression proves the Adapter apply count remains unchanged while the same semantic
state is successfully published on retry.

No production change was required.

## F2 — AvailabilityProbeManager quiesce publication could skip cleanup

**Disposition:** accepted and fixed.

Previously `shutdown()` called generation invalidation / plan publication before Adapter
cleanup. If the process-local execution-plan publisher raised while publishing `None`,
probe-owned NetworkRules cleanup was skipped.

Shutdown now attempts cleanup in `finally`.

The publisher exception remains visible. Cleanup is not converted into a successful
shutdown claim.

## F3 — failed ProbeManager plan publication must remain retryable

**Disposition:** existing behavior verified; regression added.

The Manager records a plan as published only after the publisher returns successfully.
Therefore a failed publication can be retried by an equivalent later request/audit without
creating a new physical generation merely for delivery retry.

## F4 — failed quiesce could not be retried after generation clear

**Disposition:** accepted and fixed.

The first shutdown hardening guaranteed probe-rule cleanup after quiesce publication
failure, but generation invalidation cleared `_active_generation` before the failed
publisher call. A later `shutdown()` therefore saw no generation to invalidate and did
not retry `None`.

Generation invalidation now also checks whether the last successfully published execution
plan is still non-None. That unresolved published-plan state is sufficient to retry
quiesce.

A public regression proves:

1. active plan publication succeeds;
2. first shutdown fails while publishing `None`, but cleanup runs;
3. second shutdown publishes `None` successfully and cleans again.

## F5 — two unexpected owner exceptions lost the first diagnostic

**Disposition:** accepted and fixed.

The outer LinuxNetworkPolicyRuntime already attempted both independent owner operations,
but `finally` meant a second unexpected exception replaced the first.

For the rare case where **both** owner calls throw unexpected implementation exceptions:

- `audit()` raises an `ExceptionGroup` containing both errors;
- `stop()` raises an `ExceptionGroup` containing both cleanup errors.

If only one owner throws, that original exception is raised directly.

Expected `ActionResult(False, diagnostic)` remains an ordinary result and is not wrapped
as an exception.

## F6 — no generic reliable-delivery framework

**Disposition:** rejected as unnecessary complexity.

These process-local boundaries do not justify queues/revisions/replay infrastructure.

Current policy remains:

- Manager publisher failure is a visible synchronous call failure and may be retried by a
  later Manager operation;
- Agent fanout publisher failure is isolated/logged so one long-lived worker/scheduler or
  sibling logical consumer is not destroyed;
- unexpected internal implementation exceptions remain visible.

## Evidence

Final code head for this review unit:

`6fa0dc0b09859bf3cde72915ecd20f92c88d67b0`

GitHub Actions `NG2 Python` run **735**:

- compile: PASS;
- **310 rootless unit tests PASS**;
- selective probe-process isolation: PASS;
- EXP-025: PASS;
- EXP-026: PASS;
- EXP-027: PASS;
- nft ICMP selector: PASS;
- Linux instance lifecycle: PASS;
- Linux Adapter: PASS;
- Linux LOCAL_PROCESS: PASS;
- Linux dataplane: PASS.

No external experiment is required.

## Remaining direction

Continue review of lifecycle/assembly invariants and stale artifacts. Do not add an
asynchronous reliability layer without an explicit product contract requiring one.
