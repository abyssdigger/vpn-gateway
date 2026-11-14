# NG2 AvailabilityProbeManager — 40-minute cycle start

Date: 2026-11-14

Baseline commit before this cycle:

6e64f0e2e6658f570928f7322cce9c2952b9e592

Cycle interval: 40 minutes.

Primary goal:

- review the current AvailabilityProbeManager contract against the now-normative Runner / Driver / Executor / Manager model;
- implement only policy-free Manager mechanics that are already architecturally determined;
- preserve the rules-before-evidence invariant;
- do not choose interval, retry count, hysteresis, jitter, concurrency or cancellation policy;
- do not implement production conntrack remediation before EXP-026 Debian 13 target confirmation.