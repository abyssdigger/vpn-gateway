# VPN-GATE NG3 — Human-facing configuration model

**Status:** recovered user-intent contract; NG3 refinement  
**Cycle:** `ng3-design-cycle-20261116-config-intent-model-40m`  
**Normative requirements:** `design/NG3/requirements.md`

This document restores the accepted Device/Profile user model from the implemented earlier
configuration while re-deriving its NG3 implementation consequences.

It is a product/interface contract, not permission to inherit NG1 runtime components.

Historical kernel/process facts used while recovering this model are summarized in
`design/NG3/experiment-evidence-transition.md`.

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
- `VPNG0001-R1.R2.R4`
- `VPNG0001-R1.R2.R4.R1`
- `VPNG0001-R1.R2.R4.R3`
- `VPNG0001-R1.R2.R4.R4`

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

**Requirement:** `VPNG0001-R1.R2.R4.R1.C1`.

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
- `VPNG0001-R1.R2.R4.R2`
- `VPNG0001-R1.R2.R4.R2.R1`
- `VPNG0001-R1.R2.R4.R5`

# 3.1. Recovered configuration-language principles

The source material distinguishes two layers:

```text
stable user semantics
    -> should be recovered into NG3 requirements

last agreed prototype spelling
    -> evidence for schema design, but not automatically NG3 schema v1
```

This distinction is especially important for Device NAT, traffic-envelope and publication
fields.

The historical config work established principles stronger than any one prototype spelling:

- object IDs use stable opaque identifiers; current recovered grammar is
  `[a-z0-9][a-z0-9-]*`;
- field names use semantic `snake_case`;
- booleans are real TOML booleans and are not encoded as strings/numbers;
- enum-like values use one canonical lowercase spelling;
- collection-valued fields use plural names unless ordering itself is the semantic
  (`device_order`);
- derived/redundant quantities are not repeated by the user;
- Linux implementation vocabulary such as ifindex, route metric, table ID or rule priority
  is not exposed unless it becomes a real user policy knob;
- ambiguous or non-canonical input is rejected rather than silently repaired.

Examples of strict validation already recovered:

- destination CIDRs must be strict network forms; host bits are not silently normalized;
- meaningless duplicate declarations are rejected;
- unknown object references are errors while known disabled references are valid;
- positive quantities such as prefix-selector quota must be strictly greater than zero.

Timing/unit field names remain unresolved at the human-facing layer. Internal names such as
`interval_seconds` or `failure_ticks` must not be copied into user config merely because
they exist in runtime types.

# 4. Device

A Device is a user-described **transport capability**, not a runtime binding object and not
a Manager.

Conceptually:

```text
Device
    = which VPN/network transport capability may satisfy Profiles
```

It may describe:

- how concrete VPN interfaces are expected/discovered;
- static administrative preference inside the Device;
- transport/path NAT intent;
- a restrictive Device traffic envelope;
- transport publication intent;
- other transport-specific policy that does not belong to Profile payload need.

A Device does not guarantee that any runtime interface exists and does not store current
binding state.

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

Runtime binding additionally preserves the previously accepted deterministic admission
semantics:

- Linux concrete endpoint identity is `(ifname, ifindex)`;
- same-name/new-ifindex is a fresh concrete endpoint;
- already bound survivors are not reordered/evicted by newcomers;
- over-quota candidates may be observed for diagnostics but are not policy paths;
- after verified removal frees capacity, waiting candidates are promoted deterministically
  by committed first-observed order;
- simultaneous fresh candidates keep kernel-snapshot order with ifindex tie-break;
- lexical ifname order is not user priority.

These rules implement the user's configured selector/quota order without turning incidental
interface naming into hidden policy.

**Requirements:**
- `VPNG0001-R1.R3.R4`
- `VPNG0001-R1.R3.R4.R1`
- `VPNG0001-R1.R3.R4.R2`
- `VPNG0001-R1.R3.R4.R3`
- `VPNG0001-R1.R3.R4.R4`

## 4.1. Device policy concepts recovered from historical design

The following concepts are considered stable enough to retain as product-model input while
their final NG3 human-facing grammar remains under review.

### NAT intent

Historical Device policy distinguished at least:

```toml
nat = "none"
nat = "masquerade"
```

The last agreed prototype deliberately had **no implicit NAT default** for an active Device.

Semantics:

- `none`: VPN-GATE performs no payload source NAT for this Device/path;
- `masquerade`: payload source NAT is applied through the current concrete path of the
  Device.

