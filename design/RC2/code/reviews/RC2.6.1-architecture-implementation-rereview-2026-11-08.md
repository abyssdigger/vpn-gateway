# Independent re-review — RC2.6.1 implementation/data-model feasibility

**Date:** 2026-11-08  
**Reviewed commit:** `174f9a1dff396098a20d6882397aeffabf8261ae`  
**Scope:** previous implementation review findings, typed snapshot, selector validation,
kernel boundary, package split

## Previous findings disposition check

### RC2.6 I1 — immutable pass snapshot

**RESOLVED.**

RC2.6.1 explicitly introduces one conceptual `ReconciliationSnapshot` containing interface
inventory, resolutions, readiness, desired routes and full desired policy. It correctly
states that this is internal consistency, not atomic multi-syscall kernel state.

### RC2.6 I2 — CONFIGURED RouteSpec

**RESOLVED.**

The architecture no longer requires complete config-only UNICAST RouteSpec generation.
UNICAST is derived only from config + concrete binding; selector sentinel cannot enter
RouteSpec.

### RC2.6 I3 — selector intersection

**SUFFICIENT ARCHITECTURALLY, implementation work remains.**

Pairwise semantic disjointness and key conflict examples are normative. A pure
`selectors_overlap()` helper remains the natural implementation but does not need to be an
architecture API.

Required tests still include exact/family and family/family overlap under the 15-character
limit.

### RC2.6 I4 — duplicate interface identities

**RESOLVED.**

Conflicting ifindex for one interface name in one inventory is explicitly invalid.

### RC2.6 I5 — selective cleanup strictness

**RESOLVED.**

Selected proto 201/202 entries remain strict; unsupported selected shapes are fatal.
Proto-201 ownership additionally requires BLACKHOLE + metric 65536.

### RC2.6 I6 — runtime directory opened-object validation

**PARTIALLY ARCHITECTURAL, implementation detail intentionally open.**

The architecture requires non-symlink directory, expected owner and 0700, and no silent
chmod/chown. It does not normatively require the specific dirfd/fstat sequence proposed by
the review.

That is acceptable: opened-object validation belongs in implementation security design and
can be covered by tests.

### RC2.6 I7 — package split

**RESOLVED.**

Multi-file Python package is explicitly allowed, with one daemon entry point and future Rust
single-binary mapping.

### RC2.6 I8 — deny-only policy form

**RESOLVED.**

`desired_full_policy(snapshot)` and `desired_isolation_filter(config)` are explicit policy
forms. Deny-first repair is orchestration, not ad-hoc rule surgery.

### RC2.6 I9 — status binding/readiness

**RESOLVED.**

Status must separate selector/binding/readiness from lifecycle ACTIVE.

---

## New implementation findings

### I1.1 — MEDIUM: desired policy snapshot should not freeze ACTUAL firewall inventory

The conceptual `ReconciliationSnapshot` correctly freezes config-derived interpretation.
Implementation should not be tempted to store the actual iptables snapshot inside it as if
that state were valid throughout later mutations.

Recommended distinction:

```text
ReconciliationSnapshot = DESIRED interpretation
fresh kernel inventories = ACTUAL at each verify boundary
```

The current architecture already implies fresh verify, but the object name is broad enough
that this distinction should remain explicit during implementation.

No architecture change is strictly required if tests enforce fresh ACTUAL reads.

### I1.2 — MEDIUM: selector overlap tests need the prefix-digit corner cases

The architecture's `prefix% -> ^prefix[0-9]+$` semantics create non-obvious family/family
overlaps:

```text
vpns%   vs vpns1%   -> overlap
vpns1%  vs vpns12%  -> overlap
vpns1%  vs vpns2%   -> disjoint
```

subject to the 15-character maximum.

This is not an architecture gap, but the implementation test matrix should explicitly
include it. String-prefix comparison alone is insufficient unless the suffix between
prefixes is checked to be all decimal digits and a valid concrete name can still exist.

### I1.3 — LOW: package migration should preserve one source of policy truth

During the split from the large RC2.5.1 file, avoid an intermediate state where old
`_fixed_firewall_model()` and new `policy.py` both encode policy.

Recommended migration order:

1. introduce typed model/selectors;
2. move/replace policy builder as one source of truth;
3. adapt daemon orchestration;
4. adapt kernel boundary;
5. delete old duplicated policy functions.

This is implementation sequencing, not architecture.

---

## Implementation verdict

**RC2.6.1 is implementable.**

No new architecture blocker was found.

The only architecture-adjacent clarification worth taking before code is the safety review's
distinction between an isolation-filter verify and full-policy SAFE. The remaining findings
belong in implementation tests and migration discipline.
