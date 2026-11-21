# NG3 availability defaults / Profile override and probe path discriminator review

**Date:** 2026-11-19  
**Scope:** unresolved probing work since main snapshot 109, including path-specific ICMP discrimination, Release-1 availability configuration semantics, Device-default/Profile-override resolution, parser/status integration, and associated tests.

## Scope and requirement trace

Reviewed against:

- `VPNG-U001-R1.R2.R4.R4.R1`
- `VPNG-U003-R3.R6.R1`
- `VPNG-U003-R3.R6.R3`
- `VPNG-U003-R3.R6.R3.R1`
- `VPNG-U003-R3.R6.R3.R1.C1`
- `VPNG-U003-R3.R6.R3.R1.C1.R1`
- `VPNG-U003-R3.R6.R3.R1.C1.R1.R1`
- `VPNG-U003-R3.R6.R3.R1.C1.R1.R2`
- `VPNG-U003-R3.R6.R3.R1.C1.R1.R3`
- `VPNG-U003-R3.R6.R3.R1.C1.R1.R4`
- `VPNG-U003-R3.R6.R3.R1.C1.R1.C1`
- `VPNG-U003-R3.R6.R3.R2`

The accepted product scenario is that one Device may serve several Profiles with different
business reachability criteria. Availability evidence therefore remains scoped to
`(Profile, logical VPN path)`. A Device may provide a reusable default description, while a
Profile independently chooses no check, that default, or its own same-shape description.

## Findings and dispositions

### F1 — old Profile-only wording conflicted with reusable Device defaults

The previous wording said availability-check configuration itself was Profile-scoped. That
would make a Device-owned reusable default description contradictory even though the outcome
must remain Profile/path scoped.

**Disposition:** accepted and fixed. The requirement now scopes the *Profile selection and
criterion* to Profile, while explicitly allowing reuse of a Device description. Evidence
ownership remains unchanged.

### F2 — old architecture still derived omitted ICMP targets from runtime topology

That architecture no longer matched the accepted configuration contract and would retain an
unnecessary heuristic target-discovery component.

**Disposition:** accepted and fixed. `AvailabilityTargetCalculator` was replaced by the
pure `AvailabilityDescriptionResolver`. It selects disabled / Device default / Profile
override and never invents a target from interface, peer or routing observations.

### F3 — Device default must resolve separately for each Device path

A multi-Device Profile selecting `default` cannot resolve one Profile-global target because
each permitted Device may have a different default criterion.

**Disposition:** accepted and fixed. Resolution is per availability subject. Tests cover one
Profile using two Device paths with different Device defaults.

### F4 — Profile override must not become Device-global state

Reusing a Device description is configuration reuse only. Sharing health/evidence by Device
would violate `VPNG-U003-R3.R6.R1` and break the valid scenario where two Profiles use the
same path with different criteria.

**Disposition:** accepted and fixed. Concrete runtime intents remain owned by
`ProbePolicyOwner(profile_id, path_id)`. Tests cover two Profiles producing different
targets for the same logical path.

### F5 — recovered path discriminator implementation had incomplete fixtures

The corrected probe routing contract requires both RPDB `oif` and `ping -I <ifname>`.
Initial implementation updates left one `ProbeRuleSpec` fixture without endpoint and the
canonical structural-inventory EXP-065 fixture without `oif`.

**Disposition:** accepted and fixed. Unit tests are green after both fixture corrections.

### F6 — architecture still carried the pre-fix "current defect" marker

After the executable oif + `ping -I` correction was accepted, §8.3 still described the
missing-oif condition as a current implementation defect. That made the architecture
self-contradictory with the reviewed implementation.

**Disposition:** accepted and fixed. §8.3 now records the implemented RPDB `oif`
discriminator and bound ICMP execution instead of the obsolete defect marker.

### F7 — three Linux integration jobs remain red but are baseline failures

Current branch CI reproduces failures in:

- `linux-selected-host-bootstrap-backend`
- `linux-nft-marked-host-bootstrap`
- `linux-profile-gateway-nat-association`

The same three jobs were already failing on main snapshot 108 workflow run
`44473463226`. They are unrelated to the changed availability/probe contracts.

**Disposition:** not a finding against this review unit. Do not claim whole-workflow green.
Changed-scope evidence is evaluated separately.

## Evidence

Relevant GitHub Actions evidence:

- branch run `44487686360`: `unit` success, `linux-probe-runtime` success,
  `linux-route-priority` success, `linux-structural-inventory-shape` success;
- later branch run `44487959828`: `unit` success and `linux-probe-runtime` success after
  the new availability resolver tests, while newer pushes cancelled some longer unrelated
  jobs;
- main baseline run `44473463226`: the same three unrelated Linux jobs listed in F6 fail on
  pre-change main.

The unit suite includes the new resolver scenarios and reports them passing.

## Simplification review

No generic probe-description framework is introduced. Release 1 still supports only ICMP
with one exact IPv4 target. The resolver has no runtime observation, history, caching,
fallback target inference, or shared Device health. Device default is copied into
subject-specific intent only when a Profile explicitly selects `default`.

No timing/hysteresis user knobs are added.

## Requirement-state inventory

### decomp

All current links are resolved; none is pending:

- `VPNG-U005-R5 -> VPNG-U005-R5.R6`
- `VPNG-U004-R4.R6 -> VPNG-U004-R4.R6.R1`
- `VPNG-U001-R1.R3 -> VPNG-U001-R1.R3.R2`
- `VPNG-U001-R1.R2 -> VPNG-U001-R1.R2.R2`

Some links appear at more than one relevant tree location; their causal status is the same.

### unreal

none

### broken

none

### rejected_closure

none

## Final verdict

**ACCEPTED for the reviewed scope.**

The Device-default/Profile-override semantics are consistent with the existing multi-Profile
Device model and preserve Profile/path-scoped evidence. The path discriminator correction is
represented consistently in desired state, observed state, comparison, mutation and ICMP
execution. Changed-scope unit and probe evidence is green. The known whole-workflow Linux
failures are baseline failures and are not used as positive evidence.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005-R5` -> `VPNG-M001-R1.R1`
- `VPNG-U005-R5.R6` -> `VPNG-M001-R1.R1.R6`

The original IDs in the historical body are intentionally preserved.
