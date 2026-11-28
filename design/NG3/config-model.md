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
- `VPNG-U001-R4.R4`
- `VPNG-U001-R4.R4.R1`
- `VPNG-U001-R4.R4.R3`
- `VPNG-U001-R4.R4.R4`

## 1.1. Release-1 host-routing control



Release 1 separates **which ordinary-host traffic may be assisted** from **how strongly the
helper owns that routing area**:

```toml
helper_routing_interfaces = ":none"   # default
helper_routing_policy = "peaceful"    # default
```

`helper_routing_interfaces` is one canonical comma-separated selector string:

- `":none"` — helper disabled; this value must appear alone;
- `":local"` — host-originated traffic;
- `":external"` — all non-local ordinary-host ingress traffic; this value must appear alone;
- `":any"` — host-originated plus all non-local ordinary-host ingress traffic; this value
  must appear alone;
- an exact host interface name — traffic received through that interface;
- `":local,<ifname>,<ifname>..."` or a list of exact interface names — the union of those
  selectors.

Exact interface names use the same canonical Release-1 Linux-interface spelling accepted by
the existing configuration boundary. `lo` is therefore an ordinary exact interface name and
may be combined with other names, for example `"lo,eth0"`. Tokens beginning with `:` are
reserved product selectors rather than interface names; the colon is intentionally not a
valid Linux interface-name character in the supported grammar.

The managed HOST↔STACK boundary is never an ordinary helper ingress selector. Packets already
emitted by STACK must not be captured back into STACK even when `":any"` or
`":external"` is selected.

`helper_routing_policy` defaults to `"peaceful"`. Release 1 accepts only
`"peaceful"`: lifecycle operations may install/update/remove identifiable helper
contributions, but the helper does not continuously reclaim administrator changes between
those operations. The future canonical value `"aggressive"` is reserved for the separately
postponed authoritative helper under `VPNG-U001-R5.R2` and must be rejected until that
capability completes its own requirement/design closure.

The peaceful helper never enables or disables global host IPv4 forwarding. If the effective
selector includes non-local ingress while IPv4 forwarding is disabled, the implementation
may report that prerequisite as an operator-visible warning/problem, but ownership of the
sysctl remains with the administrator.

The defaults deliberately make installation non-invasive: omitting both fields leaves
ordinary-host routing untouched.

## 1.2. Release-1 operational logging

Release 1 exposes one canonical root logging threshold:

```toml
log_level = "info"
```

Accepted values are exactly `"error"`, `"warning"`, `"info"` and `"debug"`.
Omission means `"info"`, preserving useful ordinary operational logging without requiring a
new field in existing alpha configurations. The threshold is inclusive: `info` emits
INFO/WARNING/ERROR, while `debug` additionally emits component-reaction records.

This field controls only operational logging under `VPNG-M001-R2.R3`. It does not enable the
separately deferred developer execution trace under `VPNG-D001-R2`.

Exact log line punctuation and journald metadata are not configuration semantics.

**Requirements:**
- `VPNG-M001-R2.R3.R1`
- `VPNG-M001-R2.R3.R2`

## 1.3. Managed Device reclaim policy

The top-level TOML field `managed_reclaim` selects one domain-wide release policy:

```toml
managed_reclaim = "careful"
```

Accepted values are exactly `"careful"` and `"strict"`; omission means `"careful"`.
This is a release policy for already-present surplus managed ordinary VPN Devices,
not a Profile-local knob, not a new presence obligation, and not a modification of
`warm_paths` or its ordinary/reserve calculation.

Careful protects an exact already-present ordinary realization confirmed as currently
used by at least one enabled Profile. Unknown/stale evidence does not authorize
retirement. Strict considers the joint contribution of each physical Device to all
enabled Profiles and preserves for each affected Profile the smaller of its resolved
ordinary target and fresh pre-release eligible ordinary capacity. Among equally valid
choices, retaining current use is preferred; it is not an independent obligation in
strict mode. Successful strict reconciliation is single-removal irreducible, not
necessarily a globally minimum set.

Neither policy starts or restarts an absent Device for reclaim optimization. Explicit
disable/remove, product stop, stronger safety obligations and mandatory reserve
presence remain governed separately. Withdrawal of reserve demand after ordinary
recovery remains governed by R7.R3.R3 and safe dependency release; ordinary
membership of the same Device in another Profile must still be considered.

