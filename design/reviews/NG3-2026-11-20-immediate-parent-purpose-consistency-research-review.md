# NG3 research review — immediate-parent Purpose consistency

**Date:** 2026-11-20  
**Branch:** `ng3-research-20261120-requirement-purpose-parent-consistency-30m`  
**Baseline:** main snapshot 145 `623a688e4080de56e5ac14675ffca028c3865d18`  
**Scope:** all current NG3 derived Requirements, using the strict immediate-parent Purpose test.  
**Normative files modified:** none.

## Method

The current tree was parsed as `ID -> immediate parent -> Purpose -> Statement`.
Every derived Requirement was checked against the requirement-model rules:

1. Purpose must causally support the immediate parent Statement, not merely a distant ancestor;
2. Purpose must not first introduce an independent product capability/scenario;
3. mentally removing the immediate parent must not leave the child independently justified
   for the same reason;
4. implementation/configuration placement is not a substitute for product Purpose.

Adjacent Constraints were read where they affect the causal chain, but this is not a new full
Constraint-Reason audit.

## Population

Current actual VPNG tree:

- primary project Requirements: **7**
- derived Requirements: **146**
- Constraints: **33**
- total normative VPNG nodes: **186**

The 2026-11-16 rationale review covered an earlier 128-node tree. The present tree has grown
substantially since then, especially in Device policy, availability, managed-domain,
host-routing and production-language branches. Its historical PASS is therefore evidence for
that baseline, not a proof of the later nodes.

## Results

**128 / 146 derived Requirements pass the immediate-parent test without a material finding.**

**18 / 146 require action or explicit human review:**

### Safe research corrections

1. `VPNG0001-R1.R2` — Purpose wording leaned on the primary root rather than naming the
   immediate managed-routing parent. Research draft rewrites Purpose only; Statement unchanged.
2. `VPNG0001-R1.R2.R4.R4.R1` — duplicate/misplaced availability-config node. Its semantics
   are already fully represented by the `VPNG0003-R3.R6...` availability subtree. Research
   draft omits the duplicate; no capability is removed.

### Unresolved ancestry / product-provenance findings

3. `VPNG0001-R1.R2.R4.R4.R4` — Profile source-NAT capability.
4. `VPNG0001-R1.R2.R4.R6.R1` — Device outbound NAT capability.
5. `VPNG0001-R1.R2.R4.R6.R2` — Device firewall capability.
6. `VPNG0001-R1.R2.R4.R6.R3` — server publication capability.
7. `VPNG0001-R1.R2.R4.R6.R4` — client transport/control capability.
8. `VPNG0001-R1.R3.R5` — transport endpoint provenance.
9. `VPNG0001-R2.R2` — peaceful host-routing helper.
10. `VPNG0001-R2.R3` — aggressive host-routing helper.
11. `VPNG0002-R2.R6` — remote-initiated-flow return affinity.
12. `VPNG0003-R3.R6.R3.R1` — user-selected availability criterion.
13. `VPNG0004-R4.R6` — host-network non-interference under the safety tree.
14. `VPNG0004-R4.R6.R1` — separate managed network domain as normative Requirement.
15. `VPNG0004-R4.R6.R1.R5` — literal INPUT/OUTPUT/FORWARD=DROP requirement.
16. `VPNG0004-R4.R7` — administrative payload-containment capability.
17. `VPNG0005-R5.R6.R4` — reload capability.
18. `VPNG0007-R7.R7.R1.R1` — lifecycle experiment as child of basic-applicability gate.

These are not all equal. Some Statements are likely valid product needs with the wrong
parent; some are likely architecture/configuration choices that should not be normative
Requirements; some need explicit product-holder provenance before either conclusion is safe.

## Important distinction

This review does **not** infer that the implementation behind a bad ancestry is wrong.

For most findings there are two independent questions:

1. Is the capability actually wanted?
2. If yes, what accepted parent/Basis causally requires it?

A wrong answer to (2) does not justify deleting working code. Conversely, existing working
code/evidence does not answer (1).

## Architecture/code consequence

If current capabilities are retained and only ancestry/IDs are corrected, expected impact is
primarily traceability churn. Runtime behavior can remain unchanged.

The most architecture-sensitive finding is `VPNG0004-R4.R6*`: the exact ID family is used
widely throughout managed-domain architecture/evidence. Reparenting or making the requirement
mechanism-neutral would require substantial current-document remapping but need not require a
managed-domain implementation change.

The highest potential code impact exists only if human review rejects existing semantics for
Profile SNAT, Device firewall/NAT/publication, peaceful helper, established-flow return
affinity, availability criterion or managed-domain isolation.

Detailed impact is recorded in
`design/NG3/research/NG3-2026-11-20-purpose-parent-impact.md`.

## Requirement-state inventory

This research branch does not modify normative requirement states.

Current normative tree remains unchanged with:

- existing resolved `decomp` links unchanged;
- active `unreal`: none;
- active `broken`: none;
- active `rejected_closure`: none;
- existing postponed `pending_closure` nodes unchanged.

The research annotations are not `broken` links because no normative decision has yet been
accepted.

## Verdict

**RESEARCH COMPLETE; NORMATIVE CHANGE BLOCKED ON HUMAN DECISIONS.**

The tree is substantially consistent, but the later-grown capability/configuration branches
contain 18 immediate-parent findings. Two can be corrected without a new product decision;
the remaining 16 must not be normalized away by wording alone.