NAT belongs to transport/path policy, not availability/health.

The spelling `nat = "none|masquerade"` is the last agreed prototype and is strong schema
evidence. NG3 requirements already retain the semantic obligation that NAT intent be explicit;
the final schema review must decide whether this exact spelling becomes normative. No
`snat = <address>` capability is recovered from the prototype.

### Device traffic envelope

Device traffic envelope is administrator-authored restrictive policy over tunnel traffic.

Its invariant is:

```text
effective permission
    = Profile permission
      INTERSECT
      Device traffic envelope
```

The envelope may restrict traffic allowed by Profile semantics but must never expand Profile
permission or bypass Profile direction/destination/path eligibility.

Historical design included source/destination prefixes, protocol and ports.

Recovered prototype example:

```toml
[device.oc-main.traffic_envelope]
default = "allow"

[[device.oc-main.traffic_envelope.rules]]
direction = "from-device"
action = "drop"
source = "10.20.0.0/16"
protocol = "tcp"
destination_ports = ["8007"]
```

Recovered value grammar also used strict port forms:

```text
"N"
"A-B"
```

with inclusive `1..65535` bounds and rejection of reversed/invalid ranges.

However the normative NG1 config document explicitly left the **final human-facing
traffic-envelope TOML grammar unresolved**. These examples are prototype evidence, not
automatic NG3 schema.

### Device publications

Publication belongs to Device/transport binding, not Profile routing.

Conceptually it maps a host-side TCP/UDP transport endpoint to an internal transport endpoint
inside the managed network domain so VPN transport configuration can remain stable.

EXP-010/011 prove publication as a technical boundary, including real OpenConnect same-port
TCP/UDP publication.

Recovered prototype publication syntax used compact values such as:

```text
<external>/<protocol>[><internal>]

44443/tcp
5678/udp>7890
4700:4900/udp>55200:55400
```

Recovered value rules included:

- ports `1..65535`;
- inclusive ranges;
- equal cardinality for range-to-range mapping;
- rejection of reversed/invalid ranges;
- rejection of semantically ambiguous overlaps;
- TCP and UDP are separate protocol domains.

Historical NG1 explicitly left the **final human-facing publication grammar unresolved**.
NG3 must not declare this prototype syntax normative merely because it was discussed.

### Requirement trace

The recovered Device policy/config semantics refine:

- `VPNG0001-R1.R2.R4.R6`;
- `VPNG0001-R1.R2.R4.R6.R1`;
- `VPNG0001-R1.R2.R4.R6.R2`;
- `VPNG0001-R1.R2.R4.R6.R3`;
- `VPNG0001-R1.R2.R4.R6.C1`;
- `VPNG0001-R1.R2.R5` and its canonical-config children.

These nodes remain open until the full Device/config + experiment recovery review is
performed.

### Ordering

The administrative path-priority hierarchy remains:

```text
Profile.device_order
    -> Device.expected_interfaces order
        -> stable runtime slots within selector quota
```

This ordering is user policy. Runtime discovery may not replace it with lexical interface
ordering.

## 4.2. Logical paths derived from Device slots

Users do not name every runtime/logical VPN path in Profile configuration.

For an active Device, normalized path identity is derived from the stable configured binding
shape:

```text
logical_path_id :=
    device_id
    + expected_interface selector position
    + stable slot within selector quota
```

The currently observed Linux/VPN endpoint is a binding of that identity, not the identity
itself.

Consequences:

- replacing the concrete endpoint can preserve the logical path identity;
- adding another endpoint must not rename/reorder surviving slots;
- Profile policy may reference a Device while runtime policy expands that Device into its
  currently valid logical paths;
- status and availability can name the logical path without depending on transient ifname or
  interface index.

**Requirements:**
- `VPNG0001-R1.R2.R2`
- `VPNG0001-R1.R3.R1`
- `VPNG0001-R1.R3.R3`
- `VPNG0001-R1.R3.R4.R3`
- `VPNG0001-R1.R3.R4.R3.R1`
- `VPNG0003-R3.R1.R1`

# 5. Profile

An enabled Profile expresses one independent logical routing/payload-policy domain: a user
network need that remains meaningful independently of the current VPN transport instances.

Profile is **not**:

- a VPN interface;
- a VPN peer;
- a tunnel/session;
- a Linux route metric;
- an availability probe target;
- a container for concrete Linux rules.

