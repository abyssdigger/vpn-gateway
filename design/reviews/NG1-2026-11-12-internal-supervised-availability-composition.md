# Internal review — supervised availability composition

Date: 2026-11-12

Role: internal expert review under `CONTINUOUS-DEVELOPMENT.md`.

## Scope

Reviewed composition of:

- detector freshness proof;
- protocol-neutral hysteresis;
- concrete `(ifname,ifindex)` generation identity;
- exactly-once evidence consumption.

No production runtime containment behavior or user-facing probe configuration is selected in
this review unit.

## Finding F1 — one physical probe could be counted repeatedly

Severity: high.

The first composition version advanced hysteresis every time Planner/DeviceManager consumed
the current TimedProbeSample. Multiple reconciliation passes could therefore satisfy a
multi-sample failure/recovery threshold using one physical probe.

### Disposition

Accepted and fixed.

Each TimedProbeSample now has a process-local, per-interface monotonic `sample_id`.
Supervised state remembers the last consumed sample for each concrete interface generation.

A larger id consumes one evidence outcome. Reusing an identical sample does not advance
hysteresis.

## Finding F2 — reusing an id with a refreshed timestamp could defeat freshness

Severity: high.

Remembering only the last sample id was insufficient: a broken detector could reissue the
same id with a newer timestamp. Hysteresis would not advance, but stale evidence would
appear fresh indefinitely.

### Disposition

Accepted and fixed.

Supervised state stores the complete last TimedProbeSample. Equal sample ids are accepted
only when the complete sample is identical. Changed outcome or timestamp under the same id
is a detector evidence regression error.

## Finding F3 — new sample identity may not move monotonic time backward

Severity: medium/high detector integrity.

A higher id with an older process-local monotonic timestamp contradicts the detector's
sample stream and makes age reasoning ambiguous.

### Disposition

Accepted and fixed.

Such input raises DetectorEvidenceRegression.

Equal timestamps for distinct ids remain valid because monotonic clock resolution may be
coarser than probe sequencing; sample_id is the exactly-once identity.

## Finding F4 — supervised state must keep tracker/sample generations aligned

Severity: medium normalized-state integrity.

### Disposition

Accepted and fixed.

SupervisedAvailabilityState requires the hysteresis tracker and last-sample map to contain
the same concrete interface-generation keys.

When an interface disappears, both histories disappear. Same-name/new-ifindex begins with
fresh UNKNOWN state and requires a new sample.

## Restart semantics

Sample ids and monotonic timestamps are explicitly ephemeral. They are not durable runtime
history and are reset on DeviceManager restart.

This is safe at this layer because production integration remains gated: a restarted
detector must establish fresh current-generation samples before the future caller can
obtain a supervised availability mapping.

## Test coverage

Regression coverage now proves:

- distinct samples advance hysteresis;
- the same sample is consumed exactly once;
- same-id mutated evidence is rejected;
- sample-id regression is rejected;
- timestamp regression under a new id is rejected;
- stale evidence fails before hysteresis;
- same-name/new-ifindex cannot inherit evidence;
- state generation keys remain consistent.

## Rust-alignment assessment

The model translates cleanly to:

- an enum ProbeOutcome;
- a typed sample with monotonic Instant-equivalent age plus sequence id;
- immutable per-generation state;
- explicit error variants.

A Rust implementation should use a checked/non-wrapping sequence counter for one
DeviceManager process lifetime.

## Verdict

Approved. No remaining recommendation in this review unit.

The next unresolved product boundary is intentionally outside this code:

> how production runtime reacts when DetectorSupervisionError is raised.

No production availability provider may be wired until that containment/demotion policy is
chosen and reviewed.
