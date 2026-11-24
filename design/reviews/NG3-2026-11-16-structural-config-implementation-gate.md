# VPN-GATE NG3 — Structural configuration implementation gate

**Cycle:** `ng3-design-cycle-20261116-post-closure-implementation-readiness-40m`  
**Review unit:** first executable NG3 slice — structural Device/Profile configuration

## 1. Scope

Implement the smallest rootless executable slice that turns the accepted structural
Device/Profile TOML contract into immutable normalized domain values.

Included:

- stable Device/Profile object IDs;
- mandatory explicit `enabled`;
- disabled placeholders without deep validation of inactive fields;
- ordered `expected_interfaces` exact/prefix selectors and per-selector quota;
- enabled Profile `direction`, strict IPv4 `destinations`, ordered unique `device_order`;
- unknown versus known-disabled Device references;
- active Device derivation;
- selector ambiguity checks;
- duplicate exact destination ownership checks;
- first-release inbound/bidirectional configured-capacity validation;
- pure normalized `DeviceBindingIntent` / `ProfileStructuralIntent` structural projection.

Explicitly excluded from this unit:

- final human-facing NAT spelling;
- traffic-envelope grammar;
- transport-publication grammar;
- availability-check user grammar/timing;
- runtime interface inventory/binding;
- Linux/network mutation;
- events, Managers, retry or lifecycle machinery.

Unsupported/unfinished fields are not guessed from NG1 examples.

## 2. Requirements

Primary:

- `VPNG-R1.R2.R1`;
- `VPNG-R1.R2.R2`;
- `VPNG-R1.R2.R3`;
- `VPNG-R1.R2.R4` and structural descendants;
- `VPNG-R1.R2.R5` and structural/canonical descendants;
- `VPNG-R1.R3.R4` and selector/quota descendants;
- `VPNG-R2.R1.R1`;
- `VPNG-R2.R2.R1`;
- `VPNG-R2.R3.R3`;
- `VPNG-R2.R3.C1`;
- `VPNG-R2.R3.C1.R1`;
- `VPNG-R2.R5.R1`.

Constrained by:

- `VPNG-R1.R2.R4.R6.C1` — unresolved transport-policy grammar must not be guessed.

All listed requirement/constraint nodes are currently `[closed]` and have exact architecture
references.

## 3. Scenario

An administrator supplies a candidate TOML configuration before any dependent network
actuation.

The product must either:

1. produce one deterministic normalized structural model; or
2. reject the candidate with an explicit configuration error.

No kernel state is touched by this review unit.

## 4. Component design

Use the existing `ConfigurationAdapter` boundary.

Implementation form:

```text
TOML text
    -> ConfigurationAdapter structural parser/validator
    -> immutable normalized structural values
```

No new Manager/Agent/Executor is justified.

Pure helper functions and immutable dataclasses/enums are implementation details inside the
Adapter boundary, not new components.

## 5. Normalized structural values

Minimum values required by this unit:

```text
ExpectedInterfaceSelector
    kind = exact | prefix
    value
    quota

DeviceStructuralIntent
    device_id
    enabled
    expected_interfaces[]

ProfileStructuralIntent
    profile_id
    enabled
    direction
    destinations[]
    device_order[]

DeviceBindingIntent
    device_id
    expected_interfaces[]

StructuralConfig
    devices
    profiles
    active_device_ids
    device_binding_intents
```

`DevicePolicyIntent` is intentionally outside this first executable unit because final
user-facing NAT/envelope/publication grammar is not yet accepted.

## 6. Validation rules

### IDs

`[a-z0-9][a-z0-9-]*`, non-empty, opaque.

### enabled

Every declared Device/Profile requires a real TOML boolean.

If false, the object may be a minimal placeholder and other fields are not deeply
semantically validated in this unit.

### Device selector

Canonical forms:

```text
<ifname>             -> exact, quota 1
<prefix>*/<positive> -> prefix, explicit positive quota
```

Reject malformed prefix/quota forms and ambiguous overlapping selectors.

Within one enabled Device, selector ambiguity is invalid.

Across Devices, selector ambiguity is checked only for Devices active under enabled Profile
references.

### Profile destinations

- non-empty for enabled Profile;
- strict IPv4 network form;
- `/0` and `/32` valid;
- host bits rejected rather than normalized;
- exact duplicate prefix ownership across enabled Profiles rejected;
- different-prefix-length overlap allowed.

### Device references

- `device_order` non-empty and unique;
- unknown ID rejected;
- known disabled Device allowed and skipped operationally.

### Active Device

```text
Device.enabled
AND
referenced by at least one enabled Profile
```

Only active Devices produce `DeviceBindingIntent`.

### Release 1 inbound capacity

For enabled `inbound`/`bidirectional` Profile:

```text
max eligible logical-path capacity
    = sum(selector quotas of currently enabled referenced Devices)
```

Reject if capacity > 1.

Runtime endpoint count is not part of this validation.

## 7. Simplification review

Deliberately absent:

- generic schema framework;
- plugin/registry for config fields;
- persistent config state;
- event delivery;
- retry logic;
- history/replay;
- runtime binding;
- Linux-specific identifiers;
- automatic canonicalization of invalid CIDRs;
- guessed old transport-policy grammar.

Removing any of those abstractions does not break this review unit's accepted requirements.

## 8. Evidence plan

Rootless `unittest` is sufficient.

Required cases:

- valid exact/prefix selectors;
- invalid/missing quota;
- ID grammar;
- explicit boolean `enabled`;
- disabled placeholders;
- strict IPv4 and host-bit rejection;
- exact duplicate destinations;
- allowed different-length overlap;
- duplicate/unknown/known-disabled Device references;
- intra-Device selector overlap;
- active cross-Device selector overlap;
- inactive Device does not participate in cross-Device ambiguity;
- active Device derivation;
- inbound/bidirectional capacity 0/1 accepted and >1 rejected;
- outbound capacity >1 accepted;
- deterministic normalized ordering.

Historical NG1 tests may be used as evidence inventory only; test/code semantics are
re-derived from current NG3 requirements.

## 9. Gate verdict

**PASS — implementation may begin for this bounded structural slice.**

No unresolved product-semantic decision is required for this scope.