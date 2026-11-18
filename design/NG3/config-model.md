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

No accepted NG3 requirement currently requires user-facing availability timing/unit knobs.
Internal names such as `interval_seconds` or `failure_ticks` therefore must not be copied into
user config merely because they exist in runtime types. If a later accepted requirement makes
such knobs user policy, that future capability must receive its own configuration-format
review rather than extending Release-1 syntax implicitly.

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

## 4.1. Canonical Release-1 Device policy grammar

The configuration-format review is complete for the ordinary Release-1 Device policy
surface. Historical NG1/NG3 prototype spellings remain evidence only and are **not**
compatibility aliases.

### Outbound Device NAT

For a Device that can currently serve an ordinary-to-VPN leg of an enabled Profile
(`outbound` or `bidirectional`), the field is mandatory:

```toml
use_outbound_nat = true
```

or:

```toml
use_outbound_nat = false
```

Normalization is exact:

```text
false -> NatIntent.NONE
true  -> NatIntent.MASQUERADE
```

The field belongs to the Device because it changes the source representation of payload
traffic as it leaves through that VPN transport/path. It is not an availability setting and
is independent from Profile ordinary-side `+snat`.

For a Device that participates only in inbound Profiles, the field is not required because
there is no ordinary-to-VPN payload leg on which this NAT could operate.

Historical `nat = "none|masquerade"` is rejected by the canonical Release-1 parser.

### Client-side VPN transport/control allow

A VPN client process running inside the fail-closed managed domain may need a narrowly bounded
underlay/control flow to reach its remote VPN server. This is part of the Device transport
contract, not a separate top-level integration object.

Canonical forms:

```toml
allow_vpn_client = "udp:11941>198.51.100.20:11940"
```

or, when the local source port is intentionally dynamic:

```toml
allow_vpn_client = "tcp>198.51.100.20:443"
```

Multiple flows use an array:

```toml
allow_vpn_client = [
    "tcp>198.51.100.20:443",
    "udp>198.51.100.20:443",
]
```

Grammar:

```text
tcp|udp[:<local-port>]><remote-IPv4>:<remote-port>
```

Ports are integers in `1..65535`. The remote endpoint is an exact IPv4 address; hostnames
and ambient socket discovery are not accepted as substitutes. When local port is omitted,
the reverse allow remains bounded by exact remote/address/boundary facts plus established
connection state as defined by the supported-integration local/system policy.

Top-level `[integration.*]` is not part of the Release-1 human-facing model.

### Ordered Device firewall

The Device firewall is an ordered array of one-line rules:

```toml
firewall = [
    "out allow tcp to 10.20.0.0/16:80,443,8000-8007 # web bundle",
    "out allow icmp to 10.20.0.0/16",
    "in allow tcp from 10.20.0.0/16:1024-65535 to 10.0.0.10/32:22 # SSH to bastion",
    "in reject tcp to 10.0.0.0/24:23",
]
```

Rule grammar:

```text
<in|out> <allow|deny|reject>
    [tcp|udp|icmp]
    [from <IPv4-CIDR>[:port-bundle]]
    [to <IPv4-CIDR>[:port-bundle]]
    [ # <comment>]
```

The physical string is one line; the layout above is only explanatory.

Rules:

- `in|out` is relative to the VPN Device/path, not Linux INPUT/OUTPUT;
- `out` means ordinary/host boundary -> VPN path;
- `in` means VPN path -> ordinary/host boundary;
- source/destination are literal packet fields at Device filtering time;
- a `port-bundle` is one or more comma-separated items with no whitespace;
- one item is either exact `N` or inclusive range `A-B`;
- every port is in `1..65535`, every range has `A <= B`;
- the same physical port may appear only once in a bundle: duplicate exact values,
  exact-within-range and overlapping ranges are rejected;
- declared bundle item order is preserved;
- port bundles require explicit `tcp` or `udp`; ICMP cannot carry transport ports;
- CIDRs are strict IPv4 networks;
- rule order is semantic and first terminal match wins;
- omitted `firewall` means no additional Device-layer restriction;
- a non-empty explicit firewall has terminal no-match DROP;
- the parser does not reorder, widen or silently repair rules.

Endpoint-scoped Device firewall remains outside Release 1 under
`VPNG0001-R1.R2.R4.R6.R2.R5.C1`.

### Server-side VPN publication

Publication belongs to Device/transport policy, not Profile routing. The compact canonical
field is:

```toml
publish_vpn_server = "udp:44443"
```

for same external/internal port, or:

```toml
publish_vpn_server = "udp/eth0:53,123,5000-5003"
publish_vpn_server = "tcp/192.0.2.10:443,8000-8002,9000>8443,18000-18002,19000"
```

