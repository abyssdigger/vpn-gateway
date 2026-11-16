# VPN-GATE NG3 — Payload nft Scaffold Comparison Code Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-structural-barrier-40m`  
**Reviewed commit:** `879ed650b4a5689c5e557973eb1a283085a097a9`  
**Live evidence:** EXP-032

## Scope

This unit encodes the accepted invariant payload nft scaffold as immutable lower specs and
compares them with the canonical object snapshot returned by the nft namespace observer.

It performs no nft mutation.

## Accepted invariant specs

```text
payload_forward:
    type filter
    hook forward
    priority 0
    policy drop
    comment vpn-gate:ng3:payload-forward-v1

payload_postrouting:
    type nat
    hook postrouting
    priority 100
    policy accept
    comment vpn-gate:ng3:payload-postrouting-v1
```

Handles are excluded from identity.

## Comparison semantics

PASS.

The result explicitly separates:

- confirmed invariant chains;
- missing invariant chains;
- invariant-chain conflicts;
- unclassified contained nft objects.

### Missing

An owned marked table that lacks one or both invariant chains is incomplete but repairable.

Missing is not treated as foreign ownership.

### Conflict

A same-name invariant chain with wrong:

- type;
- hook;
- priority;
- policy;
- version comment;
- unsupported semantic metadata

is a conflict and is not adopted.

### Unclassified

Rules, sets, maps, future probe chains and any other non-scaffold objects are preserved as
`unclassified_objects`.

They do **not** make the invariant chain metadata itself false, but they prevent the stronger
claim that the complete table policy is classified.

This distinction is exposed as:

```text
scaffold_confirmed
full_policy_classified
```

and is critical for safe later mutation.

## Requirement / safety gate

PASS.

The unit preserves the accepted ownership rules under:

- `VPNG0004-R4.R2`;
- `VPNG0004-R4.R5`;
- `VPNG0004-R4.R6.R1.R1`.

It does not infer user payload permission or NAT policy.

## Live evidence

GitHub Actions run:

```text
run:      43839365393
commit:   879ed650b4a5689c5e557973eb1a283085a097a9
unit:     246 tests, OK
EXP-032 packet/scaffold evidence: PASS
NG3 payload nft scaffold comparison Linux integration: PASS
EXP-031 nft owner marker: PASS
EXP-030 forwarding barrier: PASS
EXP-028/029 + route-priority integrations: PASS
overall:  success
```

## Residual boundary

The next bounded physical unit may bootstrap/repair only the invariant scaffold, and only
behind a confirmed root forwarding barrier.

It may:

- create the marked table + both invariant chains when the namespace is ABSENT;
- add a missing invariant chain to an otherwise empty/classified owned scaffold.

It must refuse mutation when:

- table ownership is CONFLICT;
- an invariant chain is conflicting;
- any contained object remains unclassified.

That keeps scaffold repair from becoming an accidental general nft cleanup engine.

## Final verdict

**PASS.**
