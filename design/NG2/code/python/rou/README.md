# VPN-GATE NG2 Python reference

Current status: executable NG2 payload semantic control loop, reviewed structural
Linux NetworkRulesAdapter baseline and protective runtime bootstrap gate.

Semantic whole-slice review: **PASS** —
`design/reviews/NG2-2026-11-14-semantic-slice-whole-code-audit.md`.

Linux Adapter focused review: **PASS** —
`design/reviews/NG2-2026-11-14-linux-network-rules-adapter-review.md`.

Linux lower-domain whole-code audit: **PASS** —
`design/reviews/NG2-2026-11-14-linux-lower-domain-whole-code-audit.md`.

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
- concrete structural Linux `NetworkRulesAdapter`:
  - monotonic opaque owner tokens and owner-scoped logical routing domains;
  - staged owner generations committed only after verified physical success;
  - fail-closed projection of absent concrete interface generations;
  - owner-safe filtering composition: NEW flow permissions preserve owner provenance;
  - deterministic Linux table/RPDB/metric allocation with protocol 201/202 ownership tags;
  - per-domain terminal blackhole plus final host-ingress RPDB unreachable guard;
  - numeric-ifindex nft filtering and source NAT;
  - exact route/RPDB/nft/sysctl verification;
  - exact nft table inventory ownership in the dedicated ROU namespace;
  - full structural rebuild behind protective IPv4/IPv6 forwarding closure;
  - exact IPv4-only namespace prerequisites: rp_filter disabled and IPv6 forwarding disabled;
  - best-effort protective close on mutation failure;
  - idempotent per-owner cleanup preserving surviving owners;
- protective runtime bootstrap:
  - closes IPv4 forwarding before exposing the Linux NetworkRulesAdapter;
  - requires fresh readback proving `net.ipv4.ip_forward=0`;
  - leaves stale physical policy closed until the first normal owner reconcile;
  - privileged restart integration starts from stale nft state plus forwarding enabled;
- privileged Linux integration gates:
  - exact apply/renew/cleanup;
  - same-name/new-ifindex detection;
  - sequential multi-owner generation transition;
  - route and foreign-nft drift repair;
  - real `/0` routing domain;
  - live OUTBOUND/BIDIRECTIONAL conntrack behavior;
  - live `EGRESS_ADDRESS` MASQUERADE;
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
- remaining runtime assembly above the protective Linux bootstrap gate;
- persistent technical allocation across daemon restart;
- richer interface-origin dispatch;
- incremental transition optimizer, only after a separate review/evidence unit.

Next implementation boundary: runtime assembly above the reviewed protective Linux
bootstrap gate. Namespace/transport lifecycle and RuntimeStateManager assembly remain
separate review units. Incremental transition optimization remains deferred.

Rootless tests:

```sh
PYTHONPATH=design/NG2/code/python \
python3 -m unittest discover \
    -s design/NG2/code/python/rou/tests \
    -p 'test_*.py' -v
```
