# VPN-GATE NG3 — Profile traffic classification code review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-post-closure-implementation-readiness-40m`

## Scope

Reviewed:

- `design/NG3/code/python/rou/profile_classification.py`;
- `design/NG3/code/python/rou/tests/test_profile_classification.py`;
- accepted `PayloadProfileRequest` semantics;
- classification implementation gate.

## Evidence

Combined rootless suite:

```text
50 tests
PASS
```

Python compilation passed.

## 1. Outbound semantics

PASS.

Outbound/bidirectional Profiles are classified by remote destination address.

Inbound-only Profiles cannot win outbound NEW classification.

No match returns `None`; no ambient/default Profile is invented.

## 2. Inbound semantics

PASS.

Inbound/bidirectional candidates are first restricted by the actual ingress
`LogicalPathId`, then by remote source prefix.

Therefore a more-specific prefix belonging to another Device/path cannot shadow a valid
less-specific Profile for the actual ingress path.

Outbound-only Profiles cannot win inbound NEW classification.

A zero-path Profile cannot admit inbound NEW traffic.

## 3. Most-specific overlap

PASS after one material fix.

### Finding — initial implementation used unrelated Profile prefixes for specificity

**Severity:** semantic classification defect  
**Disposition:** fixed before acceptance

A Profile may contain several remote prefixes.

The first implementation selected each candidate's maximum prefix length even when that
longest prefix did not match the current remote address.

Example:

```text
Profile A: 10.0.0.0/8 + 192.0.2.1/32
Profile B: 10.1.0.0/16
remote:    10.1.2.3
```

Profile B must win at /16. The unrelated /32 in Profile A must not affect classification.

Fix:

- compute specificity only from destination prefixes containing the current remote address;
- choose the largest matching prefix length.

Regression added.

## 4. Defensive ambiguity behavior

PASS.

Normal configuration validation already forbids exact duplicate destination ownership among
enabled Profiles.

If an invalid direct caller nevertheless presents two candidates with equal matching
specificity, classification raises `ProfileClassificationError` rather than choosing by
iteration order.

This preserves fail-closed deterministic semantics.

## 5. Component/scope review

Pure calculation remains inside `PayloadPolicyCalculator`.

No packet-processing state, conntrack, route metrics, Linux rules, availability state or new
component is introduced.

Return traffic for already admitted flows remains outside this NEW-flow classifier.

## Verdict

**PASS — PROFILE NEW-FLOW CLASSIFICATION ACCEPTED.**
