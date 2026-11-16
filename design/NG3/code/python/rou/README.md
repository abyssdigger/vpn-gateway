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
- rootless cross-contract structural-pipeline integration scenarios.

Important non-goals of the current reference:

- no Device Engine;
- no Netlink event state/history/replay;
- no general Linux structural route/RPDB/nft policy executor beyond the reviewed pure-priority route-key slice;
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


GitHub CI additionally runs a privileged disposable-network-namespace integration for the
physical route-priority backend. That integration exercises real iproute2 add/delete,
make-before-break priority movement and recovery from an already materialized duplicate
route state.
