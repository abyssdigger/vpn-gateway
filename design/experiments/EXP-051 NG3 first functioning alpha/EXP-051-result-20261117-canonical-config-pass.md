# EXP-051 result — canonical Release-1 config regression PASS

**Date:** 2026-11-17  
**Workflow:** NG3 Python run `44128242193`  
**Source commit:** `4a8d2dfd30de5e2f11b2f17eb4bd052b04f2d099`  
**Environment:** Debian 13 systemd container, real OpenVPN 2.6.14

## Scope

This rerun keeps the original EXP-051 runtime/lifecycle topology but changes the installed
alpha configuration to the accepted canonical Release-1 surface:

```toml
[device.ovpn]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false
allow_vpn_client = "udp:11941>198.19.254.2:11940"

[profile.alpha]
enabled = true
direction = "outbound"
destinations = ["10.253.0.1/32"]
device_order = ["ovpn"]
```

The old top-level `[integration.*]` surface is not used by the installed alpha runtime.

The test intentionally keeps `use_outbound_nat = false` and the explicit remote return route
from the original NAT-free alpha topology. This proves grammar/runtime migration without
changing the payload topology being regressed.

## Evidence

```text
EXP051_ALPHA_CONTROLLER_READY=PASS
EXP051_ZERO_PATH_TRANSPORT_ALLOW=PASS
EXP051_VPN_SYSTEMD_NAMESPACE=PASS:pid=4452
EXP051_FIRST_PAYLOAD=PASS
EXP051_FIRST_MANAGER_RECONCILE=PASS
EXP051_MANAGER_RECONCILE_COUNT=PASS:2
EXP051_VPN_ONLY_RESTART_RECONCILED=PASS:old_pid=4452:new_pid=4573:old_ifindex=2:new_ifindex=3
EXP051_STACK_STOP_CLEAN=PASS
EXP051_RESULT=PASS
```

The same workflow also passed all NG3 jobs, including 560 unit tests and the EXP-049/050 real
OpenVPN/systemd integration/lifecycle jobs.

## Verdict

**PASS.**

The first executable alpha can consume the canonical Release-1 Device/Profile grammar for the
capabilities it currently materializes. Device outbound NAT, ordinary Device firewall and
`allow_vpn_client` are wired to existing normalized lower contracts. Canonically parsed
features whose complete alpha lower runtime path is still absent (`availability_check`,
Profile `+snat`, `publish_vpn_server`) are required to fail fast rather than be silently
ignored.
