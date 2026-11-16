# Production implementation review 29 — EXP-019 WireGuard availability evidence

Date: 2026-11-12

Role: internal expert review under CONTINUOUS-DEVELOPMENT.md.

## Scope

Reviewed:

- EXP-019 topology, harness and all four attempts;
- successful WireGuard outage/recovery evidence;
- architecture §7.3 availability boundary;
- relationship to future DeviceManager and normalized DeviceEngine availability;
- whether the experiment belongs in permanent core CI.

## Attempt integrity

Attempts 1–3 are retained as procedure/environment evidence:

1. temporary directory was accidentally deleted by pre-run cleanup;
2. wg userspace could not open a private-key path below /tmp on the hosted runner;
3. the same wg-specific fopen restriction persisted below /run although generic namespace
   readability succeeded.

None of these attempts exercised the target WireGuard liveness hypothesis.

Attempt 4 changed only key delivery to stdin and then exercised the intended topology.

## Successful evidence

Attempt 4 proved:

- the WireGuard tunnel established normally;
- breaking the peer underlay left local wg0 present with the same ifindex;
- an active probe through wg0 failed during the outage;
- restoring underlay restored the probe on the same interface generation;
- latest-successful-handshake timestamp remained unchanged before, during and after the
  short outage/recovery.

## Finding F1 — interface presence cannot justify AVAILABLE

Severity: architectural evidence.

A present/up WireGuard interface may have an unusable remote path.

### Disposition

Accepted as raw Device-specific evidence. No change to DeviceEngine binding semantics:
presence establishes binding eligibility, not remote availability.

## Finding F2 — latest-handshake age is not a sufficient prompt UNAVAILABLE trigger

Severity: high for future detector design.

The tested data path recovered without a new successful handshake, so a detector based
only on handshake age would continue to report stale evidence across both outage and
recovery.

### Disposition

Accepted.

Future WireGuard availability must not classify solely from interface presence or latest
handshake age.

Handshake data may still be useful contextual evidence, but not the only prompt liveness
signal.

## Finding F3 — active path probe is viable raw evidence but its product semantics are unresolved

Severity: human-design boundary, not a current code defect.

A probe bound to the WireGuard path successfully distinguished live/unavailable/live
without changing interface generation.

However production use requires explicit decisions about:

- probe target ownership and configuration;
- ICMP versus another probe protocol;
- cadence;
- failure and recovery thresholds/hysteresis;
- behavior when the target itself is unavailable while the tunnel remains valid;
- whether availability is per interface, per Device, or combines multiple evidence sources.

These choices affect user-visible DeviceManager configuration and product semantics.

### Disposition

Accepted and intentionally stopped at the human-agreement boundary.

No DeviceManager schema or detector code is invented by this review unit.

## Finding F4 — future-only experiment should not permanently gate the completed core CI

Severity: low process/maintenance.

WireGuard tooling/module availability is not a dependency of the current production ROU
baseline. Keeping EXP-019 in every core validation run would add an unrelated future
dependency.

### Disposition

Accepted.

The successful experiment and harness are preserved under design/experiments, while the
temporary wireguard-tools install and EXP-019 step are removed from the normal NG1
workflow. When DeviceManager begins relying on WireGuard active probes, the relevant
behavior should become a permanent DeviceManager integration test.

## Rust-alignment assessment

The experiment reinforces the existing ownership boundary:

- raw transport/probe evidence remains Device-specific;
- DeviceEngine/TrafficEngine consume only normalized Availability;
- future detector implementations can be trait/provider objects returning typed evidence
  without leaking WireGuard command output downstream.

## Verdict

**APPROVED / RAW-EVIDENCE QUESTION CLOSED.**

No code-level recommendation remains in EXP-019 scope.

The next step is a human-approved DeviceManager availability policy/design decision before
any user-facing schema or positive UNAVAILABLE detector is implemented.
