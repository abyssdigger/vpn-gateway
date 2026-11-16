# NG2 — Adapter owner registry review

**Дата:** 2026-11-14  
**Тип:** autonomous internal development review  
**Scope:** identity-based owner lifecycle utility for future `NetworkRulesAdapter`

## Review criteria

Проверялись:

- соответствие agreed `owner=self` semantics;
- отсутствие предметных знаний о callers;
- защита от Python equality/hash aliasing;
- lifetime/id reuse;
- cleanup behavior;
- отсутствие преждевременной physical composition policy;
- чистота компонентной модели и предметных границ;
- Rust-aligned intent.

## Findings

### O1 — owner equality must never define ownership

**Severity:** correctness/architecture  
**Disposition:** accepted and covered.

Registry indexes by `id(owner)` and additionally verifies `stored.owner is owner`.

Test uses two objects that deliberately compare equal and have the same hash; they remain
two independent owners.

### O2 — Python `id()` reuse must not alias a live owner

**Severity:** correctness  
**Disposition:** accepted and covered by design.

Registry deliberately holds a strong reference to every registered owner. Therefore Python
cannot destroy that object and reuse its address while its registration exists.

Explicit Adapter `cleanup(owner)` will remove the registration and release the strong
reference. A test verifies that the owner remains alive while registered and becomes
collectable after registry removal.

This utility does not itself implement Adapter cleanup of external resources. Its
`remove()` is only the internal final registry step after/while the Adapter performs the
full cleanup contract.

### O3 — registry must not introduce implicit owner ordering or composition semantics

**Severity:** architecture  
**Disposition:** accepted; current implementation is intentionally neutral.

`DesiredRulesByOwner` stores independent complete desired sets. `desired_sets()` exposes
them for a lower composition step but does not:

- assign owner priority;
- merge policies;
- resolve routing conflicts;
- choose nft chain order;
- interpret caller type/name.

Physical composition/conflict handling belongs to the lower Adapter implementation and
requires its own review unit.

Dictionary iteration order is therefore not a semantic priority contract and must not be
used as one by the future composer.

## Model review

`DesiredRulesByOwner` is not a new architectural component. It is an Adapter-internal
data structure.

It introduces no Engine/Machinery role and does not create a new domain boundary.

The externally visible contract remains:

```text
NetworkRulesAdapter
    apply(owner, spec)
    renew_state(owner)
    get_last_state(owner)
    cleanup(owner)
```

## Evidence

GitHub Actions workflow `NG2 Python` was added and completed successfully on Python 3.13
for commit `bb785d98929189f92424601917bcfd069a0790a2`.

The run includes the current filtering, NAT and owner-registry tests.

Owner-registry tests cover:

- equal/hash-colliding objects remain independent owners;
- replacement for the same object preserves one owner slot;
- registry removal is idempotent;
- strong-reference lifetime until explicit removal;
- desired sets remain separate.

## Final verdict

**PASS.**

No unresolved owner-registry finding remains at minor severity or higher.

The next Adapter unit must treat policy composition/conflict resolution as a separate
lower-domain problem and must not infer semantics from registry iteration order.
