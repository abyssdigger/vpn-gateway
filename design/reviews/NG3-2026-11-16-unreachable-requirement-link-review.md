# VPN-GATE requirements-process review — unreachable causal links

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-endpoint-provenance-35m`

## Finding

The existing `[decomp: ...]` link is insufficient for a different state: a requirement can
be fully understood yet impossible to satisfy because several already accepted R/C nodes,
possibly from different branches, jointly eliminate every valid realization.

## Accepted link

```text
[unreachable because of <R/C-ID>, <R/C-ID>, ...]
```

The link is attached to the unreachable Requirement and contains the minimal sufficient
normative causal set.

It means "no compliant realization exists while this Requirement and all listed R/C nodes
remain in force". It does not mean "architecture is not known yet".

## Distinction

- `decomp` — insufficient semantics prevent honest further decomposition;
- `rejected_closure` — one architecture closure candidate failed;
- `unreachable because of` — the normative tree itself has no solution for this Requirement.

An active unreachable link therefore blocks architecture closure and implementation. Human
requirement resolution must change/remove at least one conflicting obligation or prove the
causal set wrong.

## Causal-set discipline

The set may contain several R/C nodes from different branches. Each must be normative and as
specific as practical. Experiments/components do not appear directly in the link; technical
facts must first be lifted into an accepted Constraint.

When the conflict is actually resolved, the active link is removed from the current tree and
Git/review history retains the former conflict. Merely deleting the annotation is not a
resolution.

## Example class

A hypothetical "endpoint IP must never be present in config" Requirement can become
unreachable when the accepted tree simultaneously establishes that:

1. interface discovery does not provide the transport endpoint;
2. endpoint-derived availability/filtering requires the endpoint identity;
3. all product configuration must live in the one accepted configuration surface.

The exact IDs would be recorded only if those concrete normative nodes exist in the product
tree.

## Verdict

**PASS.** `design/requirements-model.md` and `CONTINUOUS-DEVELOPMENT.md` now distinguish
normative unreachability from decomposition and architecture failure and gate closure and
implementation accordingly.
