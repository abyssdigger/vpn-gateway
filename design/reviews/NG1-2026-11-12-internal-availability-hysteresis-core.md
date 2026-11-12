# Internal review — future availability hysteresis core

Date: 2026-11-12

Role: internal expert review under `CONTINUOUS-DEVELOPMENT.md`.

## Scope

Reviewed the new protocol-neutral availability state core against:

- EXP-019 WireGuard raw availability evidence;
- EXP-020 OpenConnect raw availability evidence;
- DeviceEngine concrete `(ifname,ifindex)` identity semantics;
- current Planner availability-provider boundary;
- future Rust migration constraints.

The review intentionally excludes probe target, probe cadence, timeout values and
user-facing DeviceManager configuration because those product-policy decisions are not yet
selected.

## Finding F1 — unbounded streak counters add state without meaning

Severity: low/medium, state-model/Rust-alignment.

The first implementation incremented success/failure streaks indefinitely after the
relevant threshold had already been reached.

That creates unnecessary unbounded state and complicates an eventual fixed-width Rust
representation without changing availability semantics.

### Disposition

Accepted and fixed.

Success/failure streaks saturate at their configured threshold.

## Finding F2 — INDETERMINATE cannot be used as detector-health supervision

Severity: high if violated by a future integration.

The pure state machine correctly treats INDETERMINATE as "no decisive path evidence in
this sample" and freezes the previous hysteresis state.

However, if a future DeviceManager silently maps a stalled/crashed probe engine to repeated
INDETERMINATE samples, stale AVAILABLE or UNAVAILABLE state could persist indefinitely.

This is not solvable inside protocol-neutral hysteresis because it requires detector
freshness/lifecycle information.

### Disposition

Accepted and gated.

The API documentation now states explicitly:

- INDETERMINATE is a sample outcome, not detector-failure state;
- detector freshness/supervision is a separate DeviceManager responsibility;
- production runtime integration is forbidden until that supervision contract is defined.

No speculative timeout/default is added.

## Finding F3 — interface-generation state must never transfer by name

Severity: high, already correctly implemented.

The tracker is keyed by concrete `InterfaceIdentity(ifname,ifindex)`. Disappearance removes
state; same-name/new-ifindex begins at UNKNOWN.

No change required. Regression coverage exists.

## Finding F4 — thresholds must remain explicit until product policy exists

Severity: medium product-policy boundary.

The raw experiments establish that active path evidence is useful, but do not establish
universal failure/recovery thresholds.

### Disposition

Correct as implemented.

`AvailabilityPolicy` has no defaults and requires explicit positive failure/recovery
thresholds. The new core is not wired to TOML or production runtime.

## Test coverage

Rootless tests cover:

- positive threshold validation;
- UNKNOWN -> UNAVAILABLE hysteresis;
- UNAVAILABLE -> AVAILABLE recovery hysteresis;
- AVAILABLE failure hysteresis;
- bounded/saturating counters;
- INDETERMINATE freeze;
- missing-sample behavior;
- disappearing generation cleanup;
- same-name/new-ifindex reset;
- rejection of evidence for an unobserved generation;
- duplicate observed identity rejection.

## Rust-alignment assessment

The state model maps directly to enums/immutable structs:

- `ProbeOutcome`;
- `AvailabilityPolicy`;
- per-generation tracker state;
- pure reconcile transition.

No clock, subprocess, protocol parser or global singleton is embedded in the pure state
machine.

## Verdict

The normalized availability hysteresis core is approved.

One explicit gate remains before production integration:

> DeviceManager detector supervision/freshness semantics must be defined and reviewed.

The next review unit may design that supervision boundary without selecting user-facing
probe target/cadence defaults.
