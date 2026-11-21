# VPN-GATE NG3 — R5.C1 recovery-scope review

**Date:** 2026-11-20  
**Branch:** `ng3-r5-c1-recovery-scope-cleanup`  
**Reviewed head:** `e2ec5c970f58837c8637be9ce0545699acffb142`

## Verdict

**PASS.**

`VPNG-U005-R5.C1` remains a valid Constraint under lifecycle/recovery, but its normative role
is now limited to the boundary of required automatic recovery/adoption after unsupported
external intervention.

It is no longer a second blanket safety root.

## Parent/Reason review

`VPNG-U005-R5` requires predictable lifecycle and recovery of VPN-GATE-owned runtime state.

A separate constraint is justified because arbitrary root/admin intervention can destroy or
make ambiguous the identity/ownership facts needed for safe automatic reconstruction. Such an
environment is not necessarily ordinary recoverable drift.

The revised Reason therefore answers the parent question directly:

> why automatic recovery may stop being promised after unsupported external mutation.

It no longer derives the constraint from particular historical implementation artifacts such
as one namespace, veth or systemd dependency object.

## Current C1 semantics

The Constraint now says:

- automatic lifecycle/recovery need not cover authoritative VPN-GATE-owned state that was
  arbitrarily damaged outside the supported lifecycle when a trustworthy desired state
  cannot be reconstructed from accepted configuration plus fresh observation;
- VPN-GATE need not forensic-adopt arbitrary surviving processes, recover unknown namespace
  references or infer ownership from untrustworthy leftovers;
- consequences for forwarding, readiness or another active function are determined by the
  applicable safety/readiness/recovery requirement for the concrete invariant that was lost;
- state outside authoritative VPN-GATE ownership is outside this Constraint, including
  ordinary-host routing returned to administrator control after a peaceful-helper lifecycle
  operation.

This keeps `C1` a recovery-scope constraint rather than a universal reaction policy.

## C1.R1 compensation

`VPNG-U005-R5.C1.R1` remains required and `[`closed`]`.

The administrator-facing contract now distinguishes:

1. authoritative VPN-GATE-owned managed-domain state;
2. administrator-owned integration state, including stack-specific VPN systemd
   units/drop-ins and VPN-specific configuration;
3. ordinary-host routing that peaceful helper automation returns to administrator control
   after its lifecycle operation.

For unsupported damage to authoritative state, documentation explains that the administrator
must repair/clean the environment before returning to the supported lifecycle when automatic
recovery cannot establish a trustworthy postcondition.

## Safety/readiness separation

No existing fail-closed runtime behavior was removed.

For example, the alpha periodic audit still attempts to establish
`ForwardingGate=DISABLED` when exact managed-domain verification is lost. That behavior is
correct because the concrete managed-domain safety postcondition is no longer confirmed.

Its normative basis is the applicable safety chain, especially:

- `VPNG-U004-R4.R2` — unconfirmed safety-critical actual state remains restricted;
- `VPNG-U004-R4.R5` — failed/partial policy mutation must end in a verified safe result or
  closed traffic.

`VPNG-U005-R5.C1` separately explains why the same situation need not trigger a generic
forensic reconstruction/adoption mechanism.

Thus:

```text
C1
    -> may stop automatic recovery/adoption promise

specific safety/readiness invariant
    -> determines whether forwarding closes, readiness is withheld,
       one capability degrades, or another bounded reaction applies
```

## EXP-050 evidence disposition

EXP-050 remains valid selected evidence for bounded systemd VPN lifecycle and absence of a
need for generic VPN process adoption.

Its current contribution to `VPNG-U005-R5.C1` is narrow:

- it supports the bounded recovery/adoption model;
- it did not test arbitrary root damage;
- therefore it must not be cited as proof that every arbitrary host mutation requires a
  blanket fail-closed reaction.

The historical result text remains unchanged. A current requirement-mapping note now records
this narrower interpretation.

Observed fail-closed containment in EXP-050 remains valid evidence for the concrete safety
postconditions exercised by that experiment.

## Historical reviews

The following historical reviews retain their original reasoning:

- `NG3-2026-11-17-systemd-vpn-onboarding-exp050-review.md`;
- `NG3-2026-11-17-first-functioning-alpha-review.md`;
- `NG3-2026-11-17-systemd-vpn-onboarding-exp050-35m-checkpoint.md`.

Each now carries a current-interpretation note stating that historical blanket fail-closed
wording must not be treated as the current meaning of `VPNG-U005-R5.C1`.

## Architecture/document interference review

Updated current normative/operator documents:

- `design/NG3/requirements.md`;
- `design/NG3/architecture.md`;
- `design/NG3/vpn-onboarding-release1.md`;
- EXP-050 current evidence/disposition text;
- `CHANGELOG-NG3.md`.

No code or runtime mutation was necessary.

The current architecture may continue to cite `C1` where a component is constrained by the
absence of generic forensic recovery/adoption. It must cite the relevant safety/readiness
requirements, not `C1`, when explaining why a concrete failure closes forwarding or
withholds readiness.

## Closure status

`VPNG-U005-R5.C1` remains `[`closed`]`.

`VPNG-U005-R5.C1.R1` remains `[`closed`]`.

The closure is narrower and more precise than before; no product recovery or safety promise
was weakened. The removed blanket interpretation was redundant with, and less precise than,
the existing safety/readiness requirement tree.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005-R5` -> `VPNG-M001-R1.R1`
- `VPNG-U005-R5.C1` -> `VPNG-M001-R1.R1.C1`
- `VPNG-U005-R5.C1.R1` -> `VPNG-M001-R1.R1.C1.R1`

The original IDs in the historical body are intentionally preserved.
