# EXP-042 — Device firewall L3/L4 predicate JSON primitives

## Purpose

Establish the minimum Linux/nftables lower evidence needed before the NG3 semantic
Device-firewall compiler can emit exact predicate expressions.

This experiment is **lower-mechanism evidence only**. It does not choose external
configuration grammar and does not declare which protocol names/combinations become
user-facing Release-1 syntax.

## Requirements

- `VPNG0001-R1.R2.R4.R6.R2.R1`;
- `VPNG0001-R1.R2.R4.R6.R2.R2`;
- `VPNG0004-R4.R1`;
- `VPNG0004-R4.R2`.

## Primitive questions

For an ordinary nft child chain, record exact JSON for:

1. IPv4 source CIDR;
2. IPv4 destination CIDR;
3. L4 protocol selector through `meta l4proto`;
4. TCP source port;
5. TCP destination port;
6. UDP source port;
7. UDP destination port;
8. terminal `return` / `drop`.

The tested TCP/UDP/ICMP tokens are technical examples for lower JSON evidence. PASS does not
make them an external parser whitelist.

## Candidate rules

```text
ip saddr 192.0.2.0/24
ip daddr 198.51.100.10
meta l4proto tcp
tcp sport 12345
tcp dport 443
return

meta l4proto udp
udp sport 5353
udp dport 53
drop

meta l4proto icmp
return
```

## Decision

PASS may be used by a later pure compiler to build exact nft match expressions from already
normalized internal predicate semantics.

PASS does not:

- choose TOML spelling;
- accept arbitrary protocol tokens;
- define protocol/port validation policy;
- select final REJECT realization;
- authorize mutation.
