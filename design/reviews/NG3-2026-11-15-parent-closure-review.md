# VPN-GATE NG3 — Parent Closure Review

**Cycle:** `ng3-design-cycle-20261115-managed-domain-contract-40m`  
**Scope:** verify whether parent requirements are actually architecture-closed after child reviews.

## Purpose

Closure is not inherited mechanically from children.

A parent may remain open even when every current child is closed if the current decomposition failed to cover part of the parent's statement.

## VPNG-R1.R3

**Verdict:** ACCEPT CLOSURE.

The architecture now covers the complete current statement:

- VPN-GATE consumes externally provisioned supported VPN channels;
- each path has stable logical identity;
- one verified current binding maps that identity to one concrete endpoint;
- endpoint replacement supersedes the old binding;
- the endpoint used for forwarding is inside the managed network domain;
- the administrator-facing onboarding/configuration contract is defined at architecture level.

No unresolved architecture decision remains on `VPNG-R1.R3` for the current first-release scope.

## VPNG-R4.R6.R1

**Verdict:** ACCEPT CLOSURE.

All required managed-domain properties are now answered architecturally:

- ownership of internal mutable network state;
- explicit host/domain boundary;
- VPN path endpoint placement inside the domain;
- pre-use endpoint/binding verification.

The dedicated Linux network namespace plus explicit boundary-link approach is sufficient for the current scope.

## VPNG-R4.R6

**Verdict:** ACCEPT CLOSURE.

The parent promise is fully represented by the accepted managed-domain contract and its architecture.

The closure does not make Linux netns itself a product requirement; it accepts the current architecture as sufficient for the requirement.

## VPNG-R1.R2

**Verdict:** KEEP OPEN.

The existing children close only the **configuration** side of the parent:

- declarative logical entities;
- VPN path binding intent;
- validation before mutation.

However the parent also promises product **control operations**.

Those semantics are not yet sufficiently decomposed. They overlap the lifecycle branch and therefore the parent now carries:

```text
[decomp: VPNG-R5 -> pending]
```

This is a decomposition finding, not a rejected closure: no complete closure candidate for the parent existed.

## Review finding

This review demonstrates why parent closure must remain explicit:

```text
all current children closed
!=
parent automatically closed
```

The parent statement must be reread independently during closure review.

## Verdict

**PASS.**

Accept closure for:

- `VPNG-R1.R3`;
- `VPNG-R4.R6.R1`;
- `VPNG-R4.R6`.

Keep `VPNG-R1.R2` open and blocked on lifecycle/control-operation detail from `VPNG-R5`.