**Implementation state:** normalized configuration and helper/model boundaries exist;
normal lifecycle activation and integrated acceptance in #41 are pending. The field's
canonical semantics here are normative, not a claim of completed runtime support.

**Requirements:**
- `VPNG-U001-R1.R3.R7.R4`;
- `VPNG-U001-R1.R3.R7.R4.R1`;
- `VPNG-U001-R1.R3.R7.R4.R2`.

# 2. Current human-facing representation

The human-facing surface uses TOML root policy plus named Device/Profile tables. The optional
root `default_snat_address` supplies the common Profile SNAT identity when a Profile uses
bare `+snat`:

```toml
default_snat_address = "198.19.255.10"
log_level = "info"
helper_routing_interfaces = ":none"
helper_routing_policy = "peaceful"

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

**Requirement:** `VPNG-U001-R4.R4.R1.C1`.

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
- `VPNG-U001-R4.R4.R2`
- `VPNG-U001-R4.R4.R2.R1`
- `VPNG-U001-R4.R4.R5`

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
- `VPNG-U001-R1.R3.R4`
- `VPNG-U001-R1.R3.R4.R1`
- `VPNG-U001-R1.R3.R4.R2`
- `VPNG-U001-R1.R3.R4.R3`
- `VPNG-U001-R1.R3.R4.R4`

## 4.1. Canonical Release-1 Device policy grammar

The configuration-format review is complete for the ordinary Release-1 Device policy
surface. Only the canonical fields defined below are accepted for enabled Device objects.

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
    "out allow tcp to 10.20.0.0/16:80,443,8000-8007 # all current Device paths",
    "out deny udp to 10.20.0.53/32:53 via if wg0 # only the current wg0 path",
    "out deny udp to 10.20.0.53/32:53 via peer 172.20.130.6 # only this P2P path",
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
    [via if <exact-ifname> | via peer <IPv4>]
    [ # <comment>]
```

The physical string is one line; the layout above is only explanatory.

Rules:

- `in|out` is relative to the VPN Device/path, not Linux INPUT/OUTPUT;
- `out` means ordinary/host boundary -> VPN path;
- `in` means VPN path -> ordinary/host boundary;
- source/destination are literal packet fields at Device filtering time;
- an optional `via` clause is a path-applicability predicate, not a payload predicate;
- `via if <exact-ifname>` selects only a current path of this Device whose exact interface
  name equals the operand;
- `via peer <IPv4>` selects only the current point-to-point path of this Device whose
  observed private/inner peer equals the operand; this IPv4 is never the external VPN
  transport/server endpoint;
- a rule contains at most one `via` clause, so `via if` and `via peer` are mutually
  exclusive;
- a rule without `via` applies to every current path of the Device;
- the selector value is written once in the rule; no separate path declaration is required
  solely to make that rule addressable;
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

The current path-selector surface is deliberately small: Device-wide by omission, exact
current interface, or private/inner point-to-point peer. Resolution is performed only among
current paths already belonging to the Device; a matching host/private-network interface that
is not a current path of that Device is irrelevant.

`via if` uses the already verified current PathBinding and introduces no additional
observation dependency. `via peer` exists for dynamic point-to-point members whose exact
runtime interface cannot be known in advance and whose payload remote networks do not
distinguish the intended member. Confirmed absence of the requested peer means that the rule
currently selects no path; ambiguous matching or failed peer observation is not treated as
proof that the restriction is absent and must remain fail-closed.

This does not introduce a generic VPN-path identity system. WireGuard public keys, OpenVPN
CN/session IDs, L2TP tunnel/session IDs and external transport endpoints are not canonical
Device-firewall selectors under the current contract. If no active Device firewall rule
contains `via peer`, private-peer address observation is not a prerequisite for Device/path
binding or firewall realization.

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

- `VPNG-U001-R4.R4.R6`;
- `VPNG-U001-R4.R4.R6.R1`;
- `VPNG-U001-R4.R4.R6.R2`;
- `VPNG-U001-R4.R4.R6.R3`;
- `VPNG-U001-R4.R4.R6.C1`;
- `VPNG-U001-R4.R4.R6.R4`;
- `VPNG-U001-R4.R5` and its canonical-config children.

