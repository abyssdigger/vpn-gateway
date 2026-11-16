# NG2 — AvailabilityProbeManager whole-slice audit

Date: 2026-11-14
Status: PASS for policy-free rules + single-attempt mechanics
Scope: current executable AvailabilityProbeManager slice

## Implemented boundary

The current Manager now owns:

- latest accepted full AvailabilityProbeSetRequest;
- order-insensitive semantic idempotence of equivalent snapshots;
- ProbeRulesCalculator projection;
- shared NetworkRulesAdapter owner lifecycle;
- ProbeRulesStateCalculator interpretation;
- deterministic audit/repair;
- owner-wide rules-readiness epoch;
- fail-closed invalidation of removed probe_id publications;
- one explicit single-attempt operation through generic ProbeDriver;
- mandatory fresh rules validation both before and after the Driver attempt.

It still does not own any chosen timing or verdict policy.

## Raw attempt boundary

ProbeAttemptResult is now Linux-independent semantic Driver output:

- REPLY;
- NO_REPLY;
- ERROR.

ProbeAttemptObservation is created only when:

1. a fresh READY epoch exists before execution;
2. the exact current logical probe is still requested;
3. ProbeDriver executes one attempt;
4. a fresh post-attempt NetworkRules observation remains READY;
5. the same Manager readiness epoch remains current.

Otherwise no raw observation is admitted to future availability policy.

ERROR remains a local execution result and is not converted to UNREACHABLE.

## Generation model

ProbeObservationGeneration is a Manager-local owner-wide rules-readiness epoch.

It is not:

- a Linux interface generation number;
- an Adapter physical transaction ID;
- a uid;
- a conntrack mark;
- a routing/nft generation identifier.

The first ProbeRulesState remains owner-wide, so a loss of READY invalidates all evidence
for the current Manager epoch.

## Idempotence / unnecessary mutation review

Equivalent reordered AvailabilityProbeSetRequest snapshots do not create a new epoch.

A logical probe-set change does create a new Manager epoch, but if ProbeRulesCalculator
produces semantically equivalent physical NetworkRulesSpec, the Manager audits the existing
plane instead of forcing a structural apply.

This avoids needless backend rebuilds and future unnecessary probe-class conntrack cleanup.

## Removed probe lifecycle

When a probe_id disappears from the full desired set, the Manager publishes one final:

    UNKNOWN
    observation_generation = None
    reason = "probe no longer requested"

before forgetting that publication locally.

This prevents a latest-value subscriber from retaining stale REACHABLE/UNREACHABLE evidence.

## Unused / unnecessary artifacts

Removed during the audit:

- _latest_rules_state cache;
- residual dynamic assignments to that removed cache.

No second network reconciler, per-plane generation allocator, Linux-specific attempt type,
or scheduler abstraction was introduced.

## Diagnostic readiness getter

AvailabilityProbeManager.observation_generation remains temporarily exposed as a
diagnostic/test-only read surface.

A first attempt to remove it showed that existing tests depended on it directly. Rather than
perform a broad test rewrite at the cycle boundary, the getter was restored without changing
runtime behavior.

Review again when the verdict/publication slice is implemented. Preferred final shape is
to observe generation only through semantic ProbeAttemptObservation /
AvailabilityProbeStateInfo unless a real diagnostics consumer requires the getter.

## Still intentionally absent

No implementation chooses:

- attempt interval;
- timeout value/source policy;
- retry count;
- REPLY success threshold;
- NO_REPLY failure threshold;
- hysteresis / retention of prior verdict;
- ERROR effect on prior verdict;
- jitter;
- concurrency;
- cancellation / supersession of an in-flight attempt.

Therefore the current Manager publishes UNKNOWN only. It does not yet emit
REACHABLE/UNREACHABLE.

## Lower-domain gate

EXP-026 selective probe-class conntrack cleanup is privileged-CI PASS but still requires
Debian 13 target confirmation before production conntrack remediation is implemented.

No production conntrack cleanup was added in this slice.

## Validation

Latest executable head at audit start:

    50af2bf94f6c9c03d42f33ea801330b4f5f69fcf

GitHub Actions:

- NG2 Python unit: PASS;
- privileged NG2 Linux integration: PASS;
- NG1 Python validation: PASS.

## Verdict

PASS for the implemented policy-free slice.

The next semantic unit is availability verdict policy. It must be agreed explicitly rather
than inferred from single-attempt Driver outcomes.
