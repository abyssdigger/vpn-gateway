# VPN-GATE NG3 — Payload NAT Authoritative Observation Boundary Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-structural-barrier-40m`

## Trigger

EXP-033 proved the selected exact-ifindex masquerade behavior, but also showed that nft JSON
does not simply echo numeric ifindices.

A live operand is rendered as its interface name; after that ifindex disappears, the stale
operand is rendered as a decimal-string index.

Therefore textual nft rule equality is not an authoritative NAT identity model.

## Accepted observer inputs

The future strict observer receives:

1. canonical nft objects already scoped to the marked `table ip vpn_gate`;
2. a fresh current `InterfaceIdentity(ifname, ifindex)` inventory.

It runs only after table/scaffold ownership is confirmed.

## Accepted rule shape

The only current payload NAT rule is exactly:

```text
payload_postrouting
comment vpn-gate:ng3:payload-nat-v1
meta iif == <operand>
meta oif == <operand>
masquerade
```

No additional expression is silently ignored.

## Interface operand normalization

### Current textual name

Resolve through the fresh link inventory to the complete current InterfaceIdentity.

### Decimal-string index

Resolve by exact current ifindex if present.

If absent, preserve it as stale numeric identity. Do not map it to a same-name replacement.

This directly models the EXP-033 result:

```text
old oif = 9
new same-name oif = 11
stale nft rule after replacement -> right = "9"
```

### Other form

Conflict.

## Whole-chain classification

Because `payload_postrouting` is an owned chain, every contained rule must be accounted for.

A rule with the wrong/missing owner comment or unsupported expression is an explicit
conflict, not foreign state to ignore.

This is stricter than table-level marker ownership and is required before any cleanup/delete
operation.

## Comparison identity

Desired semantic physical identity is:

```text
current ingress InterfaceIdentity
current egress InterfaceIdentity
plain masquerade
```

Rule handle is actual-object identity for an eventual exact delete, not desired identity.

A stale unresolved ifindex cannot confirm desired state.

## Mutation boundary

This review accepts **observation semantics only**.

No physical NAT mutation should be added until:

- strict parser is executable;
- actual-vs-desired comparison is executable;
- conflict/stale cases are tested;
- mutation remains behind the confirmed ForwardingGate structural barrier.

## Human-facing grammar

No new decision is required here.

The observer is downstream of normalized `NatIntent`; it does not depend on whether final
TOML eventually spells that intent with the historical `nat = "masquerade"` form or another
accepted canonical syntax.

## Verdict

**PASS — authoritative NAT observation contract closed; implementation is the next unit.**
