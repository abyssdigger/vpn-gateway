# VPN-GATE NG3 Python reference

Current executable scope is intentionally narrow.

Implemented review units:

- structural Device/Profile TOML parsing;
- canonical IDs and explicit `enabled`;
- exact/prefix `expected_interfaces` selectors and quotas;
- strict IPv4 destinations;
- Device references and active Device derivation;
- selector/destination ambiguity rejection;
- Release 1 inbound/bidirectional configured-capacity validation;
- immutable structural normalized values.

Also implemented:

- pure stable-slot Device binding projection from fresh ordered interface inventory;
- concrete current interface identity as `(ifname, ifindex)`;
- logical path identity as Device/selector/stable-slot;
- survivor preservation and bounded waiting-candidate order;
- delayed promotion: a slot freed by disappearance is reusable only on a later reconciliation
  after the removal projection has been committed;
- same-name/new-ifindex treated as a fresh endpoint;
- no Device Engine, Netlink event state, history/replay or kernel mutation in this slice.

Not yet implemented in the user-facing parser:

- final NAT spelling;
- traffic-envelope grammar;
- publication grammar;
- availability-check/timing grammar.

Those fields are deliberately not guessed from historical prototypes.

Rootless tests:

```sh
PYTHONPATH=design/NG3/code/python \
python3 -m unittest discover \
    -s design/NG3/code/python/rou/tests \
    -p 'test_*.py' -v
```
