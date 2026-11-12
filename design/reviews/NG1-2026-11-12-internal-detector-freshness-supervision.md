# Internal review — detector freshness supervision primitive

Date: 2026-11-12

Role: internal expert review under `CONTINUOUS-DEVELOPMENT.md`.

## Scope

Reviewed the future DeviceManager freshness/supervision primitive against:

- EXP-019 and EXP-020 raw path-evidence results;
- the approved protocol-neutral availability hysteresis core;
- DeviceEngine concrete generation identity;
- Python-to-Rust state/value boundaries;
- restart/reboot monotonic-clock semantics.

This review intentionally does not choose production probe cadence, target, timeout,
failure threshold or recovery threshold.

## Finding F1 — non-finite timestamps/policy values could bypass freshness checks

Severity: high for a future integration.

IEEE NaN does not order normally. A NaN max age or timestamp could make stale/future checks
silently evaluate false.

### Disposition

Accepted and fixed.

Freshness policy, sample timestamps and caller-supplied current monotonic time now require
finite numeric values. Booleans are rejected explicitly despite Python's bool/int
relationship.

## Finding F2 — Python annotations alone did not guarantee typed ProbeOutcome

Severity: low/medium normalized-domain integrity.

A directly constructed TimedProbeSample could contain an arbitrary string even though the
field annotation named ProbeOutcome.

### Disposition

Accepted and fixed.

TimedProbeSample validates ProbeOutcome at construction.

## Finding F3 — monotonic timestamps are not durable state

Severity: high restart correctness if violated.

A monotonic-clock value is meaningful only in the process/boot clock domain that produced
it. Persisting and restoring it could make sample age meaningless after restart/reboot.

### Disposition

Accepted and fixed as an explicit lifecycle contract.

Timed samples are ephemeral supervision state and must never be persisted. A restarted
detector must establish fresh samples for current concrete interface generations.

No wall-clock substitution is introduced.

## Finding F4 — stale/missing evidence must remain an explicit supervision failure

Severity: high policy-boundary correctness.

The supervision primitive must not invent Availability from detector failure.

### Disposition

Correct as implemented.

Missing and stale evidence raise distinct supervision errors. The primitive does not map
those errors to UNKNOWN, AVAILABLE or UNAVAILABLE.

The eventual runtime containment/demotion behavior remains a separate DeviceManager policy
decision requiring review/human agreement.

## Test coverage

Rootless tests cover:

- fresh and exact-boundary samples;
- missing/stale evidence;
- future timestamp rejection;
- same-name/new-ifindex sample isolation;
- disappeared-generation sample tolerance;
- duplicate identity rejection;
- nonpositive/nonfinite/boolean time values;
- typed ProbeOutcome enforcement.

## Rust-alignment assessment

The primitive is suitable for direct translation:

- explicit finite duration policy;
- typed sample/outcome;
- immutable fresh-evidence result;
- explicit error variants;
- monotonic time supplied by caller.

No protocol/process/thread ownership is hidden inside the pure verifier.

## Verdict

Approved. No remaining recommendation in this review unit.

Production runtime integration remains gated on a separate policy decision:

> what should DeviceManager/runtime do when current bound-generation detector evidence is
> missing or stale?

That question must not be answered implicitly by this primitive.
