# VPN-GATE NG3 — Human-facing configuration model

**Status:** recovered user-intent contract; NG3 refinement  
**Cycle:** `ng3-design-cycle-20261116-config-intent-model-40m`  
**Normative requirements:** `design/NG3/requirements.md`

This document restores the accepted Device/Profile user model from the implemented earlier
configuration while re-deriving its NG3 implementation consequences.

It is a product/interface contract, not permission to inherit NG1 runtime components.

# 1. User model

The configuration separates:

```text
Device
    = what external VPN/network resource the product should expect/bind

Profile
    = what network behavior the user wants
```

A Profile refers to Devices by stable user-visible ID.

A Profile does not describe current Linux route metrics, runtime interface indices, nftables
rules or other internal networking objects.

A Device may be reused by multiple Profiles.

**Requirements:**
- `VPNG-R1.R2.R4`
- `VPNG-R1.R2.R4.R1`
- `VPNG-R1.R2.R4.R3`
- `VPNG-R1.R2.R4.R4`

# 2. Current human-facing representation

The recovered implemented surface uses TOML named tables:

```toml
[device.oc-main]
enabled = true
expected_interfaces = [
    "vpns*/2",
]

[device.wg-backup]
enabled = true
expected_interfaces = [
    "wg0",
]

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
```

Named table keys are object IDs. There is no separate user-facing `name` field.

Current ID grammar:

```text
[a-z0-9][a-z0-9-]*
```

IDs are opaque strings.

**Requirement:** `VPNG-R1.R2.R4.R1.C1`.

# 3. enabled and placeholders

Every declared Device/Profile has explicit `enabled`; there is no implicit default.

A disabled object may be only a placeholder:

```toml
[device.wg-future]
enabled = false

[profile.future]
enabled = false
```

Other active-object fields may be absent and are not deeply semantically validated.

A disabled object creates no active routing/binding behavior.

A known disabled Device may remain referenced by an enabled Profile. It is skipped
operationally while disabled.

An unknown Device reference is invalid.

**Requirements:**
- `VPNG-R1.R2.R4.R2`
- `VPNG-R1.R2.R4.R2.R1`
- `VPNG-R1.R2.R4.R5`

# 4. Device

An enabled Device describes expected runtime endpoints.

Required field:

```toml
expected_interfaces = [
    "wg0",
    "vpns*/3",
]
```

Supported selector forms:

```text
<ifname>
<prefix>*/<positive-quota>
```

Semantic normalization:

```text
"wg0"
    -> EXACT("wg0"), quota = 1

"vpns*/3"
    -> PREFIX("vpns"), quota = 3
```

A PREFIX selector without an explicit positive quota is invalid.

The list is ordered and order contributes to path preference.

Selectors must not be ambiguous within one Device or across simultaneously active Devices.

A Device becomes active for discovery/binding only when:

```text
Device.enabled
AND
referenced by >= 1 enabled Profile
```

Unreferenced Devices do not create runtime binding work.

Endpoints beyond selector quota are not silently admitted.

**Requirements:**
- `VPNG-R1.R3.R4`
- `VPNG-R1.R3.R4.R1`
- `VPNG-R1.R3.R4.R2`
- `VPNG-R1.R3.R4.R3`
- `VPNG-R1.R3.R4.R4`

# 5. Profile

An enabled Profile expresses one user network need.

Required semantic fields:

```text
direction
destinations[]
device_order[]
```

## 5.1 direction

Accepted values:

```text
outbound
inbound
bidirectional
```

Meaning:

- `outbound`: ordinary/host side may initiate NEW flows toward Profile destinations;
- `inbound`: remote side through a permitted Profile Device/path may initiate NEW flows
  toward ordinary/host side;
- `bidirectional`: both sides may initiate;
- admitted return traffic may be handled statefully.

Direction is explicit and is not inferred from topology.

**Requirement:** `VPNG-R2.R3.R3`.

## 5.2 destinations

`destinations` is a non-empty set/list of strict remote-side IPv4 CIDR prefixes.

Examples:

```toml
destinations = [
    "10.0.0.0/8",
    "192.168.100.0/24",
]
```

List order has no routing semantics.

The same remote-prefix meaning is used in both flow directions:

```text
ordinary -> VPN:
    classify by remote destination

VPN -> ordinary:
    first restrict candidate Profiles to those allowing the ingress Device/path
    then classify by remote source
```

An exact prefix cannot belong to more than one enabled Profile.

