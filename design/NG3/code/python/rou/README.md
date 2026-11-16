# VPN-GATE NG3 Python reference

Current executable scope is intentionally narrow.

Implemented review unit:

- structural Device/Profile TOML parsing;
- canonical IDs and explicit `enabled`;
- exact/prefix `expected_interfaces` selectors and quotas;
- strict IPv4 destinations;
- Device references and active Device derivation;
- selector/destination ambiguity rejection;
- Release 1 inbound/bidirectional configured-capacity validation;
- immutable structural normalized values.

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
