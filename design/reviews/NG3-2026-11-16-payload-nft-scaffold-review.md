# VPN-GATE NG3 — Invariant Payload nft Scaffold Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-structural-barrier-40m`

## Scope

Define only the invariant nft object skeleton that is independent of the unresolved
human-facing traffic-envelope/publication grammar and of per-Device NAT choices.

No concrete Profile allow rule, envelope rule or masquerade rule is selected in this unit.

## Selected scaffold

```text
table ip vpn_gate
comment "vpn-gate:ng3:owner-v1"

chain payload_forward
    type filter
    hook forward
    priority 0
    policy drop
    comment "vpn-gate:ng3:payload-forward-v1"

chain payload_postrouting
    type nat
    hook postrouting
    priority 100
    policy accept
    comment "vpn-gate:ng3:payload-postrouting-v1"
```

## Why payload_forward is a base chain with policy drop

The managed network domain exists specifically to contain VPN-GATE forwarding/policy state.

An empty final payload policy must therefore mean:

```text
no forwarded payload is permitted
```

not "fall through to whatever foreign FORWARD policy happens to exist."

A default-drop base chain provides the structural terminal verdict without requiring one
Profile-specific rule to exist.

This is the nft analogue of the historical terminal forwarding deny, but the NG3 choice is
re-derived for the isolated managed domain and is not an import of old chain names.

## Why priority 0

This is the ordinary filter priority and does not require special early-hook packet
interpretation.

Safety does not rely on being first among base chains: nft drop is terminal, while an accept
verdict from another base chain must not bypass a later VPN-GATE drop. EXP-032 must prove
this exact property on the target nftables/kernel combination.

If the live result differs, the priority/layout must be revised before code.

## Why an always-present postrouting NAT chain

NAT semantics are per Device/path and remain explicit product policy.

The base chain itself carries no NAT decision. Keeping an empty owned postrouting chain gives
the structural Executor one stable object boundary whether current desired NAT contributions
are zero or non-zero.

This avoids making chain existence itself a hidden NAT default.

## Ownership markers

Each invariant chain has an exact versioned comment.

The later strict object observer must reject same-name chains whose:

- comment;
- type;
- hook;
- priority;
- policy

do not exactly match the accepted scaffold.

Chain handles are incidental and never ownership identity.

## User-grammar boundary

This unit does not resolve the open human-facing traffic-envelope/publication syntax.

It also does not add a NAT default.

The later final payload nft desired-state builder remains gated until normalized
`DevicePolicyIntent` is executable with explicit NAT intent and, if used, a fully accepted
traffic-envelope semantic representation.

## Evidence gate

EXP-032 must prove:

1. current nftables accepts both base-chain shapes;
2. exact metadata/comments round-trip through JSON;
3. empty `payload_forward policy drop` blocks a real forwarded packet;
4. foreign unconditional accept base chains before and after priority 0 do not bypass it;
5. explicit VPN-GATE accept rules can permit the tested path when added;
6. the empty postrouting chain itself performs no NAT.

## Verdict

**PASS — scaffold selected; executable adoption remains gated by EXP-032.**
