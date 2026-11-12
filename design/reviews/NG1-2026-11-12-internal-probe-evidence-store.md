# Internal review — probe evidence store

Date: 2026-11-12

Role: internal expert review under `CONTINUOUS-DEVELOPMENT.md`.

## Scope

Reviewed the process-local probe evidence registry against:

- exactly-once supervised availability semantics;
- concurrent probe-worker publication;
- concrete `(ifname,ifindex)` generation identity;
- process restart/reset requirements;
- Python-to-Rust migration.

## Finding F1 — probe workers must not own sample sequence coordination

Severity: medium architecture/consistency.

If each worker assigned sample ids independently, exactly-once consumption would depend on
protocol-specific code and could collide/reuse ids inconsistently.

### Disposition

Resolved by design.

ProbeEvidenceStore owns one process-local monotonically increasing sample-id sequence.
Workers publish only `(InterfaceIdentity, ProbeOutcome)`.

## Finding F2 — evidence publication must serialize id/time assignment

Severity: medium concurrency correctness.

The sample id and monotonic timestamp must belong to the same serialized publication
operation.

### Disposition

Correct as implemented.

Clock read, sample construction, latest-sample replacement and sequence increment occur
under one lock.

Concurrent regression coverage proves 32 writers receive unique ordered ids and the latest
registry value has the highest assigned id.

## Finding F3 — pruning must not rewind sample identity

Severity: medium exactly-once integrity.

Removing stale interface-generation samples must not permit sample-id reuse later in the
same process.

### Disposition

Correct as implemented.

`retain()` removes latest samples but does not rewind the global sequence.

## Finding F4 — retain() accepted arbitrary hashable identities

Severity: low/medium normalized-boundary correctness.

A programming error could pass strings/other hashables and silently prune valid registry
entries.

### Disposition

Accepted and fixed.

`retain()` now requires InterfaceIdentity values and rejects duplicates.

## Finding F5 — registry and supervised availability state must share lifecycle ownership

Severity: high for future integration, not a defect in this isolated store.

Both sample ids/timestamps and consumed-sample state are explicitly process-local. If the
registry resets while SupervisedAvailabilityState survives (or the reverse), sequence/time
assumptions become invalid.

### Disposition

Accepted as the next implementation gate.

Production integration must introduce one lifecycle owner that creates/resets both the
ProbeEvidenceStore and SupervisedAvailabilityState together. Neither object may be
persisted independently.

## Test coverage

Rootless tests cover:

- monotonically increasing sequence assignment;
- immutable point-in-time snapshots;
- prune without id reuse;
- same-name/new-ifindex separation;
- duplicate/type validation;
- invalid clock values without sequence consumption;
- concurrent writer serialization.

## Rust-alignment assessment

The registry maps naturally to a process-owned structure around:

- Mutex-protected latest-sample map;
- checked monotonic sequence counter;
- monotonic clock supplied at publication time.

A Rust port should use checked integer increment and treat counter exhaustion as fatal
process-state corruption rather than wrap/reuse.

## Verdict

Approved. No remaining recommendation in this review unit.

Next required future unit: a single DeviceManager availability controller owning both
probe evidence and supervised hysteresis state.
