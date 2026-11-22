# EXP-082 — protective-mode lower containment composition

## Status

Research experiment for re-entered `VPNG-U004-R5` and the escalation path from
`VPNG-U001-R5.R2.R3`.

## Question

Can the current Linux architecture compose two independently verifiable lower barriers to
realize the traffic part of administrative protective mode without destroying runtime state?

Candidate lower composition:

1. current Private-network `ForwardingGate=DISABLED`
   (`net.ipv4.ip_forward=0`) blocks routed transit inside the managed network domain;
2. a host-side nftables `netdev` ingress+egress gate attached to the exact ordinary-side
   managed-boundary interface drops IPv4 packets crossing that boundary in either direction.

The experiment does **not** select the final public API, lifecycle owner or exit protocol.

## Hypotheses

- **H1:** with both gates open, ordinary -> VPN, VPN -> ordinary and VPN -> VPN test paths pass;
- **H2:** after verified Private-network forwarding disable plus host-boundary IPv4 gate,
  all three test paths fail;
- **H3:** the host boundary link remains UP and the topology/routing state remains present,
  so containment does not require destroying the runtime network objects;
- **H4:** removing the host gate and explicitly re-enabling Private-network forwarding
  restores all three paths.

## Why two barriers

Kernel documentation defines `net.ipv4.ip_forward` as forwarding packets between
interfaces. The current architecture already records that it does not cover local INPUT/OUTPUT
traffic and cannot by itself implement the broader public protective mode.

The nftables `netdev` family supplies per-device ingress and egress hooks, so a boundary
gate can cover packets crossing the ordinary-side interface independently of route lookup.

## Acceptance

PASS establishes only a lower-mechanism feasibility result. Architecture closure still needs:

- a public enter/leave contract;
- verified transition ordering and failure semantics;
- ownership/recovery of both lower barriers while protective mode is active;
- composed acceptance against the exact product postcondition.

## Execution

```bash
sudo python3   "design/experiments/EXP-082 NG3 protective lower containment/exp082_protective_lower_containment.py"
```
