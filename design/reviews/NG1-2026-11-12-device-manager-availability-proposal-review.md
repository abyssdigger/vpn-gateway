# Internal review — DeviceManager availability policy proposal

Date: 2026-11-12

Role: internal expert review under CONTINUOUS-DEVELOPMENT.md.

## Scope

Reviewed the proposed first DeviceManager availability slice against:

- NG1 Draft 5 normalized Availability semantics;
- EXP-016 ECMP prerequisite evidence;
- EXP-019 WireGuard retained-generation outage/recovery evidence;
- EXP-020 OpenConnect retained-generation outage/recovery evidence;
- current Device / ExpectedInterface ownership boundaries;
- current default-DROP OUTPUT policy;
- future Rust provider/trait migration.

## Finding F1 — detector failure must not demote availability knowledge to UNKNOWN

Severity: high routing-safety semantics.

The initial proposal said detector execution failure should produce UNKNOWN. In the current
routing architecture UNKNOWN participates in the normal tier. Therefore an already proven
UNAVAILABLE path could be promoted back into normal routing merely because the detector
itself failed.

### Disposition

Accepted and fixed.

Detector health is now orthogonal to normalized path availability:

- a new generation with no valid evidence starts UNKNOWN;
- valid probe evidence drives AVAILABLE/UNAVAILABLE transitions;
- detector malfunction does not create an availability transition;
- after a generation has reached AVAILABLE or UNAVAILABLE, detector failure preserves the
  last normalized state and is reported separately.

This preserves the distinction between path evidence and detector-health evidence.

## Finding F2 — probe target ownership must align with the Device abstraction

Severity: medium schema/ownership consistency.

Putting target configuration on each ExpectedInterface would couple health semantics to
selector/quota syntax and complicate one Device with multiple dynamic bindings.

A Device is already the external networking/VPN resource and availability domain, while
ExpectedInterface is discovery/quota policy.

### Disposition

Recommendation accepted in the proposal:

- schema-v1 availability target is Device-scoped;
- every bound generation of that Device is probed independently against the same target;
- if different binding groups require different targets, they are modeled as separate
  Devices.

This keeps ExpectedInterface free of transport-health configuration and gives one Device
one availability/trust domain.

## Finding F3 — path probe must be concrete-generation specific

Severity: high implementation safety.

A destination-only probe is insufficient because ordinary routing could send it through a
different Device/interface. The provider must prove that each result belongs to the
`(device_name, ifname, ifindex)` generation being classified.

### Disposition

Accepted as an implementation gate.

The design does not guess the concrete Python/Linux mechanism. A dedicated EXP-021 must
prove an interface-generation-bound probe primitive, including same-name/new-ifindex
replacement and no alternate-route escape, before the detector drives production
availability.

## Finding F4 — active probe requires a deliberate OUTPUT exception

Severity: high security-boundary change.

Current ROU OUTPUT policy is default-DROP and intentionally permits NEW local traffic only
through host0. A Device-bound probe therefore cannot be implemented by silently broadening
OUTPUT.

### Disposition

The proposal correctly requires one generated generation-scoped exception limited to:

- concrete bound Device interface generation;
- configured /32 probe target;
- selected probe protocol/message type.

No generic Device-interface OUTPUT ACCEPT is acceptable.

Human approval is required because this intentionally changes the local security boundary.

## Finding F5 — timing/hysteresis values are not established by EXP-019/020

Severity: product-policy boundary.

The experiments establish only that active path evidence can distinguish outage/recovery.
They do not establish production cadence, timeout or thresholds.

### Disposition

No defaults are invented.

The proposal recommends explicit `interval`, `timeout`, `failures` and `successes`
in the first schema unless the maintainer explicitly chooses an opinionated preset/default
policy.

## Rust-alignment assessment

The proposed split is strong:

- immutable AvailabilityKey = Device + interface generation;
- transport/process evidence stays in provider implementations;
- routing core consumes only normalized Availability;
- detector health remains separate diagnostic state;
- process lifecycle and availability remain separate provider traits.

No protocol command output leaks into Planner/TrafficEngine.

## Verdict

**APPROVED AS A DESIGN PROPOSAL; IMPLEMENTATION BLOCKED ON HUMAN POLICY DECISIONS.**

No further autonomous schema or detector implementation should occur until the maintainer
selects:

1. target ownership policy;
2. timing/hysteresis policy;
3. first probe protocol;
4. the narrow generation-scoped OUTPUT exception.

After approval, the next review unit is EXP-021, proving the concrete generation-bound
probe primitive before production detector code is written.
