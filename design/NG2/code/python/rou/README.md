# VPN-GATE NG2 Python reference

Current status: routing/dispatch plus effective payload-filtering contract slice.

Implemented:

- generic network-rules routing/dispatch data contract;
- canonical generation-aware `InterfaceIdentity` in a neutral cross-domain module;
- semantic `LOCAL_NETWORK` endpoint instead of leaking the infrastructure `host0` name;
- Direct `NetworkRulesAdapter` protocol with opaque caller-instance ownership:
  - `apply(owner, spec)`;
  - `renew_state(owner)`;
  - `get_last_state(owner)`;
  - idempotent `cleanup(owner)` is part of the contract;
- explicit known/unknown Adapter state contract;
- zero-path routing domain as semantic `DROP` fail-close intent;
- allow-only filtering contract:
  - `traffic_allows` describes effective byte-level permission;
  - `flow_initiation_allows` additionally describes which permitted traffic may create a
    new stateful flow;
  - conntrack / established-related realization is intentionally below the Adapter boundary;
- `PayloadRulesCalculator` routing/filtering slice:
  - Profile -> logical routing domain;
  - ordered generation-aware paths;
  - longest-prefix-first dispatch;
  - duplicate-destination ambiguity rejection;
  - Profile direction resolved before the Adapter;
  - payload-domain selector/protocol/port types are explicitly converted to network-rules
    types;
  - Device traffic-envelope first-match/default policy resolved to effective predicates
    before the Adapter;
  - more-specific Profile destinations exclude broader allows so overlapping Profiles do
    not widen each other's policy.

Not implemented yet:

- NAT contract and NAT slice of `PayloadRulesCalculator`;
- Linux `NetworkRulesAdapter` implementation;
- owner-composition backend materialization;
- Drivers and transition/materialization logic.

Rootless tests:

```sh
PYTHONPATH=design/NG2/code/python \
python3 -m unittest discover \
    -s design/NG2/code/python/rou/tests \
    -p 'test_*.py' -v
```
