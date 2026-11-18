# EXP-061 — NG3 stack-side established-flow return affinity

## Status

PREPARED — evidence pending.

## Requirements

- `VPNG0002-R2.R6` — reply traffic for VPN-originated managed traffic returns through the VPN
  channel that accepted the original traffic even when another allowed channel also covers the
  sender address.
- `VPNG0007-R7.R3.R4` — identity/state required downstream survives material boundaries or is
  reconstructed unambiguously.
- `VPNG0007-R7.R3.R4.R1` — automated differentiating evidence must cross the material
  boundaries and fail if ordinary reclassification would choose a different result.

## Question

Can Linux conntrack + mark/RPDB preserve the original inbound VPN channel inside the managed
stack when ordinary longest-prefix routing for the reply would select a different, more-specific
VPN route?

## Differentiating topology

```text
remote-A namespace
  source loopback 10.0.0.2/32
  transit 172.16.10.2/30
        |
        | channel A represents 10.0.0.0/16
        |
stack namespace
  A: 172.16.10.1/30
  B: 172.16.20.1/30
  host boundary: 198.18.0.2/30
  main:
      10.0.0.0/16 via A
      10.0.0.0/24 via B   <-- ordinary reply lookup wins here
        |
        | explicit stack/host boundary
        |
host namespace
  boundary: 198.18.0.1/30
  LAN: 192.0.2.1/30
        |
lan namespace
  192.0.2.2/30
```

Channel B is deliberately a sink for this source. Therefore a reply reclassified only by
destination `10.0.0.2` follows the more-specific `/24` and fails.

The host boundary uses the already EXP-053-proven stateful return steering so the LAN reply
returns to the stack without a host main-table route for `10.0.0.0/8`.

The stack then installs a separate connection mark for NEW traffic entering through channel A.
On the return packet entering from the host boundary, that connection mark is restored to the
packet mark; an RPDB rule selects an A-specific return table. Thus established return affinity
wins over ordinary NEW-flow longest-prefix routing.

## PASS criteria

One privileged run must prove all of:

1. main-table lookup for `10.0.0.2` selects channel B due to `/24` over `/16`;
2. before stack-side affinity steering, remote-A cannot complete the ping through LAN;
3. after stack-side affinity steering, the same remote address can complete the ping;
4. host main has no route for the remote prefix, proving the round trip crosses the EXP-053-style
   host return boundary rather than succeeding through an accidental host route;
5. removing stack-side affinity steering restores the failing behavior.

A PASS proves the Linux mechanism and the cross-boundary continuity property for this scenario.
It does not by itself choose permanent mark/table allocation or Release-2 multi-path failover
semantics.
