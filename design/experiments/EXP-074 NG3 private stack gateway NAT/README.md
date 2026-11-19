# EXP-074 — NG3 private stack gateway NAT

Status: **PREPARED**

## Question

Can Profile ordinary-side gateway NAT live entirely inside STACK after the managed firewall,
using the routed managed-L3 endpoint, while ordinary LAN hosts need no route to remote VPN
prefixes or to the stack service /32?

The experiment also checks that:

- two +snat Profiles coexist with one neighboring no-SNAT Profile;
- a more-specific no-SNAT Profile is not accidentally absorbed by a broader +snat Profile;
- reverse NAT completes through the same STACK conntrack state.

## Topology

```text
REMOTE-A/B/C -> STACK -> unnumbered routed veth -> HOST -> LAN

STACK service/NAT identity: 198.19.74.2/32
HOST owns only: route 198.19.74.2/32 dev vpng0
LAN owns only: default via 192.0.2.1
```

No LAN route is installed for any remote VPN prefix or for `198.19.74.2/32`.

Profiles represented by test flows:

- A: +snat;
- B: +snat;
- C: no-SNAT, more-specific exception inside A's broader source prefix.

Host-local traffic is tested separately and must preserve the original remote source.

## PASS

- A/B forwarded peers observe `198.19.74.2`;
- A/B replies complete through STACK reverse NAT;
- C forwarded peer observes its original remote source;
- C does not hit gateway-NAT counters;
- LAN has no remote-prefix or stack-service route beyond its ordinary default.
