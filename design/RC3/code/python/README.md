# RC3 Python implementation

This directory is the active RC3 implementation line.

It was bootstrapped from the frozen RC2.5.1 Python baseline in
`design/RC2/code/python/`. RC3 changes are applied here only; the RC2 tree remains a
regression baseline.

## Current RC3 implementation status

The Python implementation now follows the **interface-centric RC3 architecture accepted
after EXP-009**.

Implemented domain model:

- `InterfaceSelector` supports:
  - exact string: `"wg0"`;
  - multiple prefix: `"vpns+"`;
  - ordered explicit exact list: `["vpnA", "vpnB", "vpnC"]`;
- legacy `%` selector syntax is rejected;
- transport `peers` and exact `local_address` are not part of `VpnProfileConfig`;
  legacy managed keys with those names are rejected by the closed schema;
- one profile may have multiple simultaneous active concrete bindings;
- concrete binding identity is exact `name + ifindex`;
- a candidate becomes active only when it has at least one local IPv4 address inside the
  configured `network`;
- interface address prefix length is not compared with `network`; tunnel/P2P local /32
  representation remains valid when the host IPv4 belongs to the logical transport network;
- point-to-point remote endpoint, transport handshake and peer state are not route truth.

Active ordering:

- exact selector: one active interface;
- prefix selector: process-local stable order of first accepted bindings;
- explicit list: configured order filtered to active elements.

For `prefix+`, surviving bindings keep their relative order, new bindings append in the
order returned by the current interface inventory, and removed bindings disappear without
reordering survivors. No extra name sorting is applied. This order drives binding-specific
firewall/NAT materialization and is useful diagnostically; it is not a route-priority
guarantee and is not persisted across restart.

Routing:

- one `proto 201 metric 65536` BLACKHOLE remains required for every protected
  destination;
- every daemon-owned UNICAST metric is strictly lower than `BLACKHOLE_METRIC`;
- daemon-owned UNICAST routes are direct interface routes:
  `dev <exact-interface> proto 202 metric <N>`;
- desired UNICAST uses `via=None` and `onlink=False`;
- exact metric is `FIRST_UNICAST_METRIC` (currently 10);
- explicit-list slot N uses
  `FIRST_UNICAST_METRIC + N * ROUTE_METRIC_STEP` and therefore preserves configured
  priority holes;
- prefix metrics come from a cyclic process-local allocator;
- a continuously active prefix binding keeps its metric;
- new prefix bindings do not renumber existing routes;
- the allocator wraps before `BLACKHOLE_METRIC`, skips occupied values and fails closed
  only if every valid slot is occupied;
- prefix route preference between interfaces is intentionally unspecified.

Firewall/NAT:

- selector wildcards appear only in deny-only guards;
- allowing INPUT/FORWARD blocks and MASQUERADE rules use exact active interface names;
- all simultaneous active interfaces of a profile are materialized;
- normal binding lifecycle uses two local procedures without changing `ip_forward`:
  `ADD = NAT -> filter -> route` and `REMOVE = filter -> route -> NAT`, with
  verification between stages and without rebuilding surviving contributions;
- replacement, including same-name/new-ifindex, is `REMOVE old -> ADD new`;
- `INIT/PANIC` is the only global rebuild path and is reserved for startup, unexpected
  FORWARD/NAT drift, UNKNOWN state, non-decomposable transitions, or failed local apply;
- confirmed INPUT-only drift still uses narrow repair without disabling forwarding.

Lifecycle and verification:

- one immutable `ReconciliationSnapshot` is used per reconciliation pass;
- Netlink events are wakeup hints; the fresh snapshot decides;
- IPv6 host prerequisites are revalidated on every full reconciliation before allowing
  policy is built;
- a runtime IPv6 prerequisite violation latches the daemon into the host-prerequisite
  isolation path until restart;
- structural verification success is distinct from functional `ProfileResult`;
- a verified zero-path state is committed, yields `ProfileResult=FAIL`, and may run as
  `DEGRADED`;
