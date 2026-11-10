# RC3 Python implementation

This directory is the active RC3 implementation line.

It was bootstrapped blob-for-blob from the frozen RC2.5.1 Python baseline in
`design/RC2/code/python/`. RC3 changes are applied here only; the RC2 tree remains a
regression baseline and is not rewritten to match the new architecture.

Current RC3 implementation status:

- RC2.5.1 package structure preserved as the starting point;
- typed interface selector / inventory / resolution value objects added;
- universal cleanup uses selective proto-201/proto-202 route inventory and never reads
  unrelated main-table routes;
- `VpnProfileConfig.interface` now carries an `InterfaceSelector` value;
- pure selector resolution and readiness logic implements `ABSENT`/`BOUND`/`AMBIGUOUS`;
- `SubprocessKernelInterface.list_interfaces()` inventories name/ifindex/IPv4;
- route derivation now uses exact resolved binding names; static `CONFIGURED RouteSpec`
  state has been removed from `VpnProfile`;
- process-local committed state now includes OWNED routes plus binding/readiness;
- pure full/isolation firewall policy derivation is available without orchestration side effects;
- runtime configuration now accepts exact and prefix-family interface selectors;
- immutable `ReconciliationSnapshot` value support is available for daemon integration;
- the kernel adapter exposes the IPv6 host-prerequisite sysctls required by RC3;
- firewall/NAT comparison now classifies confirmed drift as INPUT-only or transit-affecting;
- restore payload generation uses the EXP-006 `iptables-restore --noflush` contract and
  has a dedicated INPUT-only payload that contains no FORWARD operations;
- startup and runtime orchestration consume one immutable reconciliation snapshot;
- policy-changing binding/readiness transitions use isolation -> NAT -> full-filter repair;
- confirmed INPUT-only drift uses narrow repair without disabling forwarding;
- runtime reconciliation is serialized and triggered by NETLINK_ROUTE link/IPv4-address/
  IPv4-route events plus the periodic `reconcile_interval` full resync; Netlink messages
  are wakeup hints only, and ENOBUFS also forces a full reconciliation.
- optional systemd watchdog cadence is derived from `WATCHDOG_USEC`/`WATCHDOG_PID`
  and emitted by the same serialized event loop without changing policy semantics.

Entry point: `vpn-gatewayd.py`.

The package is under `vpn_gatewayd/`; tests are under `tests/`.


## EXP-009.1 architectural impact

EXP-009.1 invalidated the pre-EXP-009 assumption that every managed profile resolves to at
most one concrete runtime interface. The current Python implementation still implements
that older single-binding model.

The architecture now requires:

- selector binding cardinality: `SINGLE | MULTI`;
- exact and `prefix+` as селекторы single-binding;
- `prefix%` and explicit exact set as селекторы multi-binding;
- point-to-point peer evidence in interface inventory;
- `PeerBinding(peer -> exact interface)` for multi-binding route materialization;
- multiple exact INPUT/FORWARD/NAT blocks and peer-specific route interfaces;
- route failback when a desired binding reappears.

Netlink events remain wakeup hints. A route is materialized from the current reconciliation
snapshot: an active concrete binding for a selector single-binding, or a unique
`PeerBinding` for a selector multi-binding.

The OpenConnect negative control in EXP-009.1 also showed that route metrics do not detect
a dead path: with the preferred route still present and winning by metric, disabling
forwarding behind that path did not move traffic to the secondary route.

EXP-009.2 remains pending and will test WireGuard peer failure with stable `wg0`. Until
that experiment is complete, OpenConnect interface-lifecycle evidence is not treated as
proof of WireGuard peer-failure/failover behavior.

Profile-result semantics also changed: a partially available multi-binding profile is
`SUCCESS` when at least one desired UNICAST path per protected destination is materialized
and verified; zero UNICAST paths is `FAIL`/`DEGRADED` even when fail-closed security
state is correct. `SUCCESS` is not an end-to-end connectivity health-check.

References to readiness / `ABSENT` / `BOUND` in the implementation-status bullets above
describe the current pre-EXP-009 code, not the normative post-EXP-009 RC3 domain model.

The 125/125 unit-suite result remains valid for the pre-EXP-009 implementation baseline,
but it is not evidence that the new multi-binding architecture is implemented.