Only the canonical fields and top-level tables defined by this model are accepted for
enabled configuration objects; unknown fields/tables are rejected rather than interpreted as
aliases.

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
- `VPNG-U001-R4.R2`
- `VPNG-U001-R1.R3.R1`
- `VPNG-U001-R1.R3.R3`
- `VPNG-U001-R1.R3.R4.R3`
- `VPNG-U001-R1.R3.R4.R3.R1`
- `VPNG-U003-R3.R1.R1`

## 4.3. Явно управляемый VPN

Этот раздел задает каноническое пользовательское представление для Device, подготовку и
жизненный цикл VPN которого пользователь явно передает VPN-GATE. Отсутствие таблицы
`managed_vpn` сохраняет прежний контракт внешне подготовленного Device.

Наличие таблицы является самим явным включением управления; отдельный логический флаг для этого
не вводится.

Для текущего принятого WireGuard-варианта:

```toml
[device.wg-main]
enabled = true
use_outbound_nat = true

[device.wg-main.managed_vpn]
kind = "wireguard"
interface = "wg0"
address = "10.200.0.1/32"
private_key_file = "/etc/vpn-gate/secrets/wg-main.key"

[[device.wg-main.managed_vpn.peers]]
id = "edge-a"
public_key = "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="
endpoint = "198.51.100.10:51820"
probe_target = "10.201.0.1"

[[device.wg-main.managed_vpn.peers]]
id = "edge-b"
public_key = "ISIjJCUmJygpKissLS4vMDEyMzQ1Njc4OTo7PD0+P0A="
endpoint = "198.51.100.11:51820"
probe_target = "10.201.0.2"
preshared_key_file = "/etc/vpn-gate/secrets/wg-main-edge-b.psk"
```

Допустимое текущее значение `kind` — только `"wireguard"`. Другие VPN-интеграции должны
получить собственное предметное рассмотрение до появления новых значений.

### Источник истины для интерфейса

Для управляемого Device поле `expected_interfaces` не задается. Точный интерфейс выводится
из `managed_vpn.interface` как единственное условие выбора интерфейса с квотой 1.

Одновременное задание `managed_vpn` и `expected_interfaces` является ошибкой
конфигурации: одно и то же намерение не должно иметь два пользовательских источника истины.

`interface` должен быть допустимым точным именем Linux-интерфейса. В текущем WireGuard
контракте управляемый Device создает ровно один такой интерфейс.

### Базовая конфигурация WireGuard

Обязательные поля `managed_vpn`:

- `kind = "wireguard"`;
- `interface`;
- `address` — один канонический адрес IPv4 с длиной префикса;
- `private_key_file` — абсолютный путь к файлу закрытого ключа;
- непустой упорядоченный массив `peers`.

При необходимости может быть задан `listen_port` в диапазоне `1..65535`. Его отсутствие означает,
что конкретная WireGuard-реализация может выбрать локальный порт сама; это не меняет порядок
или идентичность пиров.

Каждый элемент `peers` обязан содержать:

- `id` — устойчивый непрозрачный идентификатор по обычной грамматике идентификаторов проекта;
- `public_key` — публичный ключ WireGuard;
- `endpoint` — точная транспортная точка IPv4 с UDP-портом;
- `probe_target` — точный IPv4-адрес, постоянно принадлежащий только этому пиру внутри
  туннеля.

Необязательное `preshared_key_file` является ссылкой на дополнительный секрет этого пира.

Порядок элементов `peers` является административным порядком предпочтения. Отдельное поле
приоритета не вводится. `id`, `public_key` и `probe_target` должны быть уникальны внутри
Device.

`probe_target` нормализуется в постоянный `/32` соответствующего пира. Он является
технической целью выбора WireGuard-пира и не заменяет `availability_check` Profile.

### Recoverable groups выводятся из Profile membership

Для generalized `VPNG-U001-R1.R3.R8` отдельная пользовательская сущность с повторным списком
payload-префиксов не вводится. Для каждого enabled Profile, использующего enabled managed
WireGuard Device, создается recoverable group identity:

```text
(profile_id, device_id)
```

