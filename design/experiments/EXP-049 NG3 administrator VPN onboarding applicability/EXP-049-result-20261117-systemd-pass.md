# EXP-049 result — systemd OpenVPN onboarding PASS

**Date:** 2026-11-17  
**Verdict:** **PASS**  
**Evidence commit:** `d3ceaa43b9a74ab7329f2b13f2e9af1af6627216`  
**GitHub Actions run:** `44069971041`  
**Target userspace:** Debian GNU/Linux 13.7  
**VPN:** OpenVPN 2.6.14

## Supported onboarding mechanism

The passing mechanism is the first-release administrator/systemd contract:

```text
managed network namespace exists
    ->
distinct stack-specific OpenVPN systemd service
    BindsTo = managed-domain lifecycle anchor
    After = managed-domain lifecycle anchor
    NetworkNamespacePath = /run/netns/<managed>
    ->
OpenVPN MainPID starts inside managed namespace
    ->
OpenVPN creates vpn0 there
```

The OpenVPN client configuration is policy-neutral with respect to VPN-GATE routing and uses
`route-noexec`.

The administrator-facing VPN-GATE integration facts provide the exact remote protocol/address
and port needed by the integration-local policy.

## Production local transport admission

The successful run materializes only:

```text
stack_output:
    current host-boundary
    exact managed local IPv4
    exact OpenVPN server IPv4
    udp dport 11940
    accept

stack_input:
    current host-boundary
    exact OpenVPN server IPv4
    exact managed local IPv4
    udp sport 11940
    ct state established,related
    accept
```

Owner marker:

`vpn-gate:ng3:local-integration-v1`

Unrelated ICMP underlay traffic remains blocked after activation.

## Two clean cycles

Both clean cycles proved:

```text
systemd domain lifecycle anchor active                PASS
VPN endpoint initially absent                         PASS
underlay reachable before local policy                PASS
OpenVPN MainPID in managed network namespace          PASS
real vpn0 created in managed domain                   PASS
fresh exact LogicalPathId -> InterfaceIdentity        PASS
production policy activation                          PASS
controlled host payload through admitted vpn0         PASS
unrelated local ICMP underlay after activation        BLOCKED
systemctl stop OpenVPN                                PASS
vpn0 absent after service stop                        PASS
controller/domain cleanup                             PASS
managed namespace + host boundary absent              PASS
```

The second cycle used a distinct OpenVPN MainPID and a newly created clean managed domain.

## Superseded failure

`EXP-049-result-20261117.md` remains retained as historical evidence.

That run established the original defect: a real OpenVPN endpoint could be placed and bound,
but terminal local INPUT/OUTPUT DROP killed its transport because the concrete integration
allow owner class did not yet exist.

The current PASS does not erase that finding; it demonstrates the reviewed repair.

## Scope of the PASS

This evidence accepts:

- OpenVPN 2.6.14;
- process creation by systemd directly inside the managed network namespace;
- the tested policy-neutral OpenVPN configuration shape;
- explicit bounded integration transport facts;
- current NG3 discovery/binding/network-policy activation.

It does not automatically prove WireGuard, OpenConnect or arbitrary vendor helpers equivalent.

## Dependency consequence

This PASS satisfies the prerequisite for EXP-050 only when EXP-050 uses this same
OpenVPN/systemd onboarding mechanism.
