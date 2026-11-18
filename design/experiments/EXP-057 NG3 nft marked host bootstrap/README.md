# EXP-057 — NG3 nft-marked host bootstrap without main-table routes

## Status

COMPLETE — FAIL.

## Question

Can VPN-GATE implement ordinary-side bootstrap routing with only:

- one dedicated host routing table containing a default route to the managed stack;
- one fwmark RPDB rule selecting that table;
- nft PREROUTING/route-OUTPUT classification that marks managed destinations only when the
  packet did **not** arrive from the managed boundary?

If so, host `main` remains entirely ordinary and packets emitted from the managed stack
(client VPN underlay, VPN-server replies, ordinary-side payload egress) naturally bypass
bootstrap capture without endpoint pins.

## Mechanism

```text
table <VPNG>:
    default via <managed-inner-peer>

ip rule:
    fwmark <VPNG> lookup <VPNG-table>

nft prerouting:
    iif != <managed-boundary> && daddr in bootstrap destinations
        meta mark set <VPNG>

nft route-output:
    daddr in bootstrap destinations
        meta mark set <VPNG>
```

The local RPDB rule (priority 0) remains ahead of the VPN-GATE fwmark rule, so traffic to
host-local addresses remains local.

## PASS criterion

PASS requires:

1. host-local traffic to a full-tunnel destination traverses the managed boundary;
2. ordinary forwarded traffic to the same destination traverses the managed boundary;
3. traffic originating inside the managed stack reaches the ordinary uplink without a pin;
4. exact destination equal to the external endpoint is directionally disambiguated;
5. host `main` remains unchanged and contains no VPN-GATE route;
6. removing the nft/table/rule owner restores ordinary host routing.
