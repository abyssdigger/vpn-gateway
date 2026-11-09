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
