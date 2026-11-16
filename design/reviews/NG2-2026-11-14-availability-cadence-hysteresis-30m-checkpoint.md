# NG2 Availability cadence / hysteresis — 30-minute cycle checkpoint

Date: 2026-11-14
Branch: code-cycle-20261114-availability-cadence-hysteresis-30m
Base: d766aab344ba72ae3d1b77d4f675894dc48d68c5
Status: implementation candidate; semantic review requested before promotion

## Scope

This cycle extends the already-agreed one-attempt availability verdict boundary with
per-logical-probe cadence and hysteresis.

It does not add:

- a background thread;
- sleeps/timers inside AvailabilityProbeManager;
- user-facing config parsing/defaults;
- jitter;
- parallel attempts;
- in-flight cancellation;
- a second rules reconciler;
- a new Driver/Runner role.

## Normalized per-probe policy

AvailabilityProbeRequest may now carry:

    AvailabilityProbePolicy
        interval_seconds
        retry_interval_seconds
        timeout_seconds
        failure_threshold = 1
        recovery_threshold = 1

policy=None keeps the probe manually driven through evaluate_once() and excludes it from
run_due().

No arbitrary timing defaults were invented. The producer must supply interval/retry/timeout
for autonomously scheduled probes.

Threshold defaults remain 1/1 so the previously agreed one-attempt baseline is preserved.

The implementation intentionally does not require retry_interval_seconds <=
interval_seconds. The two fields express distinct cadences; policy normalization may impose
a stronger user-facing constraint later if desired.

## Cadence boundary

AvailabilityProbeManager owns deterministic due-state but not the clock/event loop.

The outer runtime calls:

    run_due(monotonic_now)

All due probes are executed synchronously and serially in probe_id order.

A new scheduled probe is immediately due.

After a stable valid check the next deadline uses interval_seconds.

While contrary evidence is below its threshold, or after ERROR / invalid attempt, the next
deadline uses retry_interval_seconds.

The supplied monotonic_now is the dispatch timestamp for the pass. Deadlines are anchored
to that timestamp, not to Driver completion time. At most one attempt per probe is executed
in one run_due() call; there is no internal catch-up loop.

The Manager has a single-threaded control-loop contract. Public mutation methods are expected
to be serialized by the outer runtime.

## Hysteresis

Per probe_id only.

REACHABLE:
- matching REPLY confirms state and returns to normal cadence;
- NO_REPLY below failure_threshold retains REACHABLE and uses retry cadence;
- threshold reached transitions to UNREACHABLE.

UNREACHABLE:
- matching NO_REPLY confirms state and returns to normal cadence;
- REPLY below recovery_threshold retains UNREACHABLE and uses retry cadence;
- threshold reached transitions to REACHABLE.

UNKNOWN:
- REPLY must satisfy recovery_threshold before REACHABLE;
- NO_REPLY must satisfy failure_threshold before UNREACHABLE.

Opposite evidence resets the pending streak.

Local Driver ERROR:
- immediately publishes UNKNOWN;
- clears pending streaks;
- uses retry cadence;
- never counts as remote NO_REPLY.

An attempt discarded by the rules/generation validity envelope also uses retry cadence and
does not contribute to either threshold.

## Logical versus physical generations

The first implementation pass exposed an unnecessary coupling and the cycle corrected it.

ProbeObservationGeneration is now kept strictly as an owner-wide physical rules-readiness
epoch.

Therefore:

- physical NetworkRulesSpec change -> invalidate the owner-wide epoch and all evidence;
- loss of READY -> invalidate the owner-wide epoch and all evidence;
- logical-only change with identical physical NetworkRulesSpec -> preserve rules epoch;
- changed surviving probe_id -> invalidate only that probe's publication/streak/due-state;
- removed probe_id -> final UNKNOWN invalidation then forget;
- newly added logical probe sharing an existing plane -> starts UNKNOWN without invalidating
  unchanged probes;
- policy-only change -> no structural NetworkRules apply and no global epoch bump.

This is both narrower and more faithful to the meaning of "rules-readiness epoch".

## Physical-plane boundary

Timing policy is intentionally absent from ProbeRulesCalculator output.

Changing only policy makes AvailabilityProbeSetRequest semantically different but produces
the same NetworkRulesSpec.

A regression test proves this directly.

## Manual versus scheduled path

evaluate_once() remains the explicit one-attempt baseline:

    REPLY -> REACHABLE
    NO_REPLY -> UNREACHABLE
    ERROR -> UNKNOWN

It bypasses scheduled thresholds.

If used for a probe that also has scheduled state, it clears pending hysteresis streaks but
does not move that probe's existing due deadline. Production should normally choose one
control path; this mixed behavior is retained mainly to keep the explicit diagnostic/test
operation well-defined.

## Regression

Latest executable code head:

    43c0d8b34cfe1f479d6a067bae272dc5cffd0eb6

GitHub Actions:

- NG2 unit: PASS — 252 tests;
- NG2 privileged Linux integration: PASS;
- NG1 Python validation: PASS.

The Linux integration still covers EXP-024, EXP-025, EXP-026, nft syntax, instance
lifecycle, NetworkRulesAdapter, LOCAL_PROCESS and payload dataplane.

Documentation-only commits follow the executable head.

## Complexity audit

New production artifacts:

- one small immutable AvailabilityProbePolicy value type;
- one private _ProbeScheduleState owned by AvailabilityProbeManager;
- run_due() plus policy application helpers.

Not introduced:

- Scheduler class;
- Timer abstraction;
- VerdictCalculator hierarchy;
- retry job objects;
- per-physical-plane timing state;
- async framework;
- locks;
- a second availability Manager.

The policy/state module split is justified because policy is a normalized domain value
carried by AvailabilityProbeRequest rather than Linux execution machinery.

## Explicit agreement before next runtime slice

The implementation currently chooses:

1. thresholds apply from UNKNOWN as well as across an existing stable verdict;
2. pending contrary evidence retains the prior authoritative verdict rather than inserting
   UNKNOWN;
3. ERROR is exceptional and immediately changes the probe to UNKNOWN;
4. retry_interval_seconds is a distinct cadence and is not required to be numerically
   shorter than interval_seconds;
5. deadlines are anchored to the run_due() dispatch timestamp, not Driver completion;
6. due probes execute serially in probe_id order;
7. policy=None is allowed as an explicit/manual mode at the normalized request layer.

If these stand, the next natural unit is outer runtime integration: production policy
normalization plus monotonic tick scheduling around AvailabilityProbeManager, without
reopening Driver or NetworkRules semantics.
