# NG3 research review — immediate-parent Purpose consistency

**Date:** 2026-11-20  
**Branch:** `ng3-research-20261120-requirement-purpose-parent-consistency-30m`  
**Baseline:** main snapshot 145 `623a688e4080de56e5ac14675ffca028c3865d18`  
**Scope:** all baseline NG3 derived Requirements plus product-holder dispositions applied to
the non-normative corrected-tree draft.  
**Normative files modified:** none.

## Method

The baseline tree was parsed as `ID -> immediate parent -> Purpose -> Statement`.
Every derived Requirement was checked against the requirement-model rules:

1. Purpose must causally support the immediate parent Statement, not merely a distant ancestor;
2. Purpose must not first introduce an independent product capability/scenario;
3. mentally removing the immediate parent must not leave the child independently justified
   for the same reason;
4. implementation/configuration placement is not a substitute for product Purpose.

Adjacent Constraints were read where they affected the causal chain. This was not initially a
full Constraint-Reason audit, but one adjacent placement defect
(timing/hysteresis under availability reuse) was retained and corrected when the accepted
availability subtree was remapped.

## Baseline population

Snapshot 145 normative VPNG tree:

- primary project Requirements: **7**
- derived Requirements: **159**
- Constraints: **20**
- total normative VPNG nodes: **186**

The 2026-11-16 rationale review covered an earlier 128-node tree. Snapshot 145 had grown
substantially since then, especially in Device policy, availability, managed-domain,
host-routing and production-language branches.

## Baseline audit result

**139 / 159 derived Requirements passed the immediate-parent test without a material finding.**

**20 / 159 required action or explicit human review.**

Two were safe research corrections:

1. `VPNG0001-R1.R2` — Purpose wording leaned on the primary root rather than the immediate
   managed-routing parent;
2. `VPNG0001-R1.R2.R4.R4.R1` — duplicate/misplaced availability-config node.

The remaining 18 findings required product-holder disposition.

## Product-holder dispositions applied

The accepted decisions are recorded in
`design/NG3/research/NG3-2026-11-20-requirement-refactor-decisions.md`.
The resulting proposed tree is rendered in
`design/NG3/research/NG3-2026-11-20-purpose-parent-corrected-requirements-draft.md`.

The current research draft has:

- primary project Requirements: **7**
- derived Requirements: **153**
- Constraints: **24**
- total proposed nodes: **184**

The count change is not itself a scope change: several old implementation/configuration nodes
were removed or split into a product capability plus configuration Constraint/Requirement,
and managed-domain mechanism nodes were moved out of requirement semantics.

### Resolved findings

The draft now has accepted dispositions for **17 of the original 20 findings**:

1. former `VPNG0001-R1.R2` configuration ancestry — common configuration moved directly
   under `VPNG0001` as provisional `VPNG0001-R4`;
2. duplicate Profile availability config node — removed;
3. Profile source identity / `+snat` — product capability lifted to provisional
   `VPNG0001-R3`, Release-1 spelling remains a config contract;
4. Device outbound NAT — product capability separated from `use_outbound_nat`;
5. Device firewall — product additional-restriction capability separated from firewall
   grammar/config placement;
6. VPN-server publication — moved to supported VPN-channel transport conditions;
7. VPN-client transport/control admission — moved to supported VPN-channel transport
   conditions;
8. transport endpoint provenance — removed from requirement tree; retained only as possible
   lower architecture fact;
9. peaceful host-routing helper — moved under positive host-routing automation capability;
10. aggressive host-routing helper — moved under the same positive automation capability and
    remains postponed for Release 1;
11. user-selected availability criterion — confirmed and reworded;
12. host-network safety/non-interference — kept as mechanism-neutral
    `VPNG0004-R4.R6`;
13. managed network domain — removed as product Requirement and retained as selected
    architecture mechanism;
14. literal INPUT/OUTPUT/FORWARD=DROP requirement — removed with the managed-domain
    implementation subtree; default-deny realization remains architecture/evidence;
