# NG3 2026-11-24 — architecture traceability hygiene review

**Scope:** resolve the accepted structural/traceability findings CO-4, TG-1, N-1, N-2,
N-3, N-4, N-5/N-8 and N-7 without changing product semantics.

## Verdict

**PASS — the accepted architecture hygiene findings are resolved.**

## Findings and dispositions

### F1 — RuntimeStatusTextRenderer Space API markers

**Decision:** accepted.  
**Resolution:** fixed.

The STACK occurrence is now `@RuntimeStatusTextRenderer`; its Space API entry is
`@RuntimeStatusTextRenderer.render(...)`; A.009 exposes `@render(...)`; interaction edges use
the same marked occurrence. The canonical component heading remains unmarked as required by
§2.6.

### F2 — exact configuration-validation trace

**Decision:** accepted.  
**Resolution:** fixed.

A.002 now directly lists `VPNG-U002-R2.R3.C1.R1` as a full contribution and explicitly
records `VPNG-U001-R4.R4.R6.R2.R5.C1` as a constraint. The existing §2.10 coverage remains
valid; these additions improve local reverse traceability rather than creating new closure.

### F3 — Device-firewall packet-field meaning

**Decision:** accepted.  
**Resolution:** fixed.

C.001 decision 8 now states that IN/OUT field matching occurs in the `forward` chain before
the subsequent VPN-GATE source-address translation. The configured L3/L4 fields therefore
refer to literal payload fields at that filtering point, as required by
`VPNG-U001-R4.R4.R6.R2.R2`.

### F4 — probe local admission ownership

**Decision:** accepted.  
**Resolution:** fixed.

C.001 now explicitly describes `probe local admission policy` as derived lower state used
only to satisfy the exact A.007/C.008 availability-check execution precondition. It is not an
independent user policy and cannot widen Profile/Device payload permissions.

### F5 — environment containment wording

**Decision:** accepted.  
**Resolution:** fixed.

C.007 now permits only the namespace entry and ForwardingGate read needed to establish
containment before trust. Observation/repair of other owned environment properties begins
after fresh confirmation of `ForwardingGate=DISABLED`.

### F6 — C.002 full contribution does not claim whole-requirement enforcement

**Decision:** accepted.  
**Resolution:** fixed.

C.002 keeps `VPNG-U004-R4 — [full]` because §2.9 defines materialization status per component
contribution. A new decision makes the contribution explicit: C.002 fully owns only
representability/allocation rejection before mutation; restrictive enforcement belongs to
C.003/C.005.

### F7 — aggressive Release-1 constraint is explicit on the child Enforcer

**Decision:** accepted.  
**Resolution:** fixed.

E.004 now explicitly records `VPNG-U001-R5.R2.C1` under `Constrained by`, matching its
parent E.003 and making constraint search direct.

### F8 — rejected reviewer findings remain rejected

**Decision:** rejected as changes.

CO-2 remains rejected: Release-1 permission constraints retain their scope meaning even when
a stronger implementation exists. The historical EV-00010 109/109 count remains tied to its
explicit reviewed baseline and is not rewritten as a current count.

## Evidence

- NG3 Python unit/architecture-traceability job on structural commit
  `744ae37326cb0f8cbb5df582d15694cd72fe743b`: PASS.
- Final commit `5151ef217b8fb7d61d5bb86b7ea78d1f20741e12` changes only the Russian wording of
  the C.007 clarification after the same semantic review.
- Actual-main lineage guard on the final commit: PASS.

No unresolved finding remains in this review unit.
