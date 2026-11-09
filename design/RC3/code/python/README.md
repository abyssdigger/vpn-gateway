# RC3 Python implementation

This directory is the active RC3 implementation line.

It was bootstrapped blob-for-blob from the frozen RC2.5.1 Python baseline in
`design/RC2/code/python/`. RC3 changes are applied here only; the RC2 tree remains a
regression baseline and is not rewritten to match the new architecture.

Current migration status:

- RC2.5.1 package structure preserved as the starting point;
- typed interface selector / inventory / resolution value objects added;
- `VpnProfileConfig.interface` now carries an `InterfaceSelector` value;
- the running ConfigLoader remains exact-selector-only until binding-aware route/policy
  migration, so the legacy RC2 path cannot receive a prefix selector prematurely.

Entry point: `vpn-gatewayd.py`.

The package is under `vpn_gatewayd/`; tests are under `tests/`.
