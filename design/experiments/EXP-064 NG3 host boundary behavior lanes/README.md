# EXP-064 — NG3 host-boundary behavior lanes

## Status

COMPLETE — **PASS**. See `EXP-064-result-20261118.md`.

## Context

EXP-063 disproved transient packet-mark handoff across the cross-netns veth boundary as a
usable Profile-association carrier.

The host does not actually need arbitrary Profile identity. For accepted Release-1 semantics
it needs only two already-normalized host-side behavior bits for remote-initiated traffic:

- stateful return steering: yes/no (`+route-return` disables it);
- ordinary-side gateway NAT: yes/no (`+snat` enables it).

That yields four behavior classes independent of the number of Profiles.

## Technical question

Can the managed stack select one of four VPN-GATE-owned boundary lanes after Profile
classification, allowing the host to derive the required behavior only from the actual ingress
lane, while preserving:

- original packet addresses across the boundary;
- host-local traffic without gateway NAT;
- reverse NAT;
- stateful-return and route-return variants;
- stack-side established-flow affinity for the final VPN return path?

## Candidate mechanism

```text
selected inbound Profile
    -> stack connection association
    -> routing mark selects Profile table
    -> Profile table ordinary-side default selects behavior lane

behavior lane identity:
    (stateful-return, gateway-NAT)

host ingress interface
    -> host conntrack behavior class

host forwarded ordinary leg
    -> NAT only for NAT-enabled classes

host reply
    -> stateful classes: dedicated return steering
    -> route-return classes: ordinary route/bootstrap return

stack receives reply
    -> existing stack connection association
    -> original Profile routing domain
```

No per-Profile host lane or user-visible lane exists.

## Distinguishing scenario

Four overlapping remote Profiles are represented by four actual ingress paths. Source-only
host reclassification would not be sufficient to recover which behavior was selected.

One flow is exercised for each behavior class:

| Class | Stateful return | Gateway NAT |
| --- | --- | --- |
| S0 | yes | no |
| S1 | yes | yes |
| R0 | no | no |
| R1 | no | yes |

The host has ordinary return routes only for the two route-return classes. Stateful classes
therefore succeed only through stateful return steering.

## PASS criteria

```text
EXP064_S0_STATEFUL_NO_NAT=PASS
EXP064_S1_STATEFUL_NAT=PASS
EXP064_R0_ROUTE_NO_NAT=PASS
EXP064_R1_ROUTE_NAT=PASS
EXP064_HOST_LOCAL_NOT_NATED=PASS
EXP064_UNRELATED_HOST_UNTOUCHED=PASS
EXP064_STACK_RETURN_AFFINITY=PASS
EXP064_RESULT=PASS
```

A PASS proves technical feasibility of the fixed behavior-lane carrier. Architecture selection,
ownership/convergence and production integration remain separate review work.
