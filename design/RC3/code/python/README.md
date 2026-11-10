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

Deterministic active ordering:

- exact selector: one active interface;
- prefix selector: current active exact names in case-sensitive bytewise ASCII order;
- explicit list: configured order filtered to active elements.

The same order drives direct routes and binding-specific firewall/NAT materialization.

Routing:

- one `proto 201 metric 65536` BLACKHOLE remains required for every protected
  destination;
- daemon-owned UNICAST routes are direct interface routes:
  `dev <exact-interface> proto 202 metric <N>`;
- desired UNICAST uses `via=None` and `onlink=False`;
- exact metric is 10;
- prefix metrics are 10,20,30... over the current sorted active set;
- explicit-list metrics use stable configuration slots, so a missing earlier interface
  does not renumber later interfaces;
- prefix metric overflow is checked at runtime without wrap/truncation.

Firewall/NAT:

- selector wildcards appear only in deny-only guards;
- allowing INPUT/FORWARD blocks and MASQUERADE rules use exact active interface names;
- all simultaneous active interfaces of a profile are materialized;
- policy-changing active-binding transitions use the verified protective barrier:
  isolation filter -> NAT -> full filter -> routes;
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
Ran 121 tests
OK
121/121 PASS
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

