# NG3 review — Release-1 executable-alpha readiness truth audit

**Date:** 2026-11-20  
**Branch:** `ng3-design-cycle-20261120-release1-readiness-audit-30m`  
**Base:** snapshot 144 `925a147477cfe86ad7877e39e03d37daf1c8814a`  
**Reviewed implementation/docs head:** `56009f23069c578e0359cf1ea2740cd38344282f`  
**Verdict:** **ACCEPTED — READINESS-TRUTH BLOCK COMPLETE**

## Scope

Audit current, non-historical statements about the executable Python alpha against the
already accepted Release-1 requirements, architecture, implementation and evidence.

This unit does not create a stable packaging contract, status API, new capability or new
requirement semantics.

## Findings and dispositions

### F1 — current alpha documentation falsely said availability was incomplete/rejected

**Decision:** accepted.  
**Resolution:** fixed.

The deployment README simultaneously described canonical `availability_check` support and
then claimed that availability/failover was not end-to-end and that the alpha rejected
`availability_check`.

Those statements were stale after the accepted continuous-availability implementation:

- `AlphaPreparedPolicy` materializes availability intent and probe-local/routing policy;
- the runtime executes ongoing ICMP observation/reconciliation;
- EXP-068 proves failover/recovery on the real Linux dataplane;
- RuntimeStatusAgent exposes bounded current states
  `disabled|unconfirmed|monitoring|problem`.

The current README now describes that behavior and no longer claims rejection.

### F2 — alpha Profile-SNAT test name still claimed the capability was unmaterialized

**Decision:** accepted.  
**Resolution:** fixed and strengthened.

The old method name
`test_alpha_accepts_availability_but_still_rejects_unmaterialized_snat` no longer matched
its own body or the runtime.

The test is now `test_alpha_materializes_availability_and_profile_snat` and, rather than
checking only parsed `effective_snat_address`, it executes
`AlphaPreparedPolicy.build_current(...)` and verifies:

- stack return-affinity desired state is present;
- exactly one Profile-SNAT rule is materialized;
- the rule uses the configured `198.19.255.10` source identity;
- the SNAT egress is the current managed host boundary.

This complements EXP-076, which remains the real privileged Profile-SNAT dataplane evidence.

### F3 — current README called the Profile-SNAT host return route a prototype

**Decision:** accepted.  
**Resolution:** fixed.

The current contract is no longer a prototype-only route. Host-side reachability to a
Profile SNAT identity is supplied either by the explicitly enabled peaceful helper or by the
equivalent administrator route documented by the manual host-integration contract.

Core Profile-SNAT semantics still end at the managed boundary and do not promise host-side
reachability by themselves.

## Evidence boundary

The current evidence is intentionally compositional rather than forcing every capability
into one installed-systemd smoke:

- EXP-068 — continuous availability/failover/recovery on a real Linux dataplane;
- EXP-076 — Profile-SNAT dataplane and return-domain behavior;
- current alpha unit evidence — both features pass through the actual
  `AlphaPreparedPolicy` runtime assembly boundary;
- EXP-051 — installed Debian 13/systemd package/controller/VPN lifecycle smoke and ordinary
  payload integration.

No accepted R/C requires EXP-051 itself to duplicate every already-proven policy capability.
Adding such duplication solely for test breadth would not be justified by
`VPNG0007-R7.R1`.

## Current alpha vs production/stable boundary

The executable Python alpha is now internally truthful about the two capabilities audited
here. This does **not** make it the final production/stable implementation.

The architecture still deliberately leaves concrete stable production packaging/version
lifecycle and a stable external status presentation/API unspecified. The existing
RuntimeStatusAgent semantics and alpha JSON snapshot satisfy current observability semantics;
choosing a stable external API/schema/path would create a user-visible interface decision
that is not derivable autonomously from the current requirement tree.

Likewise, this review does not declare the `VPNG0007-R7.R8.C2` Python-completion/Rust
transition gate globally satisfied. That gate requires a separate review of the complete
non-exempt production boundary, not inference from one alpha readiness audit.

## Requirement-state impact

No R/C wording or closure state changes.

Existing postponed nodes remain postponed:

- `VPNG0001-R2.R3` aggressive helper, with continuous recovery/containment children;
- `VPNG0004-R4.R7` administrative payload containment;
- `VPNG0005-R5.R6.R4` reload orchestration when a selected interface exposes reload.

No active `unreal`, `broken` or `rejected_closure` relationship is introduced.

## Verification

Exact reviewed head `56009f23069c578e0359cf1ea2740cd38344282f`:

- NG3 Python workflow `44780168555` — **SUCCESS**;
- compile/unit — PASS;
- installed alpha smoke — PASS;
- OpenVPN onboarding regression — PASS;
- host-routing evidence — PASS;
- Debian-12 routed-veth portability — PASS;
- all remaining workflow jobs — PASS.

## Final verdict

**ACCEPTED — READINESS-TRUTH BLOCK COMPLETE.**

The current executable-alpha documentation/test truth is consistent for availability and
Profile SNAT. Further movement toward a production/stable Release-1 package/status interface
requires an explicit product/interface decision rather than autonomous implementation.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG0007-R7.R1` -> `VPNG9001-R1.R1.R1`
- `VPNG0007-R7.R8.C2` -> `VPNG9001-R1.R1.R8.C2`

The original IDs in the historical body are intentionally preserved.
