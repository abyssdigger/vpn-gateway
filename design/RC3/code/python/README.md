# RC3 Python implementation

This directory is the active RC3 implementation line. RC2 remains a frozen regression
baseline under `design/RC2/code/python/`.

## Current domain model

RC3 is interface-centric and transport-agnostic. A routing profile describes protected
routes plus an ordered set of binding specifications:

```toml
enabled = true
reconcile_interval = 10.0

common_allowed_sources = [
    "10.200.200.8/32",
]

[profiles.primary]
enabled = true
routes = [
    "10.0.0.0/8",
    "192.168.0.0/16",
]
allowed_sources = []

bindings = [
    { interface = "wg0",    network = "172.20.126.0/29" },
    { interface = "wg1",    network = "172.20.127.0/29" },
    { interface = "ocvpn+", network = "172.20.130.0/29" },
]
```

Each `BindingSpec` owns:

- one exact interface selector or one trailing-`+` textual prefix selector;
- its own IPv4 transport network;
- for exact entries, a fixed config-derived priority rank.

There is no LIST selector domain type. Multiple exact bindings are expressed as multiple
ordered `bindings[]` entries.

A concrete runtime binding is identified by exact `name + ifindex`. A candidate becomes
active only when it has at least one local IPv4 address inside the network of its owning
BindingSpec. Point-to-point remote address, transport peer, handshake, `operstate` and
`LOWER_UP` are not binding truth.

## Enabled projection

`enabled` defaults to true at both top-level and profile level.

Parsing is staged:

1. parse TOML and top-level envelope;
2. if top-level `enabled=false`, stop before profile-body parsing;
3. inspect only `profile.enabled`;
4. discard disabled profiles before parsing their body;
5. fully parse and cross-validate enabled profiles only.

A disabled profile is intentionally not linted by normal startup or `--check-config`.
Top-level `enabled=false` produces the intentional `DISABLED` lifecycle state with
`ip_forward=0` and no managed network materialization.

`common_allowed_sources` and per-profile `allowed_sources` are optional and default to
empty. Enabled profiles require non-empty `routes[]` and `bindings[]`.

## Selector and address-space safety

Enabled BindingSpec selector namespaces are globally non-overlapping.

Exact forbidden interface names are:

```text
lo
any
default
all
```

A prefix selector is also rejected if its guard namespace would include any forbidden
exact name. This matters because `-i prefix+` is a deny-only guard over the whole textual
namespace.

Binding networks may overlap each other because selector namespaces determine ownership.
Protected routes may not overlap any enabled BindingSpec network.

## Routing and metrics

Every protected destination always has:

```text
BLACKHOLE proto 201 metric 65536
```

Every active concrete binding receives a direct route:

```text
dev <exact-interface> proto 202 metric <N>
via=None
onlink=False
```

Exact bindings use fixed metrics derived only from their ordinal among exact BindingSpec
entries:

```text
FIRST_UNICAST_METRIC = 10
ROUTE_METRIC_STEP    = 10

exact_metric(rank) = 10 + rank * 10
```

Prefix entries between exact entries do not consume exact ranks. Therefore an ordered
profile such as:

```text
wg0, oc-a+, wg1, oc-b+
```

has fixed exact metrics:

```text
wg0 -> 10
wg1 -> 20
```

and all prefix bindings share one process-local cyclic allocator beginning at:

```text
dynamic_metric_min = 10 + exact_count * 10
                   = 30
```

Consequences:

- all exact bindings are preferred over all dynamic prefix bindings;
- exact failover/failback is stable across interface disappearance/recreation;
- prefix position in `bindings[]` does not define route preference;
- continuous prefix survivors keep their metrics;
- newly accepted prefix bindings do not renumber survivors;
- removed prefix metrics remain reserved until the new verified state commits;
- the allocator wraps, skips occupied slots and fails closed on true exhaustion;
- prefix allocator/order state is process-local and is rebuilt after restart.

## Runtime ordering

Active serialization order is:

1. active exact bindings by exact config rank;
2. active prefix bindings by process-local first-acceptance order.

Prefix survivors keep relative order; new prefix bindings append in fresh interface
inventory encounter order. No additional interface-name sorting is performed.

This order drives binding-specific firewall/NAT/status serialization. It is diagnostic
state, not a prefix route-priority contract.

## Firewall/NAT and lifecycle

Allowing INPUT/FORWARD rules, NAT and routes always use exact active interface names.
Prefix syntax appears only in deny guards.

Normal local lifecycle:

```text
ADD    = NAT -> verify -> filter -> verify -> route -> verify -> commit
REMOVE = filter -> verify -> route -> verify -> NAT -> verify -> commit
```

Neither normal ADD nor REMOVE changes `ip_forward`.

Same-name/new-ifindex replacement is:

```text
REMOVE old -> verified gap -> ADD new
```

Surviving rules/routes are not deleted, recreated, reordered or re-metriced merely to
canonicalize output.

`INIT/PANIC` is the global fail-closed path for startup, unsafe/unknown transit state,
non-decomposable transitions, local-procedure failure, or failed structural route
build/apply/verification.

Route-only drift is first repaired under a verified SAFE filter. If the route pass cannot
be structurally verified, the pass escalates to `INIT/PANIC`.

Structural verification is distinct from functional availability:

- structurally exact zero-path state is committed;
- its `ProfileResult` is `FAIL`;
- daemon lifecycle is `DEGRADED`, not PANIC.

Verified process-local state uses a two-phase commit: all prospective profile state is
prepared/validated before the first committed-state mutation.

## EXP-009 boundary

EXP-009 established the key transport boundary:

- OpenConnect can expose multiple simultaneous concrete interfaces;
- protected traffic works through direct `dev <interface>` routes;
- interface disappearance removes dependent kernel routes;
- WireGuard chooses peers through `AllowedIPs`, not through Linux route next-hop;
- multiple WireGuard peers behind one `wg0` are therefore not VPN-GATE failover units.

VPN-GATE failover/failback is built from independent concrete interfaces. This is why
binding-specific networks are required: `wg0`, `wg1`, and dynamic OpenConnect sessions
may legitimately belong to different transport networks inside one routing profile.

## Validation

Permanent CI is defined in:

```text
.github/workflows/rc3-python.yml
```

It runs on pushes and pull requests to `main` using Python 3.13:

```text
python -m compileall -q design/RC3/code/python
python -m unittest discover -s design/RC3/code/python/tests -p 'test_*.py' -v
```

The suite covers config staging, BindingSpec qualification, heterogeneous transport
networks, exact failback, shared prefix allocation, survivor order/metrics, same-name/new
ifindex replacement, firewall/NAT drift handling, ADD/REMOVE/INIT-PANIC, route planning,
zero-path verification, IPv6 latch and disabled runtime state.

## Entry point

```text
vpn-gatewayd.py
```

Implementation package:

```text
vpn_gatewayd/
```

Tests:

```text
tests/
```