Ее payload bundle — ровно `Profile.destinations`. Поэтому несколько destinations одного
Profile переключаются как одна группа, а разные Profiles на одном `wg0` могут одновременно
принадлежать разным peers. Если наборы сетей должны переключаться независимо, они выражаются
разными Profiles; отдельное cross-Profile group coupling не вводится без нового требования.

Overlap не получает второй набор правил: уже каноническая Profile semantics запрещает один и
тот же exact prefix в двух enabled Profiles и допускает different-length overlap только через
deterministic most-specific classification. Для derived WireGuard groups это одновременно
дает однозначный effective ownership: более специфичный `AllowedIPs` bundle имеет тот же
most-specific смысл; дополнительная неоднозначная group-prefix декларация отсутствует.

По умолчанию все peers из `managed_vpn.peers` являются разрешенными кандидатами группы в
порядке их объявления и имеют ordinary role. Profile может уточнить policy конкретного
Device membership:

```toml
[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.20.0.0/16", "10.30.0.0/16"]
device_order = ["wg-main", "oc-backup:reserve"]

[profile.corp.device_membership.wg-main]
peer_order = ["edge-a", "edge-b:reserve"]
```

`device_membership.wg-main` не создает membership и допустим только если `wg-main` уже
ровно один раз присутствует в `device_order`. `peer_order` допустим только для explicitly
managed WireGuard Device, является непустым ordered subset его peer IDs, не допускает
повторения одного peer и использует тот же канонический suffix `:reserve`. Omitted peers не
являются кандидатами этой группы. Отсутствие таблицы сохраняет default all-peer ordinary
policy. Unknown membership fields/suffixes являются config error; таблица не является generic
option bag.

Optional Profile availability description одновременно является group end-to-end description
для этого managed WireGuard membership только если она resolves в поддерживаемый ICMP target,
лежащий внутри `Profile.destinations` и не совпадающий ни с одним permanent peer
`probe_target`. Это переиспользование description не сливает A.007 и D.002 evidence:
semantic owners/verdicts остаются раздельными. Если условие не выполнено, group endpoint
отсутствует, но peer-failure recovery остается действующим.

Каждый peer `probe_target` остается зарезервированным техническим адресом конкретного пира.
Он может находиться внутри более широкого payload-префикса, включая `0.0.0.0/0`: постоянный
`/32` намеренно остается более специфичным `AllowedIPs` и используется для peer health.
Базовая конфигурация WireGuard содержит только эти permanent `/32`; payload prefixes
появляются в `AllowedIPs` только через подтвержденную D.002 group ownership projection.

Текущий `parse_current_config` принимает `device_membership.*.peer_order` и публикует
typed `CurrentConfig.wireguard_groups` с derived prefixes, peer memberships и qualifying
group availability description. D.002 потребляет эти typed groups напрямую; прежний
`ManagedWireGuardConfig.shared_prefixes` one-group bridge удален. Prefix bundle имеет один
user-facing source of truth — `Profile.destinations`.

### Транспортные разрешения не дублируются

Для управляемого WireGuard поле `allow_vpn_client` не задается. Требуемые разрешения UDP к
транспортным точкам из `managed_vpn.peers` выводятся автоматически.

Одновременное задание `managed_vpn.kind = "wireguard"` и `allow_vpn_client` является
ошибкой конфигурации. Это сохраняет один источник истины для транспортных точек WireGuard.

Остальные политики Device — `use_outbound_nat`, `firewall`, `availability_check` и
применимые публикационные намерения — сохраняют свой существующий смысл и не становятся
частью управления жизненным циклом VPN.

### Секреты

Основной TOML содержит только ссылки на секреты. Закрытый ключ WireGuard и необязательные
предварительно согласованные ключи пиров не записываются непосредственно в основной TOML и
не должны появляться в отчете о состоянии, диагностике или журналах.

`private_key_file` и `preshared_key_file` являются абсолютными путями. Перед применением
управляемой конфигурации нижняя интеграция должна свежим наблюдением подтвердить, что
ссылка ведет на обычный файл, принадлежащий эффективному UID процесса, который читает секрет, и что у
группы и остальных пользователей нет прав доступа к этому файлу. Символическая ссылка не
считается допустимым файлом секрета.