when an explicit host selector and/or port remap is needed. Multiple endpoints use an array.

Grammar:

```text
tcp|udp[/<host-IPv4|host-interface>]:<host-port-bundle>[><internal-port-bundle>]
```

Publication port bundles use the same compact, non-overlapping `N,A-B,...` grammar as
Device firewall port bundles.

Omitted `>internal-port-bundle` means identity mapping: every host port maps to the same
internal port. With an explicit internal bundle, both bundles are expanded in declared item
order into ordered sequences of individual ports; their cardinalities must be equal and
mapping is positional 1:1. For example:

```text
443,8000-8002,9000 > 8443,18000-18002,19000

443  -> 8443
8000 -> 18000
8001 -> 18001
8002 -> 18002
9000 -> 19000
```

Omitted host selector means the publication is not restricted by an additional user-selected
host address/interface. Protocol domains remain distinct.

The external publication mapping and the managed-domain local INPUT/OUTPUT admission are
separate lower responsibilities derived from this one Device intent. A runtime that has not
implemented the full publication path must reject/diagnose that requested capability rather
than silently ignoring it.

### Requirement trace

The canonical Device policy/config grammar implements:

- `VPNG0001-R1.R2.R4.R6`;
- `VPNG0001-R1.R2.R4.R6.R1`;
- `VPNG0001-R1.R2.R4.R6.R2`;
- `VPNG0001-R1.R2.R4.R6.R3`;
- `VPNG0001-R1.R2.R4.R6.C1`;
- `VPNG0001-R1.R3.C1.C1.R3`;
- `VPNG0001-R1.R2.R5` and its canonical-config children.

Historical `nat`, `traffic_envelope`, `publications` and top-level
`[integration.*]` spellings are not accepted aliases.

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

Canonical Release-1 values:

```text
outbound
inbound
inbound+snat
inbound+route-return
inbound+snat+route-return
bidirectional
bidirectional+snat
bidirectional+route-return
bidirectional+snat+route-return
```

Meaning:

- `outbound`: ordinary/host side may initiate NEW flows toward Profile destinations;
- `inbound`: remote side through a permitted Profile Device/path may initiate NEW flows
  toward ordinary/host side;
- `bidirectional`: both sides may initiate;
- `+snat` requests Profile-scoped ordinary-side gateway source NAT only for the
  VPN-to-ordinary leg after the managed firewall boundary;
- remote-initiated return traffic uses stateful host-boundary return steering by default;
- `+route-return` opts out of that steering and requires ordinary host routing through the
  managed boundary for the return leg;
- admitted return traffic otherwise remains stateful.

`outbound+snat` is invalid because the suffix controls a VPN-to-ordinary leg that an
outbound-only Profile does not authorize. `outbound+route-return` is invalid because
outbound-only Profile does not authorize remote-initiated flows. There is no separate
Release-1 `gateway_nat` or return-routing field.

Canonical combined ordering is `+snat+route-return`; reversed suffix order is rejected.
Direction is explicit and is not inferred from topology. Configuration normalization strips
the suffixes into separate ordinary-side gateway NAT and route-return intents before
structural routing consumes the base direction.

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

`device_order` is a non-empty ordered list of unique Profile-local Device memberships.

An ordinary membership is written as the Device ID. A principally fallback membership may
carry the canonical `:reserve` suffix:

```toml
device_order = [
    "oc-main",
    "wg-backup:reserve",
]
```

The suffix describes the Device's role **inside this Profile only**. It does not mutate the
Device object and does not imply the same role in another Profile. All logical paths produced
from that Device membership inherit the Profile-local reserve role.

Canonical parsing normalizes each entry into:

```text
device_id
reserve = true | false
```

and passes the plain Device ID to structural Device-reference validation. Therefore:

- only referenced Devices are policy-eligible for the Profile;
- unknown Device IDs are invalid;
- known disabled Devices are valid references and are skipped while disabled;
- an unknown membership suffix is a configuration error;
- the same underlying Device ID may occur only once in one Profile, so
  `["oc", "oc:reserve"]` is invalid;
- absence of a suffix means ordinary sticky membership;
- list order is the user's baseline preference policy.

The baseline preference hierarchy is:

```text
Profile.device_order
    -> Device.expected_interfaces order
        -> stable runtime slot inside selector quota
```

The reserve role does not alter that baseline hierarchy. It only permits failback when a
reserve path currently occupies the active position and a more-preferred usable path has
recovered. For ordinary membership, a recovered path returns to its baseline position among
standby paths but does not preempt a still-usable active path.

Newly appearing runtime endpoints must not arbitrarily reorder surviving already-bound
endpoints.

