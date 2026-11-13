# VPN-GATE NG1 — router configuration schema version 1

Status: **normative for NG1 Draft 5**

Router policy uses TOML and requires:

```toml
schema_version = 1
```

Unknown or missing versions are rejected.

## 1. Object identifiers

Devices and Profiles are named tables:

```toml
[device.oc-main]
enabled = true

[profile.corp]
enabled = true
```

Identifiers use:

```text
[a-z0-9][a-z0-9-]*
```

A leading digit is allowed. IDs are opaque strings.

## 2. Disabled placeholders

`enabled` is mandatory for every declared Device/Profile.

A disabled declaration may be only:

```toml
[device.wg-future]
enabled = false

[profile.future]
enabled = false
```

Remaining fields on disabled objects are not deeply semantically validated.

An enabled Profile may reference a known disabled Device. Unknown Device references are
configuration errors.

## 3. Enabled Device

Every enabled Device requires:

- non-empty ordered `expected_interfaces`;
- explicit `nat = "none" | "masquerade"`.

Example:

```toml
[device.oc-main]
enabled = true
expected_interfaces = ["vpns*/2"]
nat = "masquerade"
publications = [
    "44443/tcp",
    "44443/udp",
]
```

### 3.1 Expected interfaces

Forms:

```text
<ifname>
<prefix>*/<positive-quota>
```

Examples:

```text
wg0
vpns*/5
```

Exact match has quota 1. Prefix form requires explicit positive quota. Selector order is
priority order. Active selectors must be disjoint across active Devices.

### 3.2 NAT

`nat = "none"` means ROU does no payload source NAT for this Device.

`nat = "masquerade"` creates POSTROUTING MASQUERADE only:

- on currently bound interfaces of the Device;
- for remote prefixes of enabled Profiles referencing that Device.

There is no implicit NAT default and no explicit SNAT in schema version 1.

### 3.3 Publications

Grammar:

```text
<external-port-or-range>/<tcp|udp>[><internal-port-or-range>]
```

Examples:

```toml
publications = [
    "44443/tcp",
    "44443/udp",
    "5678/udp>7890",
    "4700:4900/udp>55200:55400",
]
```

If the internal side is omitted it equals the external side. Bounds are inclusive,
1..65535, and range cardinalities must match.

For active Devices:

- external ranges for the same protocol must not overlap;
- internal target ranges for the same protocol must not overlap across different Devices;
- one Device may expose multiple external aliases to the same internal endpoint;
- TCP and UDP may use the same numeric ports.

Publication bind/target addresses come from the instance configuration, not Device policy.

### 3.4 Traffic envelope

Optional Device-scoped firewall:

```toml
[device.oc-main.traffic_envelope]
default = "allow"

[[device.oc-main.traffic_envelope.rules]]
direction = "from-device"
action = "drop"
source = "10.20.0.0/16"
protocol = "tcp"
destination_ports = ["8007"]

[[device.oc-main.traffic_envelope.rules]]
direction = "to-device"
action = "allow"
destination = "192.168.50.0/24"
protocol = "udp"
destination_ports = ["53", "5353-5355"]
```

Envelope rule fields:

- required: `direction = "from-device" | "to-device"`;
- required: `action = "allow" | "drop"`;
- optional strict IPv4 `source`, `destination`;
- optional `protocol = "any" | "tcp" | "udp" | "icmp"`, default `any`;
- optional `source_ports`, `destination_ports` as `"N"` or `"A-B"`;
- ports are valid only for TCP/UDP;
- duplicate/overlapping ranges in one port list are rejected.

Rules are first-match in file order followed by explicit `default`.

Envelope allow is restrictive composition, not permission bypass: it materializes as
RETURN to the generated Profile-direction guard, never FORWARD ACCEPT. Envelope drop is
DROP. The envelope is traversed before ESTABLISHED/RELATED and generated NEW rules.

## 4. Enabled Profile