Содержимое файла читается только при формировании требуемого поколения базовой
VPN-реализации. Изменение содержимого по той же ссылке считается изменением желаемого
поколения. Для сравнения поколений допустимо хранить только необратимый криптографический хэш, а не
значение секрета.

Отсутствующий или небезопасный файл секрета переводит управляемый Device в состояние `problem` и должен
быть обнаружен до изменения принадлежащего VPN-экземпляра.

### Сохранение externally managed Device mode

Отсутствие `managed_vpn` сохраняет явно внешний lifecycle/ownership Device; это локальный
integration mode, а не заявление о межверсионной обратной совместимости по `VPNG-M001-R4`.
Внешний контракт остается каноническим для такого Device:

```toml
[device.external-wg]
enabled = true
expected_interfaces = ["wg0"]
allow_vpn_client = "udp>198.51.100.10:51820"
```

Такой Device не имеет `managed_vpn`; VPN-GATE не создает его WireGuard-конфигурацию, не
запускает и не останавливает его VPN-экземпляр и продолжает только наблюдать уже существующий
интерфейс по обычному контракту привязки.

**Requirements:**
- `VPNG-U001-R1.R3.R7`;
- `VPNG-U001-R1.R3.R7.R1`;
- `VPNG-U001-R1.R3.R7.R2`;
- `VPNG-U001-R1.R3.R7.R3`;
- `VPNG-U001-R1.R3.R8`;
- `VPNG-U001-R4.R5`;
- `VPNG-U001-R4.R5.R2`;
- `VPNG-U001-R4.R5.R4`.

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
inbound+snat>IPv4
bidirectional
bidirectional+snat
bidirectional+snat>IPv4
```

Meaning:

- `outbound`: ordinary/host side may initiate NEW flows toward Profile destinations;
- `inbound`: remote side through a permitted Profile Device/path may initiate NEW flows
  toward ordinary/host side;
- `bidirectional`: both sides may initiate;
- bare `+snat` requests Profile-scoped source translation for the VPN-to-ordinary leg,
  after managed firewall/policy and before the packet leaves the managed network domain;
- `+snat>IPv4` requests the same translation but selects an explicit Profile SNAT identity.

Without `+snat`, VPN-to-ordinary payload leaves the managed domain with its original remote
source address. Bare `+snat` uses the top-level `default_snat_address`; the explicit address
after `>` overrides that default for the Profile. If any enabled Profile uses bare `+snat`,
`default_snat_address` is required.

`outbound+snat...` is invalid because outbound-only Profile does not authorize the
VPN-to-ordinary leg. There is no separate Profile `gateway_nat`, `snat_address` or
return-routing field. Return handling is internal product behavior, not a user-selectable
direction modifier.

Direction is explicit and is not inferred from topology. Configuration normalization strips
the SNAT suffix into base direction plus an optional effective Profile SNAT identity before
structural routing consumes the base direction.

### 5.1.1 Profile SNAT identity

The top-level default is an IPv4 string:

```toml
default_snat_address = "198.19.255.10"
```

An explicit Profile override is carried in the direction string:

```toml
direction = "inbound+snat>198.19.255.11"
```

Every effective SNAT identity must be a unicast IPv4 address. Multiple `+snat` Profiles may
intentionally share the same effective address; this groups them into one administrative
source identity after the managed boundary.

An effective SNAT address must not belong to source address space that can leave the managed
boundary untranslated in the same enabled configuration. In Release 1 this includes the
remote destinations of every enabled Profile with no effective `+snat`: outbound-only
Profiles can still emit untranslated remote sources on established replies, while inbound and
bidirectional Profiles can emit them on VPN-originated traffic. It must also not reuse an address that
VPN-GATE simultaneously owns for another service/transport role on the managed boundary.
Configuration-known conflicts are rejected during normalization; environment-resolved
boundary conflicts are fail-closed before activation.

Profile SNAT defines only the source identity presented at the managed boundary. What the
ordinary host subsequently does with that IPv4 source — route it, filter it, account it or
apply another host-side NAT — is outside Profile SNAT semantics.

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
- `VPNG-U001-R3`
- `VPNG-U001-R4.R4.R4.R4`
- `VPNG-U001-R4.R4.R4.R4.C1`
- `VPNG-U002-R2.R1.R3`
- `VPNG-U002-R2.R3.R3`
- `VPNG-U002-R2.R3.C1`
- `VPNG-U002-R2.R3.C1.R1`.

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
- `VPNG-U002-R2.R1.R1`
- `VPNG-U002-R2.R1.R2`
- `VPNG-U002-R2.R5.R1`

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

For managed Device presence, `:reserve` has an additional and deliberately orthogonal meaning:
it is excluded from `warm_paths`. A reserve Device may be brought up temporarily only while
ordinary warm capacity is deficient after ordinary convergence; its presence does not satisfy
the warm target and therefore cannot suppress continued recovery of ordinary Devices.

Newly appearing runtime endpoints must not arbitrarily reorder surviving already-bound
endpoints.

**Requirements:**
- `VPNG-U002-R2.R2.R1`
- `VPNG-U003-R3.R1.R1`
- `VPNG-U003-R3.R4.R1`
- `VPNG-U003-R3.R4.R1.R1`
- `VPNG-U003-R3.R8`
- `VPNG-U003-R3.R8.R1`

## 5.4 warm_paths

Current canonical Profile surface may select the number of **ordinary** paths that should be
kept warm independently from payload activity:

```toml
[profile.corp]
warm_paths = 2
```

Accepted values:

```text
0
positive integer N
"all"
```

Omitted `warm_paths` means `"all"`.

The target counts only enabled ordinary Device memberships. A `:reserve` membership is
explicitly excluded from warm capacity and from current warm satisfaction. Therefore:

```text
warm_paths = N
regular_present = R

