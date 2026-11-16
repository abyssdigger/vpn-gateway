# EXP-043 — Device firewall active REJECT realization

## Purpose

Prove an exact Linux/nftables lower realization for the already accepted Device-firewall
`REJECT` verdict.

The requirement needs an active negative response, not silent DROP. This experiment compares
candidate lower actions on real forwarded traffic.

## Requirements

- `VPNG0001-R1.R2.R4.R6.R2.R1`;
- `VPNG0001-R1.R2.R4.R6.R2.R2`;
- `VPNG0004-R4.R1`;
- `VPNG0004-R4.R2`.

## Candidate realization

For a rule normalized specifically to TCP:

```text
reject with tcp reset
```

For UDP, ICMP or a protocol-unspecified IPv4 rule:

```text
reject
```

The experiment records exact nft JSON for both forms.

## Behavioral checks

A disposable ordinary -> managed -> VPN forwarding topology is created.

- TCP: a real listener exists on the VPN-side target. The firewall rejects the connection
  with TCP reset; the client must fail immediately with connection-refused semantics rather
  than timeout.
- UDP: a real UDP listener exists. Bare reject must generate an active unreachable observed
  by a connected UDP client as connection refused.
- ICMP: ping through a bare reject rule must receive an explicit unreachable diagnostic,
  not merely time out.

## Scope limits

PASS does not select external `REJECT` spelling. It only selects a lower implementation for
an already normalized Device firewall action.
