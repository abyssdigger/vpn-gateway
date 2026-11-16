# VPN-GATE NG3 — Lower Route-Priority Realization Contract Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-primary-requirements-basis-40m`  
**Implementation/fix commits reviewed:**  
- `eeffa788e5a5517ad55a55bd4db3f62f5b3417ea`
- `7fd57fef61804f0ada5f6aa6a4950a1f36445b36`

## Scope

This unit implements the lower internal contract identified by the preceding
semantic-to-physical boundary review.

It does not allocate resources by itself and does not change user configuration.

The contract carries, for one physical route-key domain:

- `RoutePriorityDomainId`;
- internal route table ID;
- internal owner protocol;
- current `RoutePriorityPathRoute` realization for each logical path;
- owned route metric space.

It also maps the semantic ordered logical paths onto the lower metric preference slots.

## Requirement / architecture gate

The unit remains below NetworkPolicyAdapter and therefore preserves:

- user intent without Linux metric/table fields;
- PayloadTrafficManager independence from physical route representation;
- current logical-path identity separate from concrete endpoint/gateway form;
- Executor ownership of physical route convergence.

No new product semantics were required.

## Finding F1 — preference slot order initially did not enforce Linux metric semantics

**Severity:** material internal semantic defect  
**Disposition:** accepted and fixed in `7fd57fef`

The first version treated `preference_slots` tuple order as authoritative but did not
require numeric Linux metric order to agree with that tuple.

A lower allocator could therefore supply:

```text
preference_slots = (20, 10)
```

and semantic path #1 would be assigned metric 20 even though Linux would prefer path #2 at
metric 10.

The fixed contract requires preference slots to be **strictly increasing numeric Linux
metrics**.

Therefore:

```text
semantic path order
    ->
preference_slots order
    ->
Linux lower-metric preference
```

is one consistent ordering.

## Finding F2 — physical metric range was under-constrained

**Severity:** low internal hardening  
**Disposition:** fixed in `7fd57fef`

The realization contract now restricts all owned preference/scratch metrics to unsigned
32-bit Linux route-metric range and rejects bool values explicitly through strict integer
typing.

## Accepted invariants

- metric values are unique across preference and scratch space;
- multi-path realization requires at least one scratch metric;
- one-path realization may omit scratch space;
- one concrete endpoint cannot realize two logical paths in the same domain;
- semantic path membership must exactly equal physical realization membership before desired
  metrics are calculated;
- reversing semantic path order reverses which logical path receives the best/lower metric;
- table and owner protocol remain strict internal identifiers.

## Evidence

Final GitHub Actions run:

```text
workflow: NG3 Python
run:      43821152707
commit:   7fd57fef61804f0ada5f6aa6a4950a1f36445b36
unit:     153 tests, OK
linux-route-priority: PASS
overall:  success
```

The Linux integration continues to validate the downstream physical backend after the new
internal contract was added.

## Residual boundary

The contract defines **what** lower realization/allocation must supply. It does not yet
implement the allocator/source that chooses:

- table IDs;
- owner protocol value;
- metric ranges;
- gateway/onlink path realization from current transport topology.

Those choices remain lower Adapter implementation work and must be derived/evidenced without
moving them into user configuration.

## Final verdict

**PASS AFTER FIX.**

The semantic-to-physical boundary now has an executable typed contract that preserves user
path order in real Linux metric semantics while keeping Linux resource allocation below the
Manager.
