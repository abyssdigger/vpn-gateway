# Internal review — DeviceManager availability activation proposal

Date: 2026-11-12

Role: internal architecture review under `CONTINUOUS-DEVELOPMENT.md`.

## Scope

Reviewed the non-normative future availability proposal against:

- current three-state Availability semantics;
- persistent shadow fallback;
- ordinary binding lifecycle/no-global-barrier policy;
- EXP-019/020 evidence;
- controller freshness/error model;
- startup/restart/new-binding behavior.

## Finding F1 — global fatal containment on detector staleness has excessive blast radius

Severity: architecture/product-policy.

The initial proposal recommended treating any DetectorSupervisionError as fatal to the
whole ROU runtime.

That is fail-closed but unnecessarily global: one broken probe worker for one Device could
interrupt unrelated Profiles/Devices whose routing state remains fully verified.

This conflicts with the project's existing preference for local incremental containment
when a failure can be scoped safely.

### Recommendation

Do not make global ROU shutdown the first availability policy.

Introduce a separate **detector/readiness axis** and quarantine only the affected concrete
binding generation when its monitored evidence is not ready/trustworthy.

## Finding F2 — detector-enabled new bindings need a state before first fresh sample

Severity: high integration correctness.

Current Availability values mean:

- UNKNOWN: no positive unavailable evidence, normal routing tier;
- AVAILABLE: normal routing tier;
- UNAVAILABLE: fallback tier.

If a newly bound monitored interface has no sample yet, mapping it to UNKNOWN would admit
the path before the detector has produced any evidence. Treating missing evidence as fatal
would instead create global outage/restart behavior on every new binding.

### Recommendation

Keep Availability unchanged and add an orthogonal readiness state.

Conceptually:

- UNMONITORED: no detector configured; existing UNKNOWN semantics apply;
- PENDING: detector configured but current generation has not produced trustworthy fresh
  evidence yet;
- READY: supervised evidence is current; Availability is meaningful;
- FAILED: detector freshness/lifecycle is unhealthy.

For TrafficEngine eligibility:

- UNMONITORED: eligible;
- READY: eligible according to Availability tier;
- PENDING/FAILED: locally quarantined, no payload route/ACCEPT/fallback membership.

PENDING/FAILED remain DeviceEngine-visible so probe/recovery can continue.

## Finding F3 — local quarantine cleanly separates detector failure from path failure

Severity: architecture semantics.

Mapping detector failure to UNAVAILABLE would incorrectly claim positive path evidence and
would retain the path in the last-resort fallback.

Local quarantine instead means:

> ROU cannot currently trust its availability evidence for this monitored binding, so it
> will not use that binding for payload until evidence becomes trustworthy again.

This preserves the meaning of UNAVAILABLE and avoids sending fallback traffic over a
control-plane-unknown path.

### Recommendation

Prefer local quarantine as the first monitored-Device detector-health policy.

A separately unrecoverable DeviceManager process failure may still be a service-health
event, but ordinary per-binding stale/missing evidence should not require global
ip_forward=0.

## Finding F4 — restart seeding must not bypass readiness

Severity: high restart correctness.

Persisting last verified normalized Availability is useful for reconstructing the previous
kernel generation and hysteresis baseline, but it is not fresh evidence after restart.

### Recommendation

On restart:

- seed last stable Availability for surviving concrete generations;
- reset probe sequence/timestamps/streak counters;
- monitored bindings enter PENDING;
- keep them quarantined until a fresh sample establishes READY;
- then resume hysteresis from the seeded stable Availability with zero streak counters.

## Finding F5 — Planner integration should consume readiness-decorated bound state

Severity: architecture boundary.

The previous technical recommendation remains correct: DeviceEngine must establish binding
identity first.

The future availability layer then decorates only concrete bound generations with
readiness/Availability. TrafficEngine consumes only payload-eligible bindings.

No selector/quota rediscovery belongs in DeviceManager.

## Finding F6 — probe policy remains a human-facing decision

The raw experiments do not determine:

- ICMP-only versus multiple probe protocols;
- one versus multiple targets;
- cadence/timeout;
- failure/recovery thresholds;
- freshness policy.

No normative schema should be added autonomously.

## Verdict

The proposal requires revision before human approval.

Recommended first-production direction for monitored Devices:

1. separate detector readiness from Availability;
2. PENDING/FAILED monitored bindings are locally payload-quarantined;
3. READY bindings use existing UNKNOWN/AVAILABLE/UNAVAILABLE routing tiers;
4. durable state stores last verified stable Availability, not probe freshness;
5. global runtime containment is reserved for failures that cannot be scoped to one
   binding/Device.

No production code is wired by this review.
