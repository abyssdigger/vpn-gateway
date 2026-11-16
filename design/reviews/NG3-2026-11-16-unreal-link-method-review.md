# VPN-GATE requirements-process review — `unreal` causal link

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-config-format-35m`

## Scope

Rename the previously accepted requirement-unrealizability causal link to a compact label and
make residual requirement-state inventories mandatory in final reviews/checkpoints.

## Decision

The canonical syntax is:

```text
[unreal: <R/C-ID>, <R/C-ID>, ...]
```

`unreal` is shorthand for **unrealizable**.

Semantics are unchanged:

- the link is attached to the Requirement whose Statement has no compliant realization;
- the listed R/C IDs form the minimal sufficient normative causal set;
- it is not a decomposition blocker;
- it is not an architecture-candidate rejection;
- an active `unreal` blocks closure and implementation of the affected Requirement;
- resolving it requires a normative change or proof that the causal set was wrong.

Historical review artifacts using the former verbose label remain historical evidence; the
normative method documents use only `unreal` going forward.

## Final-review inventory

Every autonomous final review/checkpoint must explicitly list:

1. active `decomp` links;
2. active `unreal` links;
3. `[rejected_closure]` nodes.

An empty category is written as `none`; it is not omitted.

## Verdict

**PASS.** The shorter label preserves the accepted semantics and makes the three residual
requirement states mechanically and visually distinct.
