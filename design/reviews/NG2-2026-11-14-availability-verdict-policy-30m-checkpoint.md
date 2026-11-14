# NG2 Availability verdict policy — 30-minute cycle checkpoint

Date: 2026-11-14
Branch: code-cycle-20261114-availability-verdict-policy-30m
Base: e01e547e2be35a24c1ab1765bb83458c2afcc0d7
Status: implementation candidate; maintainer semantic agreement required before promotion

## Scope

This cycle intentionally did not add a scheduler, retries, hysteresis, jitter, concurrency,
or a new abstraction layer.

It implemented the smallest policy-bearing layer above the already validated raw
AvailabilityProbeManager attempt boundary.

## Candidate verdict contract

The proposed first baseline is:

    valid REPLY    -> REACHABLE
    valid NO_REPLY -> UNREACHABLE
    valid ERROR    -> UNKNOWN
    invalid/stale attempt -> no remote verdict; current state is UNKNOWN

REACHABLE and UNREACHABLE carry the current ProbeObservationGeneration.

UNKNOWN never carries an authoritative observation generation.

This is deliberately a one-attempt policy. It does not imply that production must remain
one-attempt once retry/hysteresis policy is designed.

## Boundary retained

attempt_once() remains the policy-free raw operation:

    READY pre-check
        -> Driver.execute()
        -> READY post-check
        -> ProbeAttemptObservation | None

evaluate_once() is the thin policy-bearing operation layered above it.

No new VerdictCalculator/Policy object was introduced because the current mapping is three
branches and has no independently useful lifecycle or configuration.

## Important state correction

A READY audit must not transiently downgrade an already authoritative verdict from the same
Manager readiness epoch.

The Manager now preserves a latest REACHABLE/UNREACHABLE publication when:

- rules are still fresh READY;
- an active readiness epoch exists;
- the publication carries exactly that ProbeObservationGeneration.

A request/rules transition that opens a new epoch still invalidates the old verdict and
publishes UNKNOWN until fresh evidence exists.

## Runner / Driver / Executor boundary

No terminology change was needed.

The existing agreed boundary remains consistent with this slice:

- LinuxIcmpProbeDriver performs one semantic ICMP attempt;
- its lower command transport remains Runner machinery;
- AvailabilityProbeManager owns policy/lifecycle;
- no Runner semantics leaked into the verdict model.

## Regression

Executable code head:

    7f108fec33d903eb4b599b84239abe8e78b02df2

GitHub Actions for that code SHA:

- NG2 Python: PASS;
- NG1 Python validation: PASS.

The NG2 workflow includes compile/unit plus privileged Linux integration, including
EXP-024, EXP-025, EXP-026, nft syntax, instance lifecycle, Linux Adapter,
LOCAL_PROCESS and payload dataplane.

Documentation follow-up is on the 30-minute branch after the executable head.

## Review for unnecessary complexity

No new module, Manager, Executor, Driver, Runner, generation type, timer object, retry
counter or policy hierarchy was added.

The only new public Manager operation is evaluate_once().

The existing diagnostic observation_generation getter remains unchanged and should still be
revisited only when a real diagnostics consumer or the final availability API makes its fate
clear.

## Explicit maintainer agreement requested

Before this candidate is treated as the normative availability policy, confirm or change:

1. Is one valid NO_REPLY sufficient for UNREACHABLE in the initial baseline?
2. Is a local Driver ERROR correctly projected to UNKNOWN rather than retaining the previous
   verdict?
3. Should repeated identical authoritative verdicts remain publication-idempotent? The
   implementation currently says yes.

If these three are accepted, the next cycle can design cadence/retry/hysteresis without
reopening the Driver or rules-generation boundary.
