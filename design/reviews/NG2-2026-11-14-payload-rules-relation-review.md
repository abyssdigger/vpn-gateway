# NG2 — PayloadRulesState relation review

**Дата:** 2026-11-14  
**Тип:** autonomous internal development review  
**Scope:** conservative relation proofs for divergent payload rules

## Review criteria

Проверялись:

- semantic equality vs Python structural equality;
- independence of convergence / safety / service axes;
- soundness of SAFE and UNSAFE proofs;
- absence of Linux/backend assumptions;
- conservative handling of unknown predicate implication;
- clean separation between network-rules vocabulary and payload-rules assessment;
- future compatibility with ProbeRulesState without premature commonization.

## Findings

### R1 — dataclass equality was too structural

**Severity:** correctness/architecture  
**Disposition:** accepted and fixed.

Plain `NetworkRulesSpec == NetworkRulesSpec` treated some semantically unordered
collections as ordered serialization.

This could produce false `DIVERGED` when only these changed order:

- routing domains;
- destinations inside one routing domain;
- allow-only traffic rules;
- flow-initiation allow rules.

Fix:

- explicit semantic equality;
- routing domains compared by logical name;
- destinations compared as sets;
- allow-only rule collections compared as sets;
- ordered paths remain ordered;
- dispatch remains ordered because the current contract expresses dispatch priority through
  its ordered projection;
- source NAT remains order-sensitive until the generic contract proves reordering
  commutative.

### R2 — SAFE restriction does not prove DEGRADED service

**Severity:** architecture  
**Disposition:** accepted and fixed.

The first implementation mapped every provably restrictive divergence to:

```text
SAFE + DEGRADED
```

This violated the independent-axis model.

Example: disappearance of a backup path proves a rules restriction, but does not by itself
prove that current payload service is degraded.

Fix:

```text
proven restrictive divergence
    -> safety = SAFE
    -> service = UNKNOWN
```

Service is classified only where its consequence is independently provable.

### R3 — narrow conservative SAFE proof

**Severity:** safety  
**Disposition:** accepted and implemented.

A divergent ruleset is proven restrictive only when all of the following hold:

- same routing-domain identities;
- same destinations and terminal disposition;
- actual ordered paths are an order-preserving subsequence of desired paths;
- dispatch projection is unchanged;
- actual traffic allows are an exact-rule subset of desired traffic allows;
- actual flow-initiation allows are an exact-rule subset of desired flow-initiation allows;
- source-NAT projection is unchanged.

The proof intentionally rejects many actually-safe cases rather than guessing.

### R4 — endpoint-pair permission widening can prove UNSAFE

**Severity:** safety  
**Disposition:** accepted and implemented.

If desired contains no byte-level allow for a semantic endpoint pair and observed contains a
provably non-empty allow for that pair, observed rules permit behavior forbidden by desired.

This produces:

```text
KNOWN + DIVERGED + UNSAFE + service UNKNOWN
```

`Safety` describes ruleset permissions, not whether another simultaneous routing defect
happens to prevent packet delivery at this instant.

### R5 — predicate widening inside an existing endpoint pair remains UNKNOWN

**Severity:** conservative limitation  
**Disposition:** accepted; no defect.

Example:

```text
desired: endpoint A -> B, destination 10.0.0.0/8
actual:  endpoint A -> B, ANY
```

is intuitively a widening, but the current implementation does not attempt general boolean
predicate implication.

It therefore remains `safety = UNKNOWN`.

A future implication engine may add proved cases, but the current model must not infer them
from syntax alone.

### R6 — failed intermediate CI run remained visible

**Severity:** test process  
**Disposition:** accepted and fixed.

The first relation change intentionally changed the old expectation for a same-purpose test:
replacement of an approved interface endpoint by an unapproved endpoint is now provably
`UNSAFE`.

The old test expected `UNKNOWN`, causing an NG2 CI failure. The expectation was corrected;
a patching typo in the stale-observation test was then caught and fixed as well.

Final NG2 CI on the corrected baseline is green.

## Component/domain review

All relation helpers remain private implementation of
`PayloadRulesStateCalculator`. No generic `NetworkRulesRelationCalculator` or common
rules-state type was introduced.

That is deliberate:

- the proof logic currently answers payload-state questions;
- ProbeRules semantics do not yet exist in code;
- commonization remains gated on the previously agreed post-Probe review.

No Linux route type, nft construct, conntrack state or Adapter lifecycle concept is used by
the calculator.

## Evidence

NG2 Python CI passed on commit
`d10ffab281299a1fd7a136fdfc61f33f9166e5ae`.

Tests cover:

- semantic equality under reordered domains/destinations/allow rules;
- safe ordered-path removal;
- safe allow removal;
- reordered paths remaining unclassified;
- new endpoint-pair allow -> UNSAFE;
- changed concrete interface endpoint -> UNSAFE;
- widening predicate on an existing endpoint pair remaining UNKNOWN;
- independent service UNKNOWN for merely safe restriction.

No kernel experiment is required; this is pure semantic relation logic.

## Final verdict

**PASS.**

No unresolved finding blocks this review unit.

Next coherent unit: define the payload-domain projection published by
`PayloadTrafficManager` and decide how aggregate `PayloadRulesState` maps to per-Profile
runtime information without reintroducing network-stack details.
