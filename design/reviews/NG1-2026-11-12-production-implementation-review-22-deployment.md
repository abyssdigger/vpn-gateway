# Production implementation review 22 — deployment, lifecycle and systemd

Date: 2026-11-12

Role: external expert review focused on systemd lifecycle, namespace ownership, hardening,
shutdown behavior, configuration/deployment consistency and Rust migration.

## Scope

Reviewed:

- instance bootstrap/ensure/contain/destroy;
- CLI prepare/contain/up/down/show/run surfaces;
- wrapper and installer;
- `rouvpn@.service`;
- production nft migration assumptions.

## Findings

### F1 — instance bootstrap still installed legacy iptables state

Severity: HIGH.

Although Planner/runtime/status had migrated to nftables, `instance_lifecycle.py` still
installed and verified a legacy iptables fail-closed filter during create/ensure.

That reintroduced a second production packet-policy backend on every service restart and
could leave traffic double-filtered outside nft verification.

Disposition: fixed. Instance create/ensure now installs empty owned nft NAT plus fail-closed
owned nft filter, removes foreign nft tables while forwarding is closed, and
`verify_instance()` checks nft INPUT/FORWARD/OUTPUT base-chain DROP policies.

### F2 — systemd stop timeout was shorter than a legal runtime audit wait

Severity: medium/high lifecycle robustness.

Runtime may block in event wait for up to 30 seconds. `TimeoutStopSec=15s` could force
SIGKILL before graceful publication/event/runtime teardown.

Disposition: fixed by increasing `TimeoutStopSec` to 45 seconds, providing margin above
the configured maximum audit wait.

### F3 — --instance-file with rou up/down disagreed with systemd template configuration

Severity: high configuration ownership.

The CLI could parse an override instance file for `rou up`, but the started
`rouvpn@<id>.service` always invokes `rou prepare/run <id>` using the conventional
instance path. This could validate/create one appliance while systemd runs another config.

Disposition: fixed. Systemd-owned `up/down` reject a non-conventional instance-file
override. Overrides remain useful for non-systemd administrative/test commands.

### F4 — router_config accepted paths outside the hardened production configuration root

Severity: medium deployment consistency.

The schema accepted any absolute router path, while the production unit uses
`ProtectHome=yes` and the installer provides `/etc/vpn-gateway/routers`. A config under
a protected home directory could therefore parse successfully but be unreadable by the
service.

Disposition: fixed. Schema version 1 requires router_config below
`/etc/vpn-gateway/routers`; state_file already requires
`/var/lib/vpn-gateway`.

### F5 — installer did not state production command dependencies and copied tests

Severity: low maintenance/deployment.

Disposition: fixed. Installer checks python3/ip/nft/sysctl/systemctl and omits the test
subtree from the installed Python package.

## Systemd hardening assessment

Current choices are coherent with the required privileged operations:

- root service;
- CAP_NET_ADMIN for route/nft/sysctl operations;
- CAP_SYS_ADMIN is presently required by `ip netns exec`/setns and namespace bootstrap;
- CAP_NET_BIND_SERVICE is required because publications allow privileged ports;
- NoNewPrivileges, ProtectSystem=strict, ProtectHome, PrivateTmp,
  ProtectKernelLogs/Modules, LockPersonality, MemoryDenyWriteExecute and RestrictSUIDSGID
  are compatible with the Python design;
- ProtectKernelTunables is intentionally not enabled because the service owns namespace
  sysctls;
- `/run` remains writable because iproute2 netns lifecycle uses `/run/netns`; narrowing
  this safely would require a separate systemd live experiment and is not needed for the
  first baseline.

## Lifecycle assessment

The split is appropriate:

- `rou up` ensures the appliance then enables/starts the template service;
- ExecStartPre `rou prepare` is intentionally idempotent so enabled services can recreate
  volatile network namespaces after reboot;
- `rou run` itself never adopts/creates infrastructure;
- ExecStopPost `rou contain` closes forwarding even after failed start/runtime exit;
- `rou down` proves the service inactive before deleting namespace/veth state.

## Rust-alignment review

Deployment commands remain thin adapters over normalized lifecycle/runtime objects.
No systemd-specific semantics leak into Planner/DeviceEngine/TrafficEngine.

## Verdict

Approved after F1–F5 corrections.

Remaining evidence requirement: the disposable production-cycle integration must pass on
the production nft backend. A real systemd-as-PID1 deployment smoke on the target Debian
host remains desirable before packaging/release, but it does not block further code work.
