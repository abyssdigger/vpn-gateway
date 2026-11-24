# EXP-046 — managed publication local INPUT/OUTPUT admission

## Purpose

Prove the exact nftables local/system allow primitive required by an already accepted
Device transport publication.

EXP-010/011 already prove publication topology and real OpenConnect same-port transport.
This experiment proves only the managed-namespace `stack_input` / `stack_output`
packet-filter contribution needed for the internal publication endpoint.

## Candidate contribution

For one normalized internal publication endpoint:

```text
INPUT:
    meta iif = current host-boundary ifindex
    ip daddr = exact managed local publication IPv4
    tcp|udp dport = exact internal port
    accept

OUTPUT:
    meta oif = current host-boundary ifindex
    ip saddr = exact managed local publication IPv4
    tcp|udp sport = exact internal port
    accept
```

No blanket `ct state established,related` rule is used.

## Procedure

A disposable host namespace and managed namespace are connected by one veth pair. A second
Device-side namespace reaches the managed namespace through a different veth.

The managed namespace owns:

- exact local publication IPv4 on loopback;
- TCP and UDP listeners on the same internal publication port;
- `stack_input policy drop`;
- `stack_output policy drop`.

Checks:

1. empty local chains block TCP and UDP publication traffic;
2. adding the exact INPUT+OUTPUT contributions restores both TCP and UDP;
3. the same destination/port arriving through the Device-side interface remains blocked;
4. wrong destination port remains blocked;
5. nft JSON is recorded for all four exact rules.

## Scope limits

PASS does not choose external publication grammar, relay implementation, listener process
model or arbitrary external/internal port translation semantics. It proves only the narrow
managed local firewall contribution for an already-normalized internal publication endpoint.
