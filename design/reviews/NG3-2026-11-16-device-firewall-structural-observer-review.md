# VPN-GATE NG3 — Device firewall lower structural observation review

**Date:** 2026-11-16  
**Cycle branch:** `ng3-design-cycle-20261116-device-firewall-35m`

## Scope

Review the bounded lower-policy unit that follows the accepted ordered Device-firewall
semantic architecture:

1. EXP-041 Linux/nft evidence for jump/return/drop/reject/order primitives;
2. preservation of physical nft object order in the generic namespace inventory;
3. strict read-only structural observation for owned Device firewall child chains and jumps.

No external config grammar, final predicate compiler or physical mutation is in scope.

## Evidence

EXP-041 final green run:

`43926099105` — **10/10 jobs SUCCESS**.

Confirmed lower facts:

- child `drop` narrows later Profile permission;
- child `return` continues to the Profile hard gate;
- terminal no-match `drop` fails closed;
- nft preserves child-rule order;
- jump/return/drop/reject JSON primitives are observable;
- current numeric interface identities may render as current interface names in nft JSON and
  must therefore be resolved against fresh interface inventory.

## Findings

### F1 — generic nft inventory destroyed physical order

The existing namespace inventory canonicalized contained objects by sorting
`NftNamespaceObject`. That was harmless for existing unordered scaffold/NAT/Profile-rule
consumers but cannot represent ordered Device firewall policy.

**Disposition:** fixed. Every observed nft object now carries `source_order` from the
original nft JSON sequence. Canonical object ordering/equality remains compatible with
existing consumers because `source_order` is observation metadata, not owner identity.

Regression coverage verifies canonical sorting can coexist with preserved source order.

### F2 — Device child-chain ownership needed an explicit marker

A plain regular nft child chain has no hook/type/policy metadata, so name alone is not a
sufficient ownership proof and production naming is not yet selected.

**Disposition:** fixed. EXP-041 and the observer use the explicit chain marker:

`vpn-gate:ng3:device-fw-child-v1`.

The experimental chain name remains deliberately non-normative.

### F3 — explicit rule action markers must identify ownership, not semantic role names

The first harness draft used different comments for a reverse rule and reject evidence.
That would make the observer's ownership vocabulary depend on test scenario roles rather
than the accepted rule class.

**Disposition:** fixed after red CI. All ordinary explicit Device rules use one owner marker:

`vpn-gate:ng3:device-fw-rule-v1`.

Terminal explicit-policy fallthrough remains separately marked because it is a structural
sentinel with a stronger exact-shape invariant.

The intermediate red run is retained as evidence of the harness defect; the corrected
workflow is green.

### F4 — structural recognition must not become deletion authority

The final external grammar and exact protocol/port predicate combinations remain deferred.
A structural observer that accepts arbitrary `match` JSON plus one of the accepted terminal
actions can prove owner/control-flow shape but cannot prove that the rule is the current
desired semantic policy.

**Disposition:** bounded explicitly. The observer retains predicate expressions as canonical
JSON but does not interpret them. It authorizes no mutation by itself.

A later desired-state/compiler unit must define normalized predicate semantics before
recognized explicit rules can be classified exact/missing/stale for production convergence.

### F5 — stale jump identity remains fail-closed

EXP-041 confirms nft may render numeric interface selectors as names. The observer therefore
resolves current names through fresh `InterfaceIdentity` inventory, matching the existing
forward-observer discipline. Numeric operands not present in the current inventory remain
stale identities; unresolved names are conflicts.

**Disposition:** accepted.

### F6 — terminal fallthrough order is structural, not merely semantic

For an explicit policy, the terminal no-match `drop` must be the last rule. Preserving the
set of actions without their order would incorrectly accept rules after the fallthrough.

**Disposition:** observer requires at most one owned fallthrough and reports conflict when it
is not last.

## Component-model review

- `parse_nft_namespace_ruleset` remains a read-only technical inventory boundary.
- `observe_device_firewall_structure` is pure Direct observation/classification machinery.
- Neither chooses product policy or performs mutation.
- No Manager/Agent/state store/event flow was added.

The split remains consistent with the component model.

## Tests / CI

Final behavior-bearing code workflow:

`43926099105` — **PASS, 10/10 jobs**.

Coverage includes:

- existing full NG3 Python unit suite;
- EXP-035..038 and live strict Profile forward observer;
- EXP-041 ordered Device-firewall child-chain behavior;
- scaffold/NAT/routing/platform integrations;
- new structural Device firewall unit tests;
- nft inventory source-order regression coverage.

## Accumulated requirement-state inventory

### `decomp`

All six current links are **resolved**:

1. `VPNG0001-R1.R2`: `VPNG0005-R5 -> VPNG0005-R5.R6`.
2. `VPNG0001-R1.R3.C1.R1`: `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`.
3. `VPNG0001-R1.R3.C1.R1`: `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`.
4. `VPNG0001-R1.R3.C1.R1`: `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`.
5. `VPNG0001-R1.R3.C2.R1`: `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`.
6. `VPNG0004-R4.R6.R1.R6.R1`: `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`.

Pending `decomp`: **none**.

### `unreal`

**none**

### `[rejected_closure]`

**none**

## Remaining gate

The next logical Device-firewall unit is **normalized predicate desired-state/comparison** for
ordinary Release-1 rules. It must define exactly which already-accepted internal predicate
forms are representable without selecting the postponed human-facing grammar.

Physical mutation remains later. Final protocol-appropriate REJECT realization remains a
separate evidence/design gate.

## Verdict

**PASS.** The lower structural owner model is sufficient and correctly bounded. No open
review finding remains in this unit.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG0005-R5` -> `VPNG9101-R1.R1`
- `VPNG0005-R5.R6` -> `VPNG9101-R1.R1.R6`

The original IDs in the historical body are intentionally preserved.
