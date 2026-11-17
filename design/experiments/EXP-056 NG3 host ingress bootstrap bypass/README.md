# EXP-056 — NG3 host-ingress bypass for bootstrap routing

## Status

PREPARED — evidence pending.

## Question

Can host bootstrap routing live entirely outside `main` so that:

- ordinary/local traffic to managed destinations enters the VPN-GATE stack;
- every packet that already emerged from the managed stack bypasses bootstrap capture and uses
  the ordinary host `main` table;
- full-tunnel `0.0.0.0/0` therefore needs neither split-default mutation in `main` nor exact
  endpoint pins;
- dynamic VPN-server underlay replies are naturally routed outward;
- an exact payload destination may equal a VPN transport endpoint because ingress direction
  disambiguates the two cases?

## Mechanism

```text
dedicated table:
    default via <managed-inner-peer> dev <host-boundary>

RPDB, before ordinary main rule:
    iif <host-boundary> lookup main
    to <bootstrap-prefix> lookup <dedicated-table>
```

The first rule has higher precedence. The host `main` table remains untouched.

## PASS criterion

PASS requires all of:

1. ordinary host-local lookup for an endpoint covered by `0/0` selects the managed boundary;
2. forwarded ordinary/LAN lookup selects the managed boundary;
3. the same destination with ingress from the managed boundary selects the ordinary uplink;
4. real traffic originated inside the stack reaches the external endpoint through host main;
5. no exact endpoint pin exists;
6. the ordinary host main default is unchanged;
7. the same behavior holds when the managed destination is the endpoint exact `/32`.

A PASS supersedes the need for endpoint-pinning as the preferred Release-1 bootstrap mechanism;
EXP-054 remains useful comparative evidence, not necessarily the selected architecture.
