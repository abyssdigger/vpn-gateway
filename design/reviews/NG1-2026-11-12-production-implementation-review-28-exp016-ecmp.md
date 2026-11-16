# Production implementation review 28 — EXP-016 ECMP hash-policy prerequisite

Date: 2026-11-12

Role: internal expert review under CONTINUOUS-DEVELOPMENT.md.

## Scope

Reviewed:

- EXP-016 disposable-netns harness and GitHub kernel evidence;
- namespace prerequisite ownership/apply/verify;
- instance create/ensure bootstrap path;
- unit fixtures and full production-cycle regression;
- architecture/README documentation updated from the experiment result.

## Evidence

Privileged GitHub kernel integration reported:

```text
ACCEPTED_POLICIES: 0 1 2 3
PASS A: policy 1 keeps repeated 5-tuple on one nexthop
PASS B: policy 0 ignores L4-only variation for fixed L3 tuple
PASS C: policy 1 uses L4 flow variation across both nexthops
PASS D: fib_multipath_hash_policy is namespace-isolated
SELECTED_PRODUCTION_CANDIDATE=1
EXP_016_ECMP_HASH_POLICY=PASS
```

The same baseline also passed:

- NG1 rootless tests;
- RC3 validation;
- privileged namespace lifecycle;
- EXP-017;
- nft policy round-trip;
- full NG1 production reconcile cycle.

## Finding F1 — bootstrap sysctl application had two sources of truth

Severity: medium maintenance/consistency.

`create_instance()` manually wrote rp_filter/IPv6 sysctls while `ensure_instance()` and
Planner used `apply_namespace_prerequisites()`.

Adding a normative ECMP hash-policy value to only the shared prerequisite compiler would
therefore make fresh-create and ensure/reconcile semantics diverge.

### Disposition

Accepted and fixed.

Fresh instance creation now:

1. explicitly closes `net.ipv4.ip_forward`;
2. calls the shared namespace prerequisite compiler;
3. installs fail-closed nft state;
4. verifies through the same prerequisite verifier used elsewhere.

The manual duplicated sysctl block is removed.

## Finding F2 — rootless logging fixture retained the pre-EXP value

Severity: low test-fixture drift.

The engine-logging steady-state test still injected
`fib_multipath_hash_policy=0`, so the correctly tightened verifier treated the fixture as
structural drift.

### Disposition

Accepted and fixed. The fixture now uses the normative value 1.

## Production decision

NG1 owns and exactly verifies:

```text
net.ipv4.fib_multipath_hash_policy=1
```

Reasoning:

- stable selection for one 5-tuple;
- L4 flow diversity across fallback ECMP members;
- namespace-local behavior;
- directly proven on the privileged kernel runner.

This closes the hash-policy prerequisite gate for future positive UNAVAILABLE detection.

## Rust-alignment review

The result improves Rust migration shape:

- one constant owns the selected policy value;
- one prerequisite compiler owns mutation;
- one verifier owns exact observation semantics;
- bootstrap and runtime no longer duplicate sysctl policy.

## Verdict

**APPROVED / CLOSED.**

No remaining recommendation in the EXP-016 scope.