- successful startup may therefore enter either `ACTIVE` or `DEGRADED`;
- actual apply/verification failures remain hard startup failures or isolation/error paths.

The generic `RouteSpec` still retains `via` and `onlink` because foreign kernel
routes may contain them; daemon-owned desired UNICAST routes do not.

Entry point: `vpn-gatewayd.py`.

The package is under `vpn_gatewayd/`; tests are under `tests/`.

## EXP-009 basis

EXP-009 is `COMPLETE — PASS`.

The live experiment established the implementation boundary used above:

- OpenConnect can expose multiple simultaneous concrete interfaces;
- interface disappearance removes dependent routes and interface return requires route
  rematerialization;
- OpenConnect protected traffic works with a direct `dev vpns00` route without a
  configured transport peer next-hop;
- route metric does not detect a dead path behind a still-present preferred route;
- WireGuard peer selection inside one stable `wg0` is owned by WireGuard
  `AllowedIPs`, not by Linux route next-hop;
- duplicate WireGuard destination prefixes do not create primary/secondary peer routing;
  the last applied peer owns the prefix;
- WireGuard peer health does not automatically transfer that destination ownership.

The resulting RC3 rule is:

```text
VPN-GATE manages concrete VPN interfaces and protected routes.
Transport peer selection remains inside the transport.
```

## Validation

The interface-centric implementation and migrated unit suite were validated on GitHub
Actions with Python 3.13:

```text
python -m compileall -q design/RC3/code/python
PASS

python -m unittest discover -s design/RC3/code/python/tests -p 'test_*.py' -v
Ran 130 tests
OK
130/130 PASS
```

The temporary validation workflow was removed after the successful run; it is not part of
the deployment/runtime architecture.

## Post-simplification cleanup

After removing transport peers and exact `local_address`, the implementation was audited
for migration residue. The following dead layers were removed without changing desired
runtime behavior:

- write-only committed candidate history;
- obsolete `KernelInterface.list_interface_ipv4()` compatibility API and its legacy tests;
- unused route-overlap cache/helper;
- unused daemon `effective_sources()` helper;
- unused `InterfaceSelector.value` and `ProfileInterfaceState.has_active_path`;
- redundant ConfigLoader interface-regex constants;
- duplicate completed-profile-result validation.

When an IPv6 prerequisite violation is latched until restart, periodic isolation
maintenance now runs before interface inventory, avoiding an unnecessary
`ip -j addr show` on every latched pass.

Post-cleanup Python 3.13 validation:

```text
python -m compileall -q design/RC3/code/python
PASS

python -m unittest discover -s design/RC3/code/python/tests -p 'test_*.py' -v
Ran 121 tests
OK
121/121 PASS
```

The reduction from 124 to 121 tests is exactly the removal of three tests for the deleted
legacy `list_interface_ipv4()` API.

## Prefix stable-order and metric allocator implementation

The post-EXP-009 simplification was extended so a newly appearing `prefix+` interface no
longer causes existing binding-specific rules or routes to be reordered merely because its
name sorts earlier.

Verified process-local prefix state now consists of:

```text
active_order
ConcreteBinding(name, ifindex) -> metric
next_metric_cursor
```

A reconciliation snapshot derives provisional order/allocation from the last verified
state and current interface inventory. The order, allocation and cursor are committed only
after successful verification together with OWNED routes and active binding state.

Runtime snapshot projection failure, including metric-slot exhaustion, uses the fail-closed
isolation path and never applies a partial desired state.

Validation on Python 3.13:

```text
python -m compileall -q design/RC3/code/python
PASS

python -m unittest discover -s design/RC3/code/python/tests -p 'test_*.py' -v
Ran 130 tests
OK
130/130 PASS
```

The suite includes regression coverage for stable survivor order, same-name/new-ifindex
fresh bindings, preserved metrics, non-immediate hole reuse, allocator wrap-around,
occupied-slot skipping, allocator exhaustion and explicit-list
`metric < BLACKHOLE_METRIC` validation.

