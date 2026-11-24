# VPN-GATE NG3 — PayloadProfileRequest projection code review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-post-closure-implementation-readiness-40m`

## Scope

Reviewed:

- `design/NG3/code/python/rou/payload_profile.py`;
- `design/NG3/code/python/rou/tests/test_payload_profile.py`;
- config -> binding -> Profile request seam;
- implementation gate
  `design/reviews/NG3-2026-11-16-payload-profile-request-implementation-gate.md`.

## Evidence

Combined rootless suite after accepted fixes:

```text
35 tests
PASS
```

Python compilation also passed.

## 1. Profile membership and path eligibility

PASS.

Only currently bound logical paths belonging to Devices listed in
`Profile.device_order` become members of `PayloadProfileRequest.ordered_paths`.

Waiting/unbound candidates are not included.

Concrete endpoint identity is not part of the request.

## 2. Baseline ordering

PASS.

For one Profile:

```text
Profile.device_order
    -> selector index
        -> stable slot index
```

is preserved.

The global order of Device binding projection does not become Profile policy.

## 3. Zero-path semantics

PASS.

An enabled Profile with no eligible current binding still produces:

```text
PayloadProfileRequest(..., ordered_paths=())
```

This preserves the structural policy domain required for downstream fail-closed
materialization.

Disabled Profile is omitted.

## 4. Endpoint replacement

PASS.

Replacing concrete endpoint identity while preserving the same `LogicalPathId` leaves
`PayloadProfileRequest` membership unchanged.

This keeps Profile policy independent from current Linux endpoint generation.

## 5. Finding — Profile collection order leaked incidental TOML order

**Severity:** semantic canonicalization defect  
**Disposition:** accepted and fixed

The first implementation returned requests in supplied Profile iteration order.

Named Profiles form a set of policy domains; table declaration order is not a policy knob.

Fix:

- canonicalize request collection order by stable `profile_id`;
- preserve explicit ordering only inside `ordered_paths`.

Regression evidence verifies two equivalent TOML files with different Profile table ordering
produce identical request tuples.

## 6. Scope boundary

No Device policy, availability, route metrics or Linux rules are introduced here.

This unit implements the complete current `PayloadProfileRequest` structural contract only.

Device NAT/envelope/publication remain later inputs to full payload-policy compilation.

## 7. Simplification review

No new component is justified.

The projection is pure synchronous calculation inside current `PayloadPolicyCalculator`
responsibility.

No event, queue, history, retry or lifecycle state is required.

## Verdict

**PASS — PAYLOAD PROFILE REQUEST PROJECTION ACCEPTED.**

The next review unit may either:

- add the authoritative interface-observation Adapter boundary; or
- add another pure policy calculation whose full semantics are already closed.

It must not guess the unresolved Device transport-policy user grammar.
