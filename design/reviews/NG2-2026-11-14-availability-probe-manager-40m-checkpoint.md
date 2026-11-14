# NG2 AvailabilityProbeManager — 40-minute cycle checkpoint (draft)

Date: 2026-11-14
Branch: code-cycle-20261114-availability-probe-manager-40m
Cycle interval: 40 minutes

CYCLE_START_COMMIT = 32a8850fc76ecd38dddf65e8c78ba02f68b168a9
T0 = 2026-11-14T13:35:16Z

## Implemented

- generic Linux-independent ProbeDriver / ProbeAttemptResult contract;
- AvailabilityProbeStateInfo + ProbeObservationGeneration value types;
- order-insensitive AvailabilityProbeSetRequest semantic equality;
- executable AvailabilityProbeManager rules-control slice;
- deterministic audit/repair through the shared NetworkRulesAdapter;
- owner-wide Manager-local rules-readiness epoch;
- fail-closed UNKNOWN invalidation when a probe_id leaves the desired full snapshot;
- no physical structural rebuild when logical probe-set changes but compiled NetworkRulesSpec is semantically unchanged;
- deterministic attempt_once(probe_id, timeout_seconds=...) through generic ProbeDriver;
- mandatory fresh pre-attempt and post-attempt ProbeRulesState validation;
- raw ProbeAttemptObservation returned only when the same READY epoch survives the attempt;
- local ProbeAttemptOutcome.ERROR remains raw local failure and is not mapped to UNREACHABLE.

## Deliberately not implemented

- no REACHABLE/UNREACHABLE verdict mapping;
- no attempt interval;
- no timeout source/value policy (attempt_once receives an explicit timeout);
- no retries / thresholds / hysteresis;
- no jitter;
- no parallelism / cancellation / supersession semantics;
- no production conntrack remediation before EXP-026 Debian 13 target PASS.

Therefore current AvailabilityProbeStateInfo publication remains UNKNOWN only.

## Generation decision

ProbeObservationGeneration is a Manager-local owner-wide rules-readiness epoch.
It is not an Adapter transaction ID, interface ifindex, uid, conntrack mark or kernel generation.
Leaving READY invalidates the epoch; a later fresh READY state starts a new sequence.

## Lifecycle decisions

- equivalent reordered full snapshots are idempotent and preserve the current epoch;
- semantic request change ends the epoch;
- removed probe_id receives one final UNKNOWN/no-generation invalidation before local state removal;
- a logical-only change sharing the same physical probe plane does not force structural apply.

## Boundary cleanup

- ProbeAttemptOutcome/ProbeAttemptResult moved out of linux_probe_driver.py into generic probe_attempt.py;
- Linux probe integration now imports attempt semantics from the generic module;
- Linux Driver no longer re-exports generic attempt names accidentally;
- dead _latest_rules_state cache and residual dynamic assignments were removed.

## Review debt

AvailabilityProbeManager.observation_generation remains temporarily exposed as diagnostic/test-only surface.
Preferred final shape is to observe generation through ProbeAttemptObservation / AvailabilityProbeStateInfo unless a real diagnostics consumer justifies the getter.

## Validation

Latest executable head:

    50af2bf94f6c9c03d42f33ea801330b4f5f69fcf

GitHub Actions on that head:

- NG2 Python unit: PASS;
- privileged NG2 Linux integration: PASS;
- NG1 Python validation: PASS.

Subsequent commits through the draft checkpoint are documentation/review only.

## Lower-domain external gate

EXP-026 selective probe-class conntrack cleanup remains privileged-CI PASS but Debian 13 target confirmation is pending.
No production conntrack cleanup was implemented.

## Next semantic decisions

The next implementation unit is availability verdict policy. Explicit agreement is still required for:

- whether one REPLY is immediately REACHABLE or requires a success threshold;
- how many NO_REPLY observations establish UNREACHABLE;
- retention/hysteresis of the previous verdict;
- how local ERROR affects an existing verdict;
- attempt interval;
- timeout source/value;
- retry spacing;
- concurrency/cancellation behavior.