regular_deficit = max(0, N - R)
```

For `"all"`, N is the sum of configured path capacity of all enabled ordinary memberships.
A finite N larger than that configured ordinary capacity is a configuration error even when
reserve capacity exists: reserve is not allowed to make an impossible warm target look valid.

Fresh current ordinary paths from externally prepared and explicitly managed Devices both
satisfy the target. The ownership difference begins only at actuation: VPN-GATE may start or
stop only explicitly managed Devices.

A numeric target is cardinality, not proactive identity rebalance. If enough ordinary paths
are already present, an absent higher-baseline ordinary managed Device is not started merely
to replace a present lower-baseline ordinary path. If ordinary paths are missing, additional
managed ordinary Devices are selected deterministically by the existing baseline hierarchy.

Reserve is a separate exception:

```text
ordinary convergence
    -> fresh regular_deficit > 0
        -> temporarily demand enough reserve capacity for the deficit
        -> keep ordinary recovery demand unchanged
    -> fresh regular_deficit == 0
        -> reserve exception no longer creates Device demand
```

Already-present reserve paths may satisfy the temporary reserve-support amount, but they never
reduce `regular_deficit`. This is what guarantees natural recovery: bringing reserve up does
not make the missing ordinary Device cease to be demanded.

A Device shared by multiple Profiles is structurally demanded when at least one Profile demands it.
The same Device may be ordinary in one Profile and reserve in another; membership role remains
Profile-local. Structural demand alone does not determine exact physical presence or authorize
retirement: see the separate domain-wide reclaim policy in §1.3.

Payload activity, first packet, idle time and availability outcome do not participate in
`warm_paths` demand. Availability retains its separate role as an effective-order modifier
of existing paths.

**Requirements:**
- `VPNG-U001-R1.R3.R7.R3`;
- `VPNG-U001-R1.R3.R7.R3.R1`;
- `VPNG-U001-R1.R3.R7.R3.R2`;
- `VPNG-U001-R1.R3.R7.R3.R3`;
- `VPNG-U001-R1.R3.R7.R3.R4`.

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
Device-membership set so the availability calculator can apply the role to every current
logical path of those Devices without reparsing human configuration strings.

It may be empty.

```text
paths = 0
    !=
