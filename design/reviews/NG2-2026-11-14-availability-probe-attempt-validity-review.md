# NG2 — AvailabilityProbeManager single-attempt validity boundary

Date: 2026-11-14
Status: PASS boundary; result policy remains open

## Problem

A pre-attempt READY rules observation is necessary but not sufficient to make a completed
probe outcome authoritative.

LinuxIcmpProbeDriver rechecks the exact InterfaceIdentity immediately before executing the
probe, but it does not observe the complete RPDB/nft probe plane.

External drift can therefore occur after the Manager's last READY observation and before
the attempt completes.

## Required attempt envelope

A future deterministic single-attempt path must use this order:

    fresh READY rules epoch exists
        -> capture current ProbeObservationGeneration
        -> ProbeDriver.execute(request, explicit timeout)
        -> fresh NetworkRulesAdapter.renew_state(owner)
        -> ProbeRulesStateCalculator
        -> require READY still holds for the captured Manager epoch
        -> only then expose raw REPLY / NO_REPLY to result policy

If the post-attempt rules observation is UNKNOWN or INVALID:

- end the current readiness epoch;
- do not interpret REPLY as REACHABLE;
- do not interpret NO_REPLY as UNREACHABLE;
- publish/retain UNKNOWN according to current Manager state;
- normal audit/reconcile may repair rules afterwards, but that repair cannot retroactively
  validate the discarded attempt.

## Driver ERROR

`ProbeAttemptOutcome.ERROR` is a local execution failure, not remote availability
evidence. Even under READY rules it must not be converted directly to UNREACHABLE.

The future result/hysteresis policy may decide how local ERROR affects retention of an
older verdict, but that policy is intentionally not chosen here.

## Timeout

The Driver already requires explicit timeout_seconds. A deterministic attempt method may
receive that timeout as an explicit argument from future scheduling policy. Doing so does
not choose a timeout policy inside the Manager.

## Concurrency

This review assumes the current synchronous serialized Manager control path.

It does not define parallel attempts or cancellation. If future scheduling allows a
RequestEvent or rules reconcile to race an in-flight attempt, the Manager must add an
explicit cancellation/supersession contract.

## Result

The post-attempt fresh-rules check is mandatory before any raw attempt outcome becomes
availability-policy input.

No retry count, threshold, interval, hysteresis or concurrency policy is selected.