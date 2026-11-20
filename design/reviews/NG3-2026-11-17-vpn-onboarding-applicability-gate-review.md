# VPN-GATE NG3 — external VPN onboarding applicability gate review

> **Current interpretation (2026-11-20):** this review records the original closure
> wording of `VPNG0001-R1.R3.C1.R1.R1`. The current Requirement is mechanism-neutral: it
> requires reproducible end-to-end evidence that the published onboarding contract produces a
> channel VPN-GATE can accept and use under all requirements applicable to that integration.
> The managed-domain placement, exact binding and forwarding steps described below remain the
> concrete EXP-049 scenario because separate requirements require them; they are not themselves
> prescribed by `C1.R1.R1`.

**Date:** 2026-11-17  
**Cycle branch:** `ng3-design-cycle-20261117-stop-cleanup-35m`

## Scope

Review the missing acceptance obligation behind the Release-1 administrator-provisioned VPN
boundary.

Existing requirements already establish that:

- VPN-GATE Release 1 does not provision/configure VPN channels itself
  (`VPNG0001-R1.R3.C1`);
- the project must provide an administrator-facing supported-integration instruction/contract
  (`VPNG0001-R1.R3.C1.R1`);
- the usable data-plane endpoint must exist inside the managed network domain
  (`VPNG0001-R1.R3.C2`);
- a current logical path may be used only after exact current endpoint binding
  (`VPNG0001-R1.R3.R2`).

The gap was that none of those nodes required evidence that the administrator-facing contract
is actually reproducible on a target Linux system.

## Finding F1 — documented plausibility is not sufficient applicability evidence

The current architecture permits several integration shapes:

- create the VPN endpoint inside the managed namespace;
- start the VPN process inside that namespace;
- move an externally created interface into it;
- another reviewed integration-specific mechanism.

That architectural freedom is legitimate, but without an end-to-end proof the project could
call an integration supported while having proved only isolated namespace, routing, firewall
and binding primitives.

**Disposition:** accepted.

Added `VPNG0001-R1.R3.C1.R1.R1`: every external VPN onboarding mechanism claimed as
supported by Release 1 requires reproducible acceptance evidence that an administrator can
follow the published procedure, place/create the real data-plane endpoint inside the managed
domain, and let VPN-GATE freshly observe, exactly bind and use it through the existing
forwarding contract.

## Finding F2 — this is an acceptance obligation, not VPN provisioning scope expansion

The new node does not require VPN-GATE to create or configure VPN sessions.

The administrator still performs external VPN provisioning under
`VPNG0001-R1.R3.C1`. The product/project obligation is to prove that the published handoff
boundary is executable and repeatable.

Therefore the new requirement refines the already accepted administrator-support obligation
rather than contradicting the first-release constraint.

## Architecture closure

The architecture now defines the exact evidence boundary:

```text
published administrator procedure
    ->
administrator-only external VPN setup/onboarding
    ->
real VPN data-plane endpoint inside managed network domain
    ->
fresh VPNPathAdapter observation
    ->
exactly one expected logical-path binding
    ->
path admitted to accepted forwarding contract
```

It also requires:

- no VPN-GATE source patching during onboarding;
- exact external VPN implementation/version and procedure recording;
- clean teardown;
- at least one repeated clean onboarding run;
- per-integration evidence unless equivalence is explicitly reviewed.

This is sufficient architecture closure for
`VPNG0001-R1.R3.C1.R1.R1`.

## Evidence plan

`EXP-049 — administrator VPN endpoint onboarding applicability` is now planned.

Its PASS criterion is intentionally end-to-end. Separate lower PASS evidence for netns/veth,
route/RPDB, nft or binding is not a substitute.

A PASS for one concrete VPN integration applies only to that tested onboarding mechanism unless
a later review proves another mechanism materially equivalent.

## Closure versus completion

Architecture closure and product evidence completion are deliberately separate:

- requirement architecture closure: **PASS**;
- EXP-049 execution: **PENDING**;
- claim that a concrete Release-1 external VPN integration is supported: **GATED until its
  applicability evidence passes**.

Therefore the requirement may be marked `[closed]` without pretending EXP-049 has run.

## Accumulated requirement-state inventory

### `decomp`

All six previously accumulated links remain resolved. Pending: **none**.

### `unreal`

**none**

### `[rejected_closure]`

**none**

## Human decisions required

**none.** The requirement is the direct refinement requested for this cycle; no additional
product semantic choice is introduced.

## Verdict

**PASS — architecture closure accepted; applicability evidence remains explicitly pending.**
