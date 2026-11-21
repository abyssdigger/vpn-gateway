# VPN-GATE NG3 — user-facing grammar deferral review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-config-format-35m`

## Scope

Classify exact user-facing policy spelling after the semantic closures for Device firewall,
endpoint provenance and Profile gateway NAT.

The purpose of this review is to distinguish:

- accepted product semantics;
- normative core configuration already fixed in NG3;
- user-visible optional-policy spelling that is deliberately postponed.

## Findings

### F1 — Optional-policy grammar is not an open semantic Requirement

Accepted semantics already define:

- Device NAT modes and explicitness;
- ordered Device firewall behavior;
- endpoint provenance / endpoint-scoped future filtering;
- Profile ordinary-side gateway NAT;
- transport publication ownership;
- Profile-scoped ICMP availability target semantics.

The remaining slash/comma/quote/TOML representation choices do not change those promises.
They are user-visible interface decisions and must receive human acceptance before parser
implementation, but they do not justify reopening the semantic requirement tree.

**Disposition:** accepted. One explicit deferral now inventories the affected surfaces and
their re-entry condition.

### F2 — The prior config model contained stale "remain open" wording

`design/NG3/config-model.md` still described already-closed R/C nodes as open and treated
some interface spelling as generically "unresolved".

**Disposition:** fixed. The document now distinguishes closed semantics from postponed exact
external spelling.

### F3 — Availability timing names were presented as unresolved despite no requirement for knobs

No accepted NG3 Requirement says the user must configure availability interval/hysteresis
values merely because runtime types contain such values.

**Disposition:** fixed. Internal timing names are not schema obligations. If user-facing
timing controls are later required, they re-enter through ordinary requirement/config-format
review.

### F4 — Transition checklist still used old Device-envelope vocabulary

The normative transition checklist still described `Device envelope` as the current model.

**Disposition:** fixed. It now describes the accepted ordered Device firewall and points to
the explicit grammar deferral.

## Deferral

The canonical deferral is:

`design/deferrals/NG3-user-facing-policy-grammar.md`

It currently covers exact spelling/encoding for:

- Device VPN-side NAT;
- ordered Device firewall;
- named endpoint declarations/selectors;
- Profile ordinary-side gateway NAT;
- Device publication;
- Profile availability-check field/string spelling and any future timing/unit knobs.

Re-entry occurs when parser implementation for one of these surfaces becomes the next bounded
unit or when the user explicitly asks to settle the compact notation.

## Closure verdict

**PASS.**

No product-semantic requirement remains open merely because these external strings have not
yet been selected. Parser/serialization for the affected surfaces remains gated by the
explicit interface deferral.

## Accumulated requirement-state inventory

### `decomp`

All current links are resolved:

1. owner `VPNG-U001-R1.R2`:  
   `VPNG-U005-R5 -> VPNG-U005-R5.R6` — **resolved**.
2. owner `VPNG-U001-R1.R3.C1.R1`:  
   `VPNG-U004-R4.R6 -> VPNG-U004-R4.R6.R1` — **resolved**.
3. owner `VPNG-U001-R1.R3.C1.R1`:  
   `VPNG-U001-R1.R3 -> VPNG-U001-R1.R3.R2` — **resolved**.
4. owner `VPNG-U001-R1.R3.C1.R1`:  
   `VPNG-U001-R1.R2 -> VPNG-U001-R1.R2.R2` — **resolved**.
5. owner `VPNG-U001-R1.R3.C2.R1`:  
   `VPNG-U004-R4.R6 -> VPNG-U004-R4.R6.R1` — **resolved**.
6. owner `VPNG-U004-R4.R6.R1.R6.R1`:  
   `VPNG-U001-R1.R3 -> VPNG-U001-R1.R3.R2` — **resolved**.

Pending `decomp`: **none**.

### `unreal`

**none**

### `[rejected_closure]`

**none**


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005-R5` -> `VPNG-M001-R1.R1`
- `VPNG-U005-R5.R6` -> `VPNG-M001-R1.R1.R6`

The original IDs in the historical body are intentionally preserved.