Profile disappeared
```

With zero paths the Profile remains the owner of its destinations and materializes
fail-closed terminal behavior inside the managed policy domain. Once traffic has been
accepted into that Profile policy domain, absence of a usable/bound VPN path does not create
a different permitted forwarding result. This statement does not constrain ordinary-host
routing before traffic is handed to VPN-GATE.

The structural request is independent from availability. Availability may only change the
effective ordering of existing paths.

It must not change:

- Profile destinations;
- direction;
- Device membership;
- binding eligibility;
- structural existence of the Profile.

**Requirements:**
- `VPNG-U001-R4.R4.R4.R2`
- `VPNG-U001-R4.R4.R4.R3`
- `VPNG-U002-R2.R2.R2`
- `VPNG-U003-R3.R2.R1`
- `VPNG-U004-R4`

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

Release 1 uses one availability-check description shape wherever a concrete check is
defined:

```toml
[device.wg-main.availability_check]
mechanism = "icmp"
target = "198.51.100.20"
```

The same description may be written directly for a Profile when its business criterion
differs from the Device default:

```toml
[profile.accounting.availability_check]
mechanism = "icmp"
target = "10.20.30.10"
```

A Profile that wants the reusable Device description uses:

```toml
availability_check = "default"
```

Absence of `availability_check` on the Profile means no active availability check for that
Profile.

Semantics:

```text
Profile availability_check absent
    -> no active check

Profile availability_check = "default"
    -> for each (Profile, logical path), use that path's Device availability_check

Profile availability_check table
    -> use that Profile description for every availability subject of the Profile
```

The availability result remains scoped to `(Profile, logical VPN path)`; reusing a Device
description does not create Device-global health state.

For Release 1 the only supported description is `mechanism = "icmp"` plus one exact IPv4
`target`. If a Profile selects `default`, every enabled Device referenced by that Profile
must provide a valid Device availability-check description, otherwise configuration is
rejected before runtime materialization. Disabled Device placeholders remain shallow.

Release 1 intentionally exposes no availability interval, timeout, failure-count or
hysteresis knobs. Those remain implementation policy unless a later accepted requirement
makes them user policy.

**Requirements:**
- `VPNG-U003-R3.R6.R1`
- `VPNG-U003-R3.R6.R3.R1`
- `VPNG-U003-R3.R6.R3.R1.R1`
- `VPNG-U003-R3.R6.R3.R1.C1`
- `VPNG-U003-R3.R6.R3.R1.C2`
- `VPNG-U003-R3.R6.R3.R2`

## 7.1. Canonical example for currently settled Release-1 fields

This example intentionally exercises every currently settled external configuration feature. A concrete
deployment does not need to use every optional field. The Release-1 peaceful host-routing control is defined above under
`VPNG-U001-R5.R1.R1`; a deployment may omit it and retain the non-invasive `:none` default.

```toml
default_snat_address = "198.19.255.10"

[device.wg-main]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = true
allow_vpn_client = "udp:51820>198.51.100.10:51820"

[device.wg-main.availability_check]
mechanism = "icmp"
target = "198.51.100.10"
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

[device.oc-backup.availability_check]
mechanism = "icmp"
target = "198.51.100.20"
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
availability_check = "default"

[profile.remote-admin]
enabled = true
direction = "inbound+snat>198.19.255.11"
destinations = ["10.30.0.0/16"]
device_order = ["oc-server"]

[profile.remote-admin.availability_check]
mechanism = "icmp"
target = "10.30.0.1"
```

Notes:

- `expected_interfaces = ["vpn*/2"]` is valid; bare `"vpn*"` is not, because a prefix
  selector requires an explicit positive quota;
- `use_outbound_nat` controls ordinary-to-VPN payload source masquerade and is unrelated to
  Profile `+snat`; bare Profile `+snat` uses `default_snat_address`, while
  `+snat>IPv4` selects a Profile-specific identity;
- `allow_vpn_client` allows the VPN implementation's own narrowly bounded client
  transport/control flow inside the otherwise DROP-by-default managed local plane;
- `publish_vpn_server` describes server-side host publication and is independent from
  Profile routing;
- Device `firewall` can only narrow the permission already created by Profile policy;
- Profile owns the decision to check availability; it may select `"default"` to reuse each
  Device's default description or provide its own `[profile.<id>.availability_check]` block;
  Device defaults and Profile overrides use the same `mechanism + target` description shape.

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

NG3 instead uses the independently accepted canonical grammar for the settled Release-1 fields in this document.
The Release-1 peaceful host-routing helper controls are the canonical top-level `helper_routing_interfaces` and `helper_routing_policy` fields defined in section 1.1; the former `host_routing = "auto" | "manual"` spelling and other historical host-routing controls are not inherited.

Other additions require independent NG3 requirements if needed.

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
