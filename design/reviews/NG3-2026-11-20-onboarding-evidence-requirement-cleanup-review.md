# VPN-GATE NG3 — onboarding evidence requirement cleanup review

**Date:** 2026-11-20  
**Branch:** `ng3-onboarding-evidence-requirement-cleanup`  
**Reviewed head:** `92e7e1c105ee3127b6189704de9990fe56584d95`

## Verdict

**PASS.**

`VPNG-U001-R1.R3.C1.R1.R1` remains a valid child of the administrator-onboarding
compensation requirement, but no longer embeds the first concrete Linux realization into the
Requirement itself.

## Requirement result

The Requirement now asks only for reproducible end-to-end acceptance evidence proving that,
for every deployment/onboarding method claimed as supported by the first release, an
administrator can follow the published onboarding contract without modifying VPN-GATE
internals and reach a state in which VPN-GATE accepts and uses the channel in accordance with
all requirements applicable to that integration.

The Requirement no longer names:

- managed-network-domain endpoint placement;
- a concrete endpoint-observation mechanism;
- logical-path binding as an evidence step;
- a particular forwarding pipeline.

Those remain independently required when their own R/C apply.

## Removed causal links

The two former `decomp` links from `C1.R1.R1` to the binding/configuration branches were
removed.

They were artifacts of the old mechanism-specific Statement. The generic evidence obligation
does not decompose through one particular binding/configuration path; it composes with the
complete applicable requirement set of each supported integration.

## Architecture and evidence mapping

Architecture §1.1.2 now separates:

```text
C1.R1.R1
    -> reproducible end-to-end onboarding acceptance evidence

concrete supported integration
    -> applicable independent requirements
    -> concrete acceptance scenario
```

For the current OpenVPN/systemd Release-1 integration, EXP-049 still checks managed-domain
placement, fresh endpoint observation, exact logical-path binding and forwarding. These checks
remain valid because EXP-049 directly traces the independent requirements that own those
semantics, including `VPNG-U001-R1.R3.C2` and `VPNG-U001-R1.R3.R2`.

EXP-049 therefore remains valid evidence; only the ownership of its individual checks is made
explicit.

## Downstream interference review

`VPNG-U007-R7.R7.R1` and EXP-050 depend on a PASS of the basic applicability evidence gate,
not on the lower mechanisms being textually embedded in `C1.R1.R1`. Their dependency remains
valid.

Historical reviews retain their original wording. The review that originally introduced the
mechanism-specific Requirement now carries a current-interpretation note clarifying that its
managed-domain/binding/forwarding sequence is the historical concrete EXP-049 scenario, not
the current Requirement Statement.

No runtime code or behavior changed.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U007-R7.R7.R1` -> `VPNG-D001-R1.R1.R7.R1`

The original IDs in the historical body are intentionally preserved.