Requires:

- `direction`;
- non-empty `destinations`;
- non-empty ordered `device_order`.

Example:

```toml
[profile.corp]
enabled = true
direction = "outbound"
destinations = [
    "10.0.0.0/8",
    "192.168.100.0/24",
]
device_order = ["oc-main", "wg-backup"]
```

### 4.1 Direction

Values:

- `outbound`: host may initiate NEW;
- `inbound`: remote side may initiate NEW;
- `bidirectional`: either side may initiate NEW.

ESTABLISHED/RELATED return traffic is admitted subject to Device envelope.

Production schema-v1 restrictions for `inbound` and `bidirectional`:

- active interface capacity must be exactly 1, where capacity is the sum of
  `interface_quota` for enabled Devices in `device_order`;
- every active referenced Device must have `traffic_envelope` with
  `default = "drop"`.

The capacity-one rule guarantees deterministic return steering without connmark/fwmark.
The restrictive envelope is the mandatory administrator boundary that explicitly permits
host-side destinations/protocols/ports for remote-initiated traffic. Capacity greater than
one is a future EXP-014-gated flow-pinning extension.

### 4.2 Destinations

Strict remote-side IPv4 CIDRs:

- `/0` and `/32` valid;
- host bits rejected;
- exact duplicate prefixes across enabled Profiles rejected;
- overlap at different prefix lengths allowed;
- order has no routing semantics.

### 4.3 Device order

Ordered Device IDs. Unknown IDs rejected. Known disabled Device references valid and
consume no current metric range.

## 5. Complete example

```toml
schema_version = 1

[device.oc-main]
enabled = true
expected_interfaces = ["vpns*/2"]
nat = "masquerade"
publications = ["44443/tcp", "44443/udp"]

[device.oc-main.traffic_envelope]
default = "allow"

[[device.oc-main.traffic_envelope.rules]]
direction = "from-device"
action = "drop"
source = "10.20.0.0/16"

[device.wg-backup]
enabled = false

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc-main", "wg-backup"]
```

## 6. Explicitly outside schema version 1

- DeviceManager process lifecycle/configuration;
- Profile-binding availability/control conditions and ON/OFF runtime state;
- Profile warm reservation;
- live reload/CandidateConfig administrative protocol;
- explicit SNAT;
- IPv6 payload policy.

### Future availability/control configuration

`interface_balancing` is the current provisional Profile-facing name for this future
configuration surface. It is **not schema-version-1 syntax**; schema version 1 still rejects
unknown Profile fields.

Illustrative, non-final forms:

```toml
interface_balancing = "icmp/172.21.201.19"
interface_balancing = "tcp/172.21.201.19:443"
interface_balancing = "tcp/google.com:443"
interface_balancing = "icmp"
```

The option expresses whether a concrete binding actually provides what this Profile needs.
It is not global Device/interface health. Therefore the same concrete interface may pass
the condition for one Profile and fail it for another, including a multi-peer WireGuard
interface whose peer serving one Profile is down while other peers remain healthy.

For an explicit target, the Profile administrator chooses the host/service whose
reachability proves path usefulness. For a target-less form such as `"icmp"`, ROU is
expected eventually to derive a path-specific target from Device/interface/peer/Profile
information already available locally. The derivation algorithm is intentionally deferred;
the Profile administrator should not be required to know transport endpoint internals.

The agreed semantic boundary remains:

- the configured Profile expresses intent, not detector state;
- the pair is `ON` only when all required conditions for that pair are currently satisfied;
- current ON/OFF state is never persisted;
- the same concrete binding may be ON in one Profile and OFF in another;
- metric allocation remains independent of ON/OFF;
- probe/control routes must not be placed in Profile payload tables.

EXP-022 and EXP-023 have proven the isolated probe-plane mechanism. Still open are the exact
grammar/schema-version transition, supported probe types, target-less derivation,
hostname/DNS semantics, timing and hysteresis.
