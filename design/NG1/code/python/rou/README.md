# VPN-GATE NG1 ROU production reference

This directory starts the first production-capable NG1 implementation after ROU v0 / EXP-012.

Current implemented slice:

- immutable Device/Profile/ExpectedInterface domain objects;
- TOML -> `ActiveConfig` parsing for the agreed config surface;
- disabled placeholder semantics;
- strict IPv4 destination validation;
- Device reference and selector-overlap validation;
- ordered `device_order -> expected_interfaces` metric-range compilation;
- disabled Devices consume no current metric range;
- reserved metric tail with `normal < UNAVAILABLE_METRIC < BLACKHOLE_METRIC`;
- rootless DeviceEngine binding projection over fresh ordered interface snapshots;
- stable `(ifname, ifindex)` identity and survivor-preserving per-selector quota admission;
- observable over-quota candidates that are not exported as bound TrafficEngine inputs;
- normalized UNKNOWN/AVAILABLE/UNAVAILABLE availability attached to bound interfaces;
- TrafficRuntimeState projection for stable Profile-local normal metric slots;
- verified-removal barrier: a disappeared interface's committed metric is not reused until a later verified commit;
- strict parser for ordered `ip -j link show` interface observations;
- Profile destination dispatch projection in normative `prefixlen DESC, network ASC` order;
- Device→host NEW-flow Profile classification with filter-by-Device first, then longest-prefix match;
- explicit ACCEPT-or-DROP NEW-flow intent for every enabled Profile/Device/prefix pair;
- longest-prefix-first NEW verdict ordering that prevents broader overlapping Profiles from bypassing a more-specific deny;
- kernel-independent per-Profile direct-route intent for UNKNOWN/AVAILABLE normal-tier paths;
- terminal Profile blackhole intent even when no usable path exists;
- persistent shadow fallback route intent at `UNAVAILABLE_METRIC` for every bound Profile path;
- UNKNOWN/AVAILABLE keep normal routes while UNAVAILABLE removes only the normal route;
- one-member direct fallback and multi-member equal-cost fallback are represented explicitly;
- terminal Profile blackhole remains below the fallback tier.

The current runtime code is deliberately a pure projection layer. It does not mutate kernel
state and therefore cannot accidentally bypass the architecture's
`observe -> plan -> apply -> fresh observe -> verify -> commit` boundary.

Intentionally not implemented yet:

- publication TOML syntax;
- traffic-envelope TOML syntax;
- live subprocess/netlink EnvironmentSnapshot collection;
- publication supervision in the production package;
- numeric routing-table/RPDB allocation in production code;
- PlannerEngine transition execution;
- routing/RPDB/firewall/NAT kernel apply/verify;
- kernel materialization of the now-approved shadow fallback route intent.

Run rootless tests:

```sh
python3 -m compileall -q design/NG1/code/python/rou
python3 -m unittest discover -s design/NG1/code/python/rou/tests -p 'test_*.py' -v
```
