# EXP-053 — NG3 host-side return steering from managed stack

## Status

PREPARED — evidence pending.

## Purpose

This experiment tests whether the ordinary host can remember that a connection arrived from
the managed VPN-GATE stack and use that connection state to steer the reply back through the
stack, without installing a destination-specific host route for the remote prefix.

The result is intentionally useful in both directions:

- PASS permits host bootstrap routes to be required only for ordinary-side initiation
  (outbound/bidirectional Profiles);
- FAIL leaves the conservative OpenVPN/WireGuard-style host route model available for both
  initiation and return traffic.

This is a host/managed-domain boundary experiment. It does not test multi-path selection
inside the managed namespace and does not replace historical EXP-014.

## Question

Given a remote-initiated connection that enters the host through the dedicated VPN-GATE
host/stack boundary, can Linux:

1. stamp the conntrack entry at ingress;
2. restore that stamp to packet mark on the reverse direction;
3. use RPDB policy routing to send the reply through the managed stack;
4. do so both for forwarded replies and host-local replies;
5. avoid any destination-specific route for the remote prefix in the host main table?

## Topology

```text
remote namespace
  203.0.113.2/24
        |
        | 203.0.113.0/24
        |
managed-stack namespace
  203.0.113.1
  192.0.2.2
        |
        | explicit VPN-GATE host boundary
        |
host namespace
  192.0.2.1
  10.0.0.1
        |
        | ordinary LAN
        |
lan namespace
  10.0.0.2
```

The host main table deliberately has only an ordinary default route through the LAN side.
It has no route for `203.0.113.0/24` through the managed stack.

A dedicated policy table contains only:

```text
default via 192.0.2.2 dev <host-stack-boundary>
```

selected by:

```text
ip rule fwmark 0x53 lookup 1053
```

## Mechanism under test

Host nftables state:

```text
prerouting:
    packets entering from managed stack:
        ct mark set 0x53

    packets not entering from managed stack and belonging to ct mark 0x53:
        meta mark set ct mark

output, type route:
    packets belonging to ct mark 0x53:
        meta mark set ct mark
```

The output hook is a `type route` chain so a mark change can trigger route re-evaluation for
host-local replies.

## Hypotheses

### H1 — route precondition

Before any flow starts:

- ordinary host lookup for `203.0.113.2` resolves through the ordinary LAN default;
- lookup with mark `0x53` resolves through the managed-stack boundary.

This proves that success cannot be explained by a hidden main-table route to the remote prefix.

### H2 — forwarded reply

A TCP connection initiated by the remote namespace to a listener in the LAN namespace
(`10.0.0.2`) succeeds bidirectionally.

The first packet enters the host from the managed stack, obtains conntrack mark `0x53`, and
is forwarded to the directly connected LAN. The LAN reply re-enters the host from the ordinary
side, restores the mark in PREROUTING, and RPDB sends it through the managed stack.

No host main-table route for `203.0.113.0/24` is permitted.

### H3 — host-local reply

A TCP connection initiated by the remote namespace to a listener on the host boundary address
(`192.0.2.1`) succeeds bidirectionally.

The reply is generated locally, restores `ct mark` to `meta mark` in an nft `type route`
OUTPUT chain, and is rerouted through the marked RPDB table.

### H4 — ownership remains narrow

The experiment does not replace the host main default route and does not install a
destination-specific host route for the remote prefix.

## Procedure

Run:

```sh
sudo python3 "design/experiments/EXP-053 NG3 host return steering/exp053_host_return_steering.py"
```

The harness creates four disposable network namespaces, materializes the topology and policy,
runs H1-H4, prints explicit PASS markers, and removes all namespaces in `finally`.

## PASS criterion

EXP-053 is PASS only if H1-H4 pass in one run.

A PASS proves only the Linux mechanism at the host/managed-stack boundary. It does not prove
multi-path return pinning inside the managed namespace and does not by itself define final
product requirements, lifecycle reconciliation, mark allocation, or host-route ownership.