Different-length overlap is allowed only with deterministic most-specific classification.

**Requirements:**
- `VPNG-R2.R1.R1`
- `VPNG-R2.R1.R2`
- `VPNG-R2.R5.R1`

## 5.3 device_order

`device_order` is a non-empty ordered list of unique Device IDs.

```toml
device_order = [
    "oc-main",
    "wg-backup",
]
```

Semantics:

- only referenced Devices are policy-eligible for the Profile;
- unknown IDs are invalid;
- known disabled Devices are valid references and are skipped while disabled;
- list order is user policy.

The baseline preference hierarchy is:

```text
Profile.device_order
    -> Device.expected_interfaces order
        -> stable runtime slot inside selector quota
```

Newly appearing runtime endpoints must not arbitrarily reorder surviving already-bound
endpoints.

**Requirements:**
- `VPNG-R2.R2.R1`
- `VPNG-R3.R1.R1`

# 6. Profile-scoped availability

Availability is a property of one Profile/path use, not of a physical interface globally.

```text
availability subject
    = (Profile, logical VPN path)
```

Therefore:

```text
wg0 link/interface exists
    !=
wg0 is available for every Profile
```

One interface can be usable for one Profile and unusable for another.

The recovered Profile-level availability surface included compact forms such as:

```toml
interface_balancing = "icmp"
```

and:

```toml
interface_balancing = "icmp/172.21.201.19"
```

The important accepted semantics are:

```text
icmp/<explicit-ip>
    -> use that IPv4 exactly

icmp
    -> deterministically derive one path-specific target
       from already accepted Profile/path/Device/interface/binding/peer topology
```

There is no universal global default target.

Before probe runtime receives work, target normalization must have produced a concrete IPv4.

The exact historical field spelling is retained here as recovered interface context. The
semantic contract, not the string parser shorthand, is what downstream components consume.

**Requirements:**
- `VPNG-R1.R2.R4.R4.R1`
- `VPNG-R3.R6.R1`
- `VPNG-R3.R6.R3.R1`
- `VPNG-R3.R6.R3.R1.C1`
- `VPNG-R3.R6.R3.R2`

# 7. Configuration normalization boundary

The human-facing Device/Profile model is normalized before runtime network components consume
it.

Conceptually:

```text
TOML Device/Profile configuration
        |
        v
ConfigurationAdapter
        |
        +--> active Device binding intents
        |
        +--> Profile policy intents
        |
        +--> Profile/path availability-check configs
        v
validated normalized domain contracts
```

The parser/adapter must reject semantic ambiguity before dependent network mutation.

Normalized runtime contracts may use internal identifiers/structures, but they must preserve
the user semantics above.

In particular, runtime consumers must not need to parse TOML strings.

# 8. Required validation behavior

At minimum, accepted configuration must enforce:

- valid unique Device/Profile IDs;
- explicit boolean `enabled`;
- active Device has non-empty valid `expected_interfaces`;
- expected-interface selector ambiguity is rejected;
- active Profile has explicit valid direction;
- active Profile has non-empty strict IPv4 destinations;
- active Profile has non-empty unique Device references;
- unknown Device reference is rejected;
- exact duplicate destination ownership across enabled Profiles is rejected;
- overlapping destinations remain deterministic;
- availability target is normalized to a concrete IPv4 before runtime probe execution;
- any semantic failure is reported before dependent network actuation.

Disabled placeholders are the explicit exception to active-object field completeness.

# 9. What is not inherited from NG1

This recovered config model does not require NG3 to restore:

- DeviceEngine;
- TrafficEngine;
- PlannerEngine;
- NG1 runtime state classes;
- NG1 metric allocator implementation;
- transport publication machinery;
- Device traffic-envelope grammar;
- old process topology.

Those require independent NG3 requirements if needed.

# 10. Implementation consequences

This contract immediately creates implementation obligations for:

- TOML parsing and object-ID validation;
- disabled-placeholder parsing;
- Device/Profile reference validation;
- expected-interface selector parsing and overlap detection;
- active-Device computation;
- runtime endpoint discovery/binding under selector quotas;
- stable path-slot assignment;
- Profile classification by direction and remote prefixes;
- deterministic overlap handling;
- Profile device/path eligibility;
- preference compilation;
- Profile/path availability-subject creation;
- availability target normalization;
- status/diagnostics using stable Device/Profile identities;
- tests for every validation and normalization rule.

These are implementation obligations derived from the user contract, not independent reasons
to introduce new runtime components.
