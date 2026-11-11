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
- reserved metric tail with `normal < UNAVAILABLE_METRIC < BLACKHOLE_METRIC`.

Intentionally not implemented yet:

- publication TOML syntax;
- traffic-envelope TOML syntax;
- DeviceEngine runtime discovery/binding;
- TrafficEngine stable live-interface slot state;
- PlannerEngine transitions;
- kernel apply/verify;
- unavailable direct-dev multipath materialization pending its live experiment.

Run rootless tests:

```sh
python3 -m compileall -q design/NG1/code/python/rou
python3 -m unittest discover -s design/NG1/code/python/rou/tests -p 'test_*.py' -v
```