**Requirements:**
- `VPNG0002-R2.R2.R1`
- `VPNG0003-R3.R1.R1`
- `VPNG0003-R3.R4.R1`
- `VPNG0003-R3.R4.R1.R1`
- `VPNG0003-R3.R8`
- `VPNG0003-R3.R8.R1`

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
`Profile.device_order`. Configuration normalization also retains the Profile-local reserve
Device-membership set so the availability layer can derive the corresponding reserve logical
paths without reparsing human configuration strings.

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

The canonical Release-1 field is a simple Profile scalar:

```toml
availability_check = "icmp"
```

or:

```toml
availability_check = "icmp/172.21.201.19"
```

Absence of the field means no active availability check for that Profile.

Semantics:

```text
icmp/<explicit-ip>
    -> use that IPv4 exactly

icmp
    -> deterministically derive one path-specific target
       for each availability subject from already accepted
       Profile/path/Device/interface/binding/peer topology
```

There is no global Device `tunnel_endpoint` and no universal default target. This is
important for selectors such as `expected_interfaces = ["wg*/3"]`: each admitted logical
path may have a different current peer/topology and therefore a different derived target.

Before probe runtime receives work, target normalization must have produced one concrete IPv4
for the specific availability subject. If omitted-target derivation is unresolved or
ambiguous, the requested check is not silently redirected to another address and the reason
must be diagnosable.

Release 1 intentionally exposes no availability interval, timeout, failure-count or
hysteresis knobs. Those remain implementation policy unless a later accepted requirement
makes them user policy.

Historical `interface_balancing` spelling is not an alias and is rejected by the canonical
parser.

**Requirements:**
- `VPNG0001-R1.R2.R4.R4.R1`
- `VPNG0003-R3.R6.R1`
- `VPNG0003-R3.R6.R3.R1`
- `VPNG0003-R3.R6.R3.R1.C1`
- `VPNG0003-R3.R6.R3.R1.C1.R1`
- `VPNG0003-R3.R6.R3.R2`

## 7.1. Complete canonical Release-1 example

This example intentionally exercises every settled external configuration feature. A concrete
deployment does not need to use every optional field.

```toml
[device.wg-main]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = true
allow_vpn_client = "udp:51820>198.51.100.10:51820"
firewall = [
    "out allow tcp to 10.20.0.0/16:80,443,8000-8007 # web bundle",
    "out allow icmp to 10.20.0.0/16",
    "in allow tcp from 10.20.0.0/16 to 10.0.0.10/32:22 # SSH to bastion",
]

[device.oc-backup]
enabled = true
expected_interfaces = ["vpn*/2"]
use_outbound_nat = false
allow_vpn_client = [
    "tcp>198.51.100.20:443",
    "udp>198.51.100.20:443",
]
firewall = [
    "out allow tcp to 10.20.0.0/16:443",
    "out allow icmp to 10.20.0.0/16",
]

[device.oc-server]
enabled = true
expected_interfaces = ["ocsvr0"]
publish_vpn_server = [
    "tcp/eth0:443,8000-8002,9000>8443,18000-18002,19000",
    "udp/eth0:53,123,5000-5003",
]
firewall = [
    "in allow tcp from 10.30.0.0/16 to 10.0.0.20/32:22",
]

[profile.corporate]
enabled = true
direction = "outbound"
destinations = ["10.20.0.0/16"]
device_order = ["wg-main", "oc-backup"]
availability_check = "icmp"

[profile.remote-admin]
enabled = true
direction = "inbound+snat"
destinations = ["10.30.0.0/16"]
device_order = ["oc-server"]
availability_check = "icmp/10.30.0.1"
```

Notes:

- `expected_interfaces = ["vpn*/2"]` is valid; bare `"vpn*"` is not, because a prefix
  selector requires an explicit positive quota;
- `use_outbound_nat` controls ordinary-to-VPN payload source masquerade and is unrelated to
  `direction = "inbound+snat"`;
- `allow_vpn_client` allows the VPN implementation's own narrowly bounded client
  transport/control flow inside the otherwise DROP-by-default managed local plane;
- `publish_vpn_server` describes server-side host publication and is independent from
  Profile routing;
- Device `firewall` can only narrow the permission already created by Profile policy;
- `availability_check` belongs directly to Profile because no Release-1 subfields/timing
  knobs justify a dedicated table.

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
- NG1 transport publication machinery merely because it existed there;
- historical Device-firewall spellings such as `traffic_envelope`;
- historical Device publication shorthand or range grammar;
- old process topology.

NG3 instead uses the independently accepted canonical Release-1 grammar in this document.

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
