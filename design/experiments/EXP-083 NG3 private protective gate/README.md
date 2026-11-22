# EXP-083 — single Private-network protective gate

## Status

Research experiment for active `VPNG-U004-R5` design.

## Question

Can one independently owned nftables ruleset inside the Private-network namespace realize the
full IPv4 traffic postcondition of protective mode and be installed/removed as one ruleset
transaction, avoiding the release-order problem of the two-barrier EXP-082 composition?

The candidate gate uses one dedicated `inet` table with:

- INPUT drop for IPv4 arriving through the ordinary-side managed boundary;
- OUTPUT drop for IPv4 leaving through that boundary;
- FORWARD drop for all IPv4 transit in Private network.

It does not change interface/link state, routes or the ordinary host namespace.

## Hypotheses

- **H1:** before the gate, five representative paths pass:
  ordinary -> local Private-network endpoint, Private-network local -> ordinary,
  ordinary -> VPN, VPN -> ordinary, and VPN -> VPN;
- **H2:** loading the dedicated nft table with one `nft -f -` transaction blocks all five;
- **H3:** links, routes and `net.ipv4.ip_forward` remain intact while contained;
- **H4:** deleting the dedicated table restores all five paths.

## Interpretation

A PASS demonstrates a simpler lower primitive than EXP-082 for the protective traffic
postcondition. It still does not define public control API, long-lived ownership/recovery or
the semantic preconditions for leaving protective mode.

## Execution

```bash
sudo python3   "design/experiments/EXP-083 NG3 private protective gate/exp083_private_protective_gate.py"
```
