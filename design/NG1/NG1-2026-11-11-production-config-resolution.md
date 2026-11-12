# NG1 production configuration resolution proposal

Status: **implementation proposal for Draft 5 review**

This document resolves configuration surfaces intentionally left open by Draft 4.

## 1. Router configuration version

Router TOML requires:

```toml
schema_version = 1
```

Unknown/missing versions are rejected. There is no silent legacy mode in production.

## 2. Device NAT policy

Every enabled Device requires an explicit:

```toml
nat = "none"
```

or:

```toml
nat = "masquerade"
```

NAT is Device-scoped because:

- Profile has no host/local source-prefix contract; host admission belongs to BOU;
- a Device represents one tunnel/remote routing domain;
- shared Profiles on the same Device must not disagree about egress source translation.

`none` means ROU performs no payload source NAT for that Device.

`masquerade` means POSTROUTING MASQUERADE on each currently bound interface of the
Device, restricted to the union of remote prefixes of enabled Profiles that currently
reference that Device. Over-quota/unbound interfaces receive no NAT rule.

The first production schema does not expose explicit SNAT. Adding it later requires a
schema-version-compatible extension or new version.

## 3. Device publications

Enabled Device may contain:

```toml
publications = [
    "44443/tcp",
    "44443/udp",
    "5678/udp>7890",
    "4700:4900/udp>55200:55400",
]
```

Grammar:

```text
<external-port-or-range>/<tcp|udp>[><internal-port-or-range>]
```

If `>...` is omitted, internal ports equal external ports.

Range bounds are inclusive, 1..65535, and external/internal cardinality must match.

Publications are Device-scoped and materialized only for active Devices. Within the active
Device set, external ranges for the same transport protocol must not overlap. TCP and UDP
may use the same numeric port.

Across different active Devices, internal target ranges for the same protocol must also
not overlap because schema version 1 targets one common `host0` IPv4 address and Device
ownership of the listener must remain unambiguous. Within one Device, multiple external
aliases may intentionally map to the same internal endpoint.

The instance configuration supplies one explicit host-side IPv4 publication bind address.
Internal relay target address is the instance's `host0` IPv4 address. Publications map
ports/protocol only; they do not duplicate infrastructure addressing in Device config.

## 4. Device traffic envelope

An enabled Device may omit `traffic_envelope`; omission means no additional Device-layer
restriction beyond the generated Profile-direction guard.

If present:

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

Required rule fields:

- `direction = "from-device" | "to-device"`
- `action = "allow" | "drop"`

Optional matches:

- `source = "<strict IPv4 CIDR>"`
- `destination = "<strict IPv4 CIDR>"`
- `protocol = "any" | "tcp" | "udp" | "icmp"` (default `any`)
- `source_ports = ["N", "A-B", ...]`
- `destination_ports = ["N", "A-B", ...]`

Port matches are valid only with TCP/UDP. Bounds are inclusive and 1..65535.
Overlapping/duplicate ranges inside one list are rejected rather than normalized.

Rules are first-match in file order followed by the mandatory envelope `default` verdict.

### 4.1 Cumulative materialization

Envelope `allow` never maps to a FORWARD `ACCEPT`. Each bound interface receives
direction-specific Device chains:

- a matching envelope `drop` maps to `DROP`;
- a matching envelope `allow` maps to `RETURN`;
- terminal envelope default `drop` maps to `DROP`;
- terminal envelope default `allow` maps to `RETURN`.

FORWARD jumps through the relevant Device envelope chain **before**
ESTABLISHED/RELATED and generated Profile NEW verdicts. Thus the envelope can restrict
traffic, including existing flows, but can never widen Profile.direction.

If `traffic_envelope` is omitted, no extra chain is required.

## 5. Instance/bootstrap configuration

Instance TOML is separate from router policy and requires:

```toml
schema_version = 1

[instance]
namespace = "vpn-gate-rou0"
host_interface = "rouvpn0"
host_address = "192.0.2.1/30"
inner_address = "192.0.2.2/30"
publication_bind_address = "0.0.0.0"
router_config = "/etc/vpn-gateway/routers/rou0.toml"
state_file = "/var/lib/vpn-gateway/rou0/state.json"
```

Rules:

- `host0` is the fixed internal peer name in schema version 1 and is not a config field;
- host/inner addresses are strict IPv4 interface addresses in the same subnet; /31 is valid;
- `publication_bind_address` is an explicit IPv4 address; `0.0.0.0` means wildcard;
- `router_config` and `state_file` are absolute paths;
- no automatic address generation is implemented in schema version 1.

The instance identifier remains the CLI/systemd template identifier and is not duplicated
inside the file. It uses the same safe grammar as Device/Profile IDs:

```text
[a-z0-9][a-z0-9-]*
```

This keeps instance paths and systemd template arguments opaque and shell-independent.

## 6. Disabled placeholders

Existing Draft 4 placeholder semantics remain:

- disabled Device/Profile requires only `enabled=false`;
- additional fields are not deeply semantically validated;
- active policy/resource collision validation considers only active Devices.

## 7. Deferred surfaces that remain outside schema version 1

- DeviceManager lifecycle/configuration;
- Profile warm reservation;
- live reload/CandidateConfig administrative protocol;
- explicit SNAT;
- non-IPv4 payload policy.

These do not block the first complete production ROU.
