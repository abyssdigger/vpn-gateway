# VPN-GATE NG3 Python reference

Current executable scope is intentionally narrow and split into reviewed units.

Implemented:

- structural Device/Profile TOML normalization;
- canonical IDs, explicit `enabled`, strict IPv4 destinations and selector/quota validation;
- Release 1 inbound/bidirectional configured-capacity validation;
- authoritative `ip -j link show` interface identity parsing;
- concrete endpoint identity as `(ifname, ifindex)`;
- pure stable-slot Device binding projection with bounded waiting-candidate order;
- delayed waiting promotion only after a removal projection can become committed;
- `PayloadProfileRequest` projection, including zero-path Profile preservation;
- outbound/inbound NEW-flow Profile classification with ingress-path restriction;
- bounded availability confirmation state;
- availability-only effective priority transformation with unchanged membership;
- pure make-before-break route-priority move planning for unchanged path membership;
- partial-state route-priority convergence from a fresh observed snapshot, including safe cleanup of already-confirmed duplicate route copies;
- single-attempt route-priority Executor contract with mandatory re-observation after failure and fresh final postcondition verification;
- strict owned route-key inventory projection from current iproute2 JSON and current interface/path identity;
- bounded physical iproute2 route-priority backend with link-sandwiched observation, whole-domain verification and exact add/delete commands;
- Profile-level multi-domain priority coordinator with deterministic domain order and final fresh verification of every destination domain;
- lower Adapter route-priority realization contract for internal table/protocol/path-route identity and validated Linux metric space;
- deterministic shared lower network-policy allocator over injected table/RPDB/route-metric/nft platform resource space;
- accepted EXP-028 Linux platform constants for table/RPDB/protocol/metric/nft namespaces;
- semantic Profile/allocation to per-destination route-priority domain assembly without inferring gateway/onlink semantics;
- explicit opt-in direct-device VPN integration route realizer from verified PathBinding objects;
- complete immutable payload route/RPDB desired-state projection with terminal guards, per-destination path routes and host-boundary dispatch rules;
- strict read-only structural route/RPDB inventory over the entire reserved NG3 table/priority namespaces, with explicit owner-scoped conflicts for unrepresentable reserved objects;
- pure payload actual-vs-desired structural comparison producing confirmed/missing/stale route and RPDB sets without mutation;
- EXP-030-backed managed-netns IPv4 ForwardingGate with write/reread postcondition semantics;
- EXP-031-backed read-only nft table ownership observation using the exact `vpn-gate:ng3:owner-v1` marker and canonical contained-object capture;
- EXP-032-backed pure payload nft scaffold contract/comparison for exact fail-closed FORWARD and empty postrouting NAT base-chain metadata;
- guarded physical payload nft scaffold bootstrap/repair that closes/rechecks the managed-netns ForwardingGate and refuses mutation through conflicts or unclassified nft objects;
- EXP-033-backed normalized Device NAT intent and pure payload masquerade desired projection using exact current boundary/egress InterfaceIdentity values, without selecting external TOML grammar;
- EXP-033-backed read-only authoritative NAT chain observation/comparison classifying exact current, missing, stale and conflicting masquerade rules against the normalized desired state; no NAT rule add/delete or mutation authority;
- EXP-035/036/037/038-backed strict read-only `payload_forward` owner observer for no-counter NEW/RETURN rules across the full IPv4 CIDR prefix-length range, with explicit current-interface-identity vs stale-generation classification; recognized shape is not desired-policy confirmation or mutation authority;
- exact immutable lower `payload_forward` desired rule data plus pure actual-vs-desired comparison yielding confirmed/missing/stale/conflicts; this layer deliberately does not compile Profile direction, most-specific selection or Device envelope semantics;
- bounded guarded NAT-only one-step Executor + Linux nft Driver with exact whole-scope postconditions, strict refusal of foreign/forward-rule objects, verified closed ForwardingGate, and no forwarding activation; this is reference evidence, not the complete structural policy Executor;
- rootless cross-contract structural-pipeline integration scenarios.

Important non-goals of the current reference:

- no Device Engine;
- no Netlink event state/history/replay;
- no general Linux structural route/RPDB/nft policy executor beyond the reviewed pure-priority route-key slice;
- no complete structural NetworkPolicyExecutor for terminal guards, RPDB dispatch and nft payload/probe policy yet;
- no full daemon/lifecycle assembly;
- no production probe execution;
- no final user-facing NAT / traffic-envelope / publication grammar;
- no availability timing grammar.

Those omitted areas remain behind their current architecture/evidence gates and must not be
guessed from historical NG1/NG2 code.

Rootless test command:

```sh
PYTHONPATH=design/NG3/code/python \
python3 -m unittest discover \
    -s design/NG3/code/python/rou/tests \
    -p 'test_*.py' -v
```

Code reviews for each unit are stored under `design/reviews/`.


GitHub CI additionally runs privileged disposable-network-namespace integrations for the
physical route-priority backend and the managed-netns forwarding gate. That integration exercises real iproute2 add/delete,
make-before-break priority movement and recovery from an already materialized duplicate
route state.
