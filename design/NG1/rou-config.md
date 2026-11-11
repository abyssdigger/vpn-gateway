# VPN-GATE NG1 — human-facing ROU configuration

Status: **initial agreed contract; only decisions explicitly closed in the configuration brainstorm are normative here.**

This document defines the human-facing configuration surface that is already agreed.
Fields not described here, including the final syntax for Device publications,
Device traffic envelopes and future DeviceManager features, remain open.

## 1. File format

ROU configuration uses **TOML**.

Devices and Profiles are named tables, not arrays of tables:

```toml
[device.oc-main]
enabled = true

[profile.corp]
enabled = true
```

The table key is the stable object identifier. There is no separate human-facing
`name` field.

Object identifiers use:

```text
[a-z0-9][a-z0-9-]*
```

The same identifier rules apply to Device and Profile IDs.

This deliberately excludes dots, underscores, whitespace and uppercase characters so
identifiers remain unquoted and unambiguous in TOML dotted tables.

A leading digit is intentionally allowed. IDs are opaque strings; consumers must not
reinterpret them as numbers, shell identifiers or raw/unescaped systemd unit fragments.

## 2. enabled and placeholders

`enabled` is mandatory for every declared Device and Profile. There is no default.

A disabled object is allowed to be only a named placeholder:

```toml
[device.wg-future]
enabled = false

[profile.future]
enabled = false
```

For `enabled = false`, remaining object fields are optional and are not deeply
semantically validated. The parser still has to parse valid TOML and identify the object
ID plus `enabled = false`.

An enabled Profile may reference a known disabled Device. That is valid administrative
state, not a warning or error. A reference to an unknown Device ID is a configuration
error.

## 3. Device configuration

An enabled Device requires a non-empty ordered `expected_interfaces` list.

Example:

```toml
[device.oc-main]
enabled = true
expected_interfaces = [
    "oc-main",
    "vpns*/3",
    "oc-backup",
]
```

The name `expected_interfaces` is intentional: the configuration states what ROU expects
to discover, not what it guarantees will exist.

### 3.1 Expected-interface syntax

Exactly two forms are currently defined:

```text
<ifname>
<prefix>*/<N>
```

Examples:

```text
wg0
vpns*/5
```

Semantics:

- `wg0` -> EXACT match, `interface_quota = 1`;
- `vpns*/5` -> PREFIX(`vpns`) match, `interface_quota = 5`.

For PREFIX form, `N` is mandatory and must be a positive integer. There is no implicit
PREFIX quota.

Forms such as these are invalid:

```text
vpns*
wg0/1
vpns*/0
vpns*/
```

The `*` is configuration syntax for a trailing prefix wildcard only. The bootstrap
parser converts it immediately into the typed internal `InterfaceMatch`; wildcard
strings do not propagate into runtime logic.

### 3.2 Order and quota

`expected_interfaces` order is semantically significant.

All runtime interfaces admitted through an earlier entry outrank interfaces admitted
through a later entry of the same Device.

Each entry owns its own `interface_quota`. The Device aggregate is derived, not separately
configured:

```text
Device.interface_quota =
    sum(ExpectedInterface.interface_quota)
```

Selectors must be pairwise disjoint within one Device and across Devices that are active
for the current configuration.

## 4. Profile configuration

An enabled Profile requires all of:

- `direction`;
- non-empty `destinations`;
- non-empty `device_order`.

Minimal enabled example:

```toml
[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc-main"]
```

### 4.1 direction

`direction` is mandatory for enabled Profiles and has no default.

It controls **which side may initiate a flow** for the Profile's remote prefixes. It is
ROU-generated stateful transit policy, not the administrator-authored Device firewall.

Allowed values are exactly:

```text
outbound
inbound
bidirectional
```

No abbreviations are defined.

Operational meaning:

- `outbound`: host side may initiate NEW flows toward the Profile remote prefixes;
- `inbound`: remote side may initiate NEW flows through a bound Device toward the host;
- `bidirectional`: either side may initiate NEW flows;
- admitted ESTABLISHED/RELATED return traffic is allowed in both directions.

The independent Device `traffic_envelope` may restrict any of these flows further.

### 4.2 destinations

`destinations` is a non-empty list of strict **remote/VPN-side** IPv4 CIDR prefixes.

The field name reflects the host -> VPN routing view. For Device -> host NEW-flow
classification the same prefixes are matched as remote source prefixes.

Rules:

- `/0` and `/32` are valid;
- host bits are rejected rather than silently canonicalized;
- duplicate destinations among enabled Profiles are rejected, including duplicates inside
  one Profile;
- overlap at different prefix lengths is allowed;
- list order has no routing semantics.

### 4.3 device_order

`device_order` is a non-empty ordered list of Device IDs.

Rules:

- order is semantically significant;
- duplicate Device IDs inside one Profile are rejected;
- unknown Device IDs are rejected;
- known `enabled = false` Devices are valid references and are skipped operationally;
- disabled Device references consume no current metric range; enabling one later is a new configuration transition.

Device priority from this list is followed by the order of that Device's
`expected_interfaces`.

## 5. Current example

```toml
[device.oc-main]
enabled = true
expected_interfaces = [
    "vpns*/2",
]

[device.wg-backup]
enabled = false

[profile.corp]
enabled = true
direction = "outbound"
destinations = [
    "10.0.0.0/8",
    "192.168.100.0/24",
]
device_order = [
    "oc-main",
    "wg-backup",
]

[profile.future]
enabled = false
```

This example intentionally demonstrates that an enabled Profile may reference an
incomplete disabled Device placeholder.

## 6. Device traffic-envelope capability boundary

The human-facing grammar is **not yet fixed**, but the architecture now fixes what the
future Device envelope must be able to express.

It is Device-scoped, not Profile-scoped, and applies to every bound interface/Profile
sharing that Device.

Required capability surface:

- direction relative to the Device: from-device / to-device;
- source IPv4 prefix;
- destination IPv4 prefix;
- protocol at least TCP / UDP / ICMP;
- TCP/UDP source and destination ports where applicable;
- allow/drop action;
- explicit/default terminal policy.

Canonical admin use cases include temporary source-network restriction on one Device and
temporary destination-port blocking (for example TCP/8007) on another.

This is a capability contract only. The parser must continue to reject guessed
`traffic_envelope` syntax until the TOML grammar is separately agreed.

## 6. Deliberately unresolved configuration surface

The following are not yet fixed by this contract:

- configuration schema/version field;
- human-facing Device publication syntax;
- Device traffic-envelope syntax;
- future DeviceManager lifecycle/configuration fields;
- future Profile warm-reservation syntax;
- reload/CandidateConfig administrative syntax.

They must not be invented implicitly by the first parser implementation.