Device/binding layers provide transport capability; Profile describes what network behavior
that capability is allowed to satisfy.

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

First-release constraint:

```text
outbound
    -> multi-path allowed

inbound | bidirectional
    -> maximum eligible logical-path capacity <= 1
```

Capacity is computed from currently enabled referenced Devices and their configured
expected-interface selector quotas. A runtime moment with only one currently present
interface does not make a capacity>1 Profile valid.

**Requirements:**
- `VPNG0002-R2.R3.R3`
- `VPNG0002-R2.R3.C1`
- `VPNG0002-R2.R3.C1.R1`.

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
- `VPNG0002-R2.R1.R1`
- `VPNG0002-R2.R1.R2`
- `VPNG0002-R2.R5.R1`

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
- `VPNG0002-R2.R2.R1`
- `VPNG0003-R3.R1.R1`

# 6. Profile runtime normalization

After Device binding, one enabled Profile normalizes to a structural payload request:

```text
PayloadProfileRequest:
    profile_id
    direction
    destinations[]
    ordered_paths[]
```

The path list is obtained from currently valid bindings of enabled Devices in
`Profile.device_order`.

It may be empty.

```text
paths = 0
    !=
Profile disappeared
```

With zero paths the Profile remains the owner of its destinations and materializes
fail-closed terminal behavior. Traffic must not fall through to ambient/main routing merely
because no VPN path is currently usable/bound.

The structural request is independent from availability. Availability may only change the
effective ordering of existing paths.

It must not change:

- Profile destinations;
- direction;
- Device membership;
- binding eligibility;
- structural existence of the Profile.

**Requirements:**
- `VPNG0001-R1.R2.R4.R4.R2`
- `VPNG0001-R1.R2.R4.R4.R3`
- `VPNG0002-R2.R2.R2`
- `VPNG0003-R3.R2.R1`
- `VPNG0004-R4.R1.R1`

# 7. Profile-scoped availability

Availability is a property of one Profile/path use, not of a physical interface globally.

Availability is not part of structural Profile membership. It is a negative priority
modifier applied after the Profile's eligible path set has been obtained from binding.

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
- `VPNG0001-R1.R2.R4.R4.R1`
- `VPNG0003-R3.R6.R1`
- `VPNG0003-R3.R6.R3.R1`
- `VPNG0003-R3.R6.R3.R1.C1`
- `VPNG0003-R3.R6.R3.R2`

# 8. Configuration normalization boundary

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

# 9. Required validation behavior

At minimum, accepted configuration must enforce:

- valid unique Device/Profile IDs;
- explicit boolean `enabled`;
- active Device has non-empty valid `expected_interfaces`;
- expected-interface selector ambiguity is rejected;
- active Profile has explicit valid direction;
- active Profile has non-empty strict IPv4 destinations;
- active Profile has non-empty unique Device references;
- first-release `inbound`/`bidirectional` Profile is rejected if the sum of selector quotas
  across its currently enabled referenced Devices exceeds 1; this validation is based on
  configured maximum eligible path capacity, not on current observed interface count;
- unknown Device reference is rejected;
- exact duplicate destination ownership across enabled Profiles is rejected;
- overlapping destinations remain deterministic;
- availability target is normalized to a concrete IPv4 before runtime probe execution;
- any semantic failure is reported before dependent network actuation;
- active Device NAT intent is explicit when NAT capability is used;
- user input is not silently canonicalized when the accepted contract requires strict form;
- derived values such as aggregate Device quota are not required from the user.

Disabled placeholders are the explicit exception to active-object field completeness.

# 10. What is not inherited from NG1

This recovered config model does not require NG3 to restore:

- DeviceEngine;
- TrafficEngine;
- PlannerEngine;
- NG1 runtime state classes;
- NG1 metric allocator implementation;
- transport publication machinery;
- any guessed Device traffic-envelope grammar (the concept is retained; grammar remains
  unresolved);
- any guessed Device publication grammar (the concept is retained; grammar remains
  unresolved);
- old process topology.

Those require independent NG3 requirements if needed.

# 11. Implementation consequences

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

# 12. Historical Profile status work intentionally not imported

Recovered discussions considered a final aggregated `ProfileState` composed from binding,
payload-rule, publication and probe diagnostic facts.

That aggregation semantics was explicitly unfinished.

Therefore this config recovery does not invent a single Profile verdict or make probe
diagnostics control routing through status. A stronger Profile-specific status model remains
a separate future requirement/design unit if needed.
