# NG2 payload/probing decoupling — pre-test metrics

Measured before CI/testing, relative to cycle base
`ccfb625cbe7d60274991c920bd960f91f4cbec5a`.

```text
production Python: +347 / -376  => net -29 lines
tests/contracts:   +252 / -261  => net  -9 lines
production files changed: 9
test/integration files changed: 13
new production modules: 0
removed production modules: 0
```

PayloadTrafficManager itself changed by `+174 / -234` => net **-60 lines**.

Structural results before testing:

- `PayloadProfileRequest` no longer carries an availability-derived prefix;
- PayloadTrafficManager no longer imports probe_rules/probe_transport;
- payload availability input is a probe-independent priority-channel contract;
- probe cadence and payload hysteresis are separate;
- inactive availability emits no lower routing prefix hint;
- lower routing hint is named neutrally as `preferred_prefix_length`.

This file records the requested quantitative checkpoint before test execution; it is not
payload architecture documentation.
