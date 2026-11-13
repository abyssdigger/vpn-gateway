# EXP-023 — NG1 real OpenConnect Profile-binding probe plane

**Status:** READY FOR TARGET RUN  
**Architecture baseline:** NG1 Profile-binding availability/control + EXP-022 PASS  
**Type:** real dual-OpenConnect path / isolated availability-condition validation

## Purpose

Validate the EXP-022 control-plane primitive against two real OpenConnect bindings that can
both reach the same remote endpoint.

This experiment does **not** redefine availability as ping. It validates one active
availability condition on a production-like VPN path.

## Required topology

The server has two simultaneously bound OpenConnect interfaces:

```text
             real OC path A
server vpnsA ==============> remote client A ----> endpoint
       |
       |     real OC path B
       + vpnsB ==============> remote client B ----> endpoint
```

Both paths must initially reach the same IPv4 endpoint.

The script may identify the two interfaces either by interface name or by their fixed
OpenConnect peer IPv4 addresses.

## What is being proved

1. both real OC bindings can initially reach the endpoint;
2. a dedicated probe table plus
   `uidrange + ipproto + to + oif` rule selects only the primary binding;
3. a data-path-only failure behind the primary OpenConnect client makes the primary
   condition fail without terminating the OC session or removing the server-side binding;
4. the secondary OC binding remains able to reach the same endpoint;
5. the primary probe therefore does not escape through the alternate OC path;
6. removing the failure restores the primary condition on the same server-side
   `(ifname,ifindex)` binding.

EXP-021/022 already prove the unprivileged ping and narrow nft mechanisms. EXP-023 does not
modify production firewall policy; it focuses on the real OpenConnect path.

## Running

Generic form:

```sh
sudo ./exp-023-real-openconnect-probe-plane.sh \
    --primary-peer <primary-vpn-peer-ip> \
    --secondary-peer <secondary-vpn-peer-ip> \
    --target <remote-endpoint-ip>
```

Interface names may be supplied directly instead:

```sh
sudo ./exp-023-real-openconnect-probe-plane.sh \
    --primary-if vpns00 \
    --secondary-if vpns01 \
    --target <remote-endpoint-ip>
```

The script uses only a temporary local RPDB rule and routing table and removes them on exit.

## Creating the outage

When instructed by the harness, on **remote client A only** insert a temporary forwarding
DROP for the endpoint while leaving OpenConnect running:

```sh
sudo iptables -I FORWARD 1 -d <remote-endpoint-ip>/32 \
    -m comment --comment VPNG-EXP023 -j DROP
```

Later remove the same rule:

```sh
sudo iptables -D FORWARD -d <remote-endpoint-ip>/32 \
    -m comment --comment VPNG-EXP023 -j DROP
```

If the experiment is interrupted while the DROP is active, remove that remote rule
manually.

This intentionally breaks only endpoint payload through one VPN client. It avoids turning
the test into ordinary OpenConnect process/interface lifecycle.

## Diagnostics rule

Every command-derived assertion that stops the experiment prints the assertion first and
then the captured raw return code/stdout/stderr. This is the required pattern for future
VPN-GATE experiment harnesses.

## Decision boundary

A PASS validates the real OpenConnect use of the already-proven isolated probe plane. It
does not yet choose:

- configuration grammar;
- probe cadence, timeout or hysteresis;
- general condition composition;
- manual inhibit/schedule APIs.
