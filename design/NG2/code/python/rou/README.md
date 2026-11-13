# VPN-GATE NG2 Python reference

Current status: first executable NG2 contract slice.

Implemented:

- generic network-rules routing/dispatch data contract;
- generation-aware concrete interface references;
- caller-owned `NetworkRulesScope` kept outside `NetworkRulesSpec`;
- Direct `NetworkRulesAdapter` protocol:
  - `apply(scope, spec)`;
  - `renew_state(scope)`;
  - `get_last_state(scope)`;
- explicit known/unknown Adapter state contract;
- zero-path routing domain as valid fail-closed intent.

Not implemented yet:

- packet filtering contract;
- NAT contract;
- payload-to-network `PayloadRulesCalculator`;
- Linux `NetworkRulesAdapter` implementation;
- Drivers and transition/materialization logic.

Rootless tests:

```sh
PYTHONPATH=design/NG2/code/python \
python3 -m unittest discover \
    -s design/NG2/code/python/rou/tests \
    -p 'test_*.py' -v
```