15. protective/containment mode — promoted to first derived level under `VPNG0004` as
    provisional `VPNG0004-R5`;
16. Device-default/Profile-override availability reuse — moved out from under the ICMP-only
    Constraint;
17. remote-initiated-flow return affinity — moved from `VPNG0002-R2.R6` to forwarding
    behavior under `VPNG0001-R1.R1` as provisional `VPNG0001-R1.R1.R1`; the same-path
    Statement is retained, while flow/network-property stability is stated in Purpose.

The adjacent timing/hysteresis constraint was also moved to sibling
`VPNG0003-R3.R6.R3.R1.C2`, so it no longer depends on Device-default/Profile-override reuse.

### Remaining unresolved findings

Three baseline findings still lack a product-holder disposition and remain explicitly marked
`RESEARCH UNRESOLVED` in the draft:

1. `VPNG0004-R4.R3.R1` — priority-only make-before-break continuity;
2. `VPNG0005-R5.R6.R4` — reload capability/contract placement;
3. `VPNG0007-R7.R7.R1.R1` — second VPN lifecycle evidence gate placement.

Their detailed questions are maintained in
`design/NG3/research/NG3-2026-11-20-purpose-parent-unresolved-questions.md`.

## Important semantic distinctions established by the refactor

### Capability is not configuration placement

A user-facing field does not prove the product obligation it controls. The draft therefore
separates product capabilities from Release-1 config contracts for Profile source identity,
Device NAT/firewall and VPN transport/control functions.

### Architecture is not product semantics

The selected managed network domain, namespace boundaries and nft default policies may remain
good architecture. They are no longer treated as externally meaningful Requirements merely
because the current implementation uses them.

### Logical VPN path is the policy entity

Transport endpoint/peer provenance is no longer a required user-facing/product entity.
Future path-specific policy refers to a distinguishable logical VPN path; endpoint/peer
association may remain an internal adapter fact.

### Non-interference and automation are different obligations

`VPNG0001-R2` remains a limiting non-interference requirement. Peaceful and aggressive
host-routing helpers now derive from a separate positive automation requirement instead of
being justified by a parent that only says what an optional helper must not disturb.

## Architecture/code consequence

The accepted refactor implies **high traceability churn but low functional-code churn**.

Most existing Release-1 behavior can remain unchanged. The largest future document remap is
the managed-domain architecture: sections currently tracing directly to
`VPNG0004-R4.R6.R1*` must instead explain the domain/netns/nft mechanisms as an
architecture choice satisfying mechanism-neutral safety plus the relevant forwarding,
binding and policy requirements.

The current architecture/config-model must **not** yet be partially rewritten to provisional
draft IDs while `design/NG3/requirements.md` still contains snapshot-145 normative IDs.
That would create broken live traceability. The required current-document remap is recorded
in `NG3-2026-11-20-purpose-parent-impact.md` and should be performed atomically with
normative promotion of the corrected tree.

Historical reviews and experiment result files retain their original requirement IDs and
context. Current architecture/registries may later record superseding mappings; historical
evidence itself should not be rewritten.

## Requirement-state inventory

This research branch still does not change the normative requirement tree or its closure
states.

The proposed draft deliberately uses provisional IDs and marks newly created/reparented
semantic owners `pending_closure` where existing architecture closure has not yet been
revalidated against the new Statement/ancestry.

No production/reference code was changed by this research refactor.

## Verdict

**RESEARCH DRAFT SUBSTANTIALLY SYNCHRONIZED; THREE PRODUCT/PLACEMENT DECISIONS REMAIN.**

The original 20 findings have been reduced to three unresolved questions. The corrected-tree
draft, decision record, unresolved list and impact assessment are now aligned with each other.

Normative promotion remains blocked until the remaining three findings are decided and the
resulting tree is reviewed as one coherent requirement structure. After that, current
architecture/configuration/registry documents require an atomic trace remap; historical
reviews/experiments remain unchanged.
