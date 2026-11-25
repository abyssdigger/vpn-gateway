# NG3 architecture coverage-label cleanup review — 2026-11-25

**Review unit:** unambiguous structured coverage-index vocabulary  
**Reviewed source head:** `16e62c5cc43f79fe31729aad34908821f09db747`  
**Model:** `design/requirements-model.md` §14  
**Evidence:** `EV-00270`

## Verdict

**PASS — component trace semantics now use only canonical `Implements` and
`Constrained by`; the non-component closed-node index uses the neutral
`Coverage nodes` label rather than pretending mixed Requirement/Constraint nodes are one
component edge type.**

## Findings and dispositions

### F1 — §2.9.3 `Covers:` introduced a third direct-edge vocabulary

**Disposition:** accepted / fixed.

The target production-language section remains the semantic owner of the Rust/Python boundary,
but its R8/R8.R1/R8.R2/R8.R3 coverage is now registered in §2.10 rather than through a
standalone `Covers:` syntax.

### F2 — §2.10 `Requirements:` also listed Constraints

**Disposition:** accepted / fixed.

All §2.10 groups now use `Coverage nodes:`, explicitly describing index membership rather
than an Implements edge. Component-local normative direction remains exclusively
`Implements` for Requirement nodes and `Constrained by` for Constraint nodes.

### F3 — mechanical coverage must survive the label cleanup

**Disposition:** accepted.

The structured-coverage parser now consumes `Coverage nodes:`; its former special
`Covers:` parser is removed. R8 and R8.R3 were added to the maintainability/development
coverage group before the standalone marker was removed. The strengthened EV-00250 closure
gate remains green.

## Evidence

- implementation: `16e62c5cc43f79fe31729aad34908821f09db747`;
- GitHub Actions run `45596378111`, unit job `139143419624` — **PASS**;
- actual-main lineage run `45596377672` — **PASS**.
