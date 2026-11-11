# NG1 — стартовый brief брейнсторма human-facing config

Date: **2026-11-11**

Scope: only decisions that were explicitly accepted during the initial configuration
brainstorm after the NG1 internal production model was frozen.

This is a decision record, not a replacement for
`design/NG1/rou-config.md` or the normative architecture.

## 1. Named TOML tables instead of arrays of objects

Initial sketch:

```toml
[[device]]
name = "wg-future"
enabled = false
```

Final decision:

```toml
[device.wg-future]
enabled = false
```

and symmetrically:

```toml
[profile.corp]
...
```

Why:

- Device/Profile names are stable IDs, not descriptive labels;
- mapping by ID matches how Profiles reference Devices;
- object order is not the identity mechanism;
- duplicate table IDs are naturally rejected by TOML;
- placeholders become shorter;
- no separate human-facing `name` field is necessary.

The array-of-tables and named-table forms are not both supported. `device` and
`profile` have one canonical representation.

## 2. Deliberately boring IDs

The brainstorm considered the TOML consequence of IDs containing dots and quoted table
keys. The accepted rule is:

```text
[a-z0-9][a-z0-9-]*
```

Only lowercase ASCII letters, digits and hyphen are used. This keeps IDs unquoted and
predictable in TOML, CLI, logs and diagnostics.

## 3. enabled is explicit, but disabled objects may be minimal

The initial instinct was to make important state fields visibly mandatory. That remains
true for `enabled`: every Device/Profile declaration must contain it and there is no
default.

The refinement made during the brainstorm was to preserve a standard escape hatch for
future/incomplete objects.

Accepted minimal placeholders:

```toml
[device.wg-future]
enabled = false

[profile.future]
enabled = false
```

A disabled object's remaining fields are not required and are not deeply validated.

Reason: an administrator can reserve future structure without being forced to design it
prematurely.

A known disabled Device may therefore remain in an enabled Profile's `device_order`.
That is normal state. Only an unknown ID is an error.

## 4. Profile fields stay explicit

For enabled Profiles the brainstorm retained visible mandatory policy:

```toml
[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc-main"]
```

Accepted rules:

- `direction` is mandatory and has only `outbound`, `inbound`,
  `bidirectional`;
- `destinations` is mandatory and non-empty;
- `device_order` is mandatory and non-empty;
- `device_order` order is policy;
- duplicate or unknown Device IDs are errors;
- known disabled Devices are valid entries.

The explicit `direction` field was retained because this is policy an administrator
should see when reading the file.

## 5. Interface selector syntax evolved from one field to ordered expectations

The starting point was one Device selector such as:

```toml
interface = "vpns+"
```

Then quota was considered as a separate field. To keep selector and quota visually
together, the brainstorm moved toward a compact pattern.

The first compact form considered was:

```text
vpn+/5
```

It was changed to:

```text
vpn*/5
```

because `*` is immediately recognizable to an administrator as a wildcard/prefix
expectation.

The larger change came next: a Device should not be artificially limited to one expected
interface family.

Final external model:

```toml
expected_interfaces = [
    "vpns-main",
    "vpns*/3",
    "vpns-backup",
]
```

The name `expected_interfaces` was chosen instead of `interfaces` to state that ROU
expects/discovers these interfaces but does not guarantee their presence.

## 6. Quota was not removed; it moved to ExpectedInterface

An intermediate idea was to derive one aggregate Device quota and drop
`interface_quota` as a first-class concept.

That was rejected because expected-interface order itself carries route priority and each
selector therefore needs a reserved metric width.

Final internal interpretation:

```text
Device:
    expected_interfaces: list[ExpectedInterface]

ExpectedInterface:
    match: EXACT | PREFIX
    interface_quota
```

Human-facing mapping:

```text
"wg0"       -> EXACT("wg0"), interface_quota=1
"vpns*/5"   -> PREFIX("vpns"), interface_quota=5
```

PREFIX quota is mandatory and positive. EXACT quota is intrinsically 1.

The aggregate:

```text
Device.interface_quota =
    sum(ExpectedInterface.interface_quota)
```

is derived for metric-space allocation; it is not a separate user-configured value.

## 7. Final priority hierarchy

The brainstorm ended with a clear two-level static preference model:

```text
Profile.device_order[]
    -> Device.expected_interfaces[]
        -> stable runtime slot inside one ExpectedInterface quota range
```

This preserves administrator intent without reordering already bound survivors when new
runtime interfaces appear.

## 8. Deferred intentionally

The brainstorm did **not** close:

- schema/version field;
- Device publication syntax in the new TOML surface;
- Device traffic-envelope syntax;
- DeviceManager configuration;
- warm-reservation configuration;
- reload/CandidateConfig controls.

Those remain separate design work and are not silently part of the first parser contract.
