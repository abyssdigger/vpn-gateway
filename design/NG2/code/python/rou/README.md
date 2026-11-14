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
- Adapter-internal `DesiredRulesByOwner` registry keyed strictly by caller object identity,
  with explicit-lifetime strong ownership and no semantic owner names/priorities;
- multidimensional `PayloadRulesState`:
  - knowledge;
  - convergence;
  - safety;
  - service;
- conservative `PayloadRulesStateCalculator`:
  - stale/unknown observation -> unknown axes;
  - exact active rules -> matched/safe/ready;
  - exact zero-path rules -> matched/safe/isolated;
  - exact mixed active/zero-path rules -> matched/safe/degraded;
  - divergent proven isolation -> safe/isolated;
  - conservative path/allow removal can prove SAFE without guessing service;
  - new byte-level permission on an unapproved endpoint pair can prove UNSAFE;
  - semantic equality ignores ordering of unordered rule collections;
- `PayloadTrafficStateInfo` payload:
  - aggregate `PayloadRulesState`;
  - requested Profiles only;
  - per-Profile `observed_paths` facts;
  - unknown rules knowledge suppresses current path claims;
  - raw `NetworkRulesState` never crosses the event boundary;
- executable `PayloadTrafficManager` request/audit control loop:
  - pure request->desired calculation before accepting current intent;
  - `NetworkRulesAdapter` is always called with owner=`self`;
  - apply/refresh failures are interpreted only through observed state;
  - current payload state is published only through Event Delivery Environment port;
  - semantically unchanged InfoEvents are suppressed;
  - `audit()` refreshes current state and repairs only when convergence is not MATCHED;
  - MATCHED zero-path isolation is not mistaken for drift;
  - successful repair can suppress transient drift history while failed/recovered states
    publish real current-state transitions;
  - shutdown delegates idempotent Adapter cleanup for the same owner identity;
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
    not widen each other's policy;
  - `PayloadNatMode.MASQUERADE` maps to semantic `EGRESS_ADDRESS` source translation;
  - broad source-NAT intents exclude more-specific Profile destinations.

Not implemented yet:

- richer predicate implication only where future use justifies it;
- RuntimeStateManager Profile-state mapping;
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
