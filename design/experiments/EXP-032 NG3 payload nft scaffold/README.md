# EXP-032 — NG3 payload nft scaffold

## Purpose

Validate the invariant payload nft scaffold selected for Release 1:

```text
table ip vpn_gate
comment "vpn-gate:ng3:owner-v1"

chain payload_forward
    type filter
    hook forward
    priority 0
    policy drop
    comment "vpn-gate:ng3:payload-forward-v1"

chain payload_postrouting
    type nat
    hook postrouting
    priority 100
    policy accept
    comment "vpn-gate:ng3:payload-postrouting-v1"
```

The experiment does not define final Profile allow rules or Device NAT rules.

## Hypotheses

- **H1:** both chain shapes are accepted by current nftables;
- **H2:** type/hook/priority/policy/comment round-trip through JSON;
- **H3:** an empty `payload_forward policy drop` blocks real forwarded traffic;
- **H4:** foreign unconditional-accept FORWARD base chains both before and after priority 0
  do not bypass the VPN-GATE drop;
- **H5:** explicit VPN-GATE accept rules can permit the tested forwarding path;
- **H6:** the empty postrouting chain contains no NAT rule and therefore introduces no NAT
  policy by itself.

## Topology

A disposable three-namespace routed topology is used. The middle namespace has forwarding
enabled so nft FORWARD behavior, rather than the root sysctl barrier, is under test.

## Safety

All network and nft state exists only in disposable namespaces.

## Acceptance

All hypotheses must pass in privileged GitHub CI before the scaffold metadata becomes
executable lower policy.
