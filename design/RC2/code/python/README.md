# RC2 Python implementation

This directory is a mechanical decomposition of the RC2.5.1 Python monolith.

No gateway policy, lifecycle ordering, route/firewall semantics, configuration
semantics, or ownership marker values are intentionally changed by this split.

Entry point: `vpn-gatewayd.py`.

The package is under `vpn_gatewayd/`; tests are under `tests/`.
`tests/verify-split.py` compares top-level class/function ASTs and simple
top-level assignments against the pre-split monolith.
