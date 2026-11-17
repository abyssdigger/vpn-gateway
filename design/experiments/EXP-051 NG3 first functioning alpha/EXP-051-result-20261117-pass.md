# EXP-051 result — first functioning NG3 alpha PASS

**Date:** 2026-11-17  
**Verdict:** **PASS**  
**Runtime evidence commit:** `5a1a9f53c8d861e9a616cf18bfa7107764f4a38d`  
**GitHub Actions run:** `44082595411`  
**Alpha smoke job:** `134036710197`  
**Target userspace:** Debian GNU/Linux 13 with real systemd PID 1  
**VPN:** OpenVPN 2.6.x package from Debian 13

## What was tested

EXP-051 no longer invokes the controller assembly directly as an experiment-only object.

It installs and starts the actual alpha deployment surface:

```text
/usr/lib/vpn-gate-alpha/rou
/etc/systemd/system/vpn-gate-alpha.service
/etc/systemd/system/vpn-gate-alpha-openvpn.service
/etc/vpn-gate-alpha/config.toml
/etc/vpn-gate-alpha/openvpn.conf
```

The controller is started with:

```text
systemctl start vpn-gate-alpha.service
```

and the VPN independently with:

```text
systemctl start vpn-gate-alpha-openvpn.service
```

The stack-specific VPN service uses:

```ini
BindsTo=vpn-gate-alpha.service
After=vpn-gate-alpha.service
NetworkNamespacePath=/run/netns/vpn-gate-alpha
```

The controller service uses `Type=notify`; its start completes only after
`start_controller_once(...)` has established/verified the managed domain and the initial
fail-closed policy.

## Configuration used

The test uses only already accepted external grammar:

- one enabled Device expecting `vpn0`;
- one outbound Profile for `10.253.0.1/32`;
- one explicit `integration.*` transport contract:
  - UDP;
  - remote `198.19.254.2:11940`;
  - stable local port `11941`.

The postponed final Device NAT/firewall/publication grammar is not guessed.

For this first alpha runtime the lower normalized inputs are:

```text
Device NAT       = NatIntent.NONE
Device firewall  = omitted/permissive
publication      = none
```

The disposable remote test namespace has an explicit return route for host source traffic, so
the smoke does not depend on source NAT.

## Initial zero-path start

Before OpenVPN is started, the controller reaches READY with no current VPN path.

The initial policy is fail-closed for payload while already containing the exact integration
transport contribution needed for the later VPN process to establish.

Evidence marker:

`EXP051_ZERO_PATH_TRANSPORT_ALLOW=PASS`

This proves that VPN process presence is not required for controller startup and that starting
the VPN later does not require a broad local allow.

## VPN systemd placement

After the controller READY notification:

```text
systemctl start vpn-gate-alpha-openvpn.service
```

starts the real OpenVPN MainPID inside the already existing managed namespace.

Evidence:

`EXP051_VPN_SYSTEMD_NAMESPACE=PASS:pid=4449`

`vpn0` is created by that process inside the managed domain.

## First live reconciliation

The controller is **not restarted** after `vpn0` appears.

The new local runtime reconciliation loop:

1. freshly observes the managed-domain link inventory;
2. projects the current Device binding from retained semantic `DeviceBindingState`;
3. builds current Profile/path/routing/nft desired state;
4. observes actual lower policy;
5. if drift exists, enters the existing guarded `activate_network_policy(...)` boundary;
6. closes forwarding before mutation;
7. converges from fresh authoritative state;
8. verifies the exact result.

The first appearance of `vpn0` produced an actual production reconciliation marker:

`EXP051_FIRST_MANAGER_RECONCILE=PASS`

After it, controlled host payload reached the remote TUN endpoint:

`EXP051_FIRST_PAYLOAD=PASS`

## VPN-only restart

Only the VPN service was restarted:

`systemctl restart vpn-gate-alpha-openvpn.service`

The controller process remained alive.

Observed concrete generation change:

```text
old OpenVPN PID  = 4449
new OpenVPN PID  = 4565

old vpn0 ifindex = 2
new vpn0 ifindex = 3
```

The new endpoint generation was not treated as the old binding. The controller's periodic
fresh audit detected/rebound/reconciled it and payload recovered without controller restart.

Evidence:

```text
EXP051_MANAGER_RECONCILE_COUNT=PASS:2
EXP051_VPN_ONLY_RESTART_RECONCILED=PASS:
    old_pid=4449
    new_pid=4565
    old_ifindex=2
    new_ifindex=3
```

The two counted production `status=reconciled` markers correspond to:

1. first VPN endpoint appearance;
2. VPN-only restart / fresh endpoint generation.

## Stack stop

Stopping the controller service:

`systemctl stop vpn-gate-alpha.service`

cleanly stops the bound VPN service via systemd dependency ordering, then allows controller
owned-domain cleanup to complete.

The smoke confirms:

- VPN unit inactive;
- previous VPN PID absent;
- `/run/netns/vpn-gate-alpha` absent;
- host boundary `vnga-host0` absent.

Evidence:

`EXP051_STACK_STOP_CLEAN=PASS`

## Full alpha result

```text
EXP051_ALPHA_CONTROLLER_READY=PASS
EXP051_ZERO_PATH_TRANSPORT_ALLOW=PASS
EXP051_VPN_SYSTEMD_NAMESPACE=PASS:pid=4449
EXP051_FIRST_PAYLOAD=PASS
EXP051_FIRST_MANAGER_RECONCILE=PASS
EXP051_MANAGER_RECONCILE_COUNT=PASS:2
EXP051_VPN_ONLY_RESTART_RECONCILED=PASS:old_pid=4449:new_pid=4565:old_ifindex=2:new_ifindex=3
EXP051_STACK_STOP_CLEAN=PASS
EXP051_RESULT=PASS
```

## What this PASS means

The project now has a first installed, functioning NG3 alpha in which the accepted pieces
operate together rather than only as isolated lower slices:

```text
real config file
    ->
real systemd controller
    ->
managed netns
    ->
zero-path fail-closed policy
    ->
separate real OpenVPN systemd service
    ->
real vpn0 appears
    ->
ongoing controller observes/binds/reconciles it
    ->
controlled payload passes
    ->
VPN-only restart creates fresh endpoint generation
    ->
ongoing controller reconciles again
    ->
payload recovers
    ->
systemd stack stop cleans VPN + managed domain
```

## What this PASS does not mean

This is not yet a complete Release-1 implementation.

Still outside this first alpha end-to-end assembly:

- final human-facing Device NAT grammar;
- final human-facing Device firewall/publication grammar;
- Device NAT other than the current alpha `NONE` slice;
- config hot reload;
- RuntimeStatusAgent presentation;
- complete availability/probing/failover runtime assembly;
- all supported VPN technologies;
- production packaging/versioning/install lifecycle.

Those gaps must be closed by their existing accepted requirement paths rather than by extending
the EXP-051 result beyond what it proves.

## Final verdict

**PASS — the first NG3 alpha actually runs as an installed systemd stack and carries real
payload through an independently managed OpenVPN service, including VPN-only endpoint
replacement and live policy reconciliation.**
