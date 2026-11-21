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
- derived Requirements: **151**
- Constraints: **23**
- total proposed nodes: **181**

The count change is not itself a scope change: several old implementation/configuration nodes
were removed or split into a product capability plus configuration Constraint/Requirement,
and managed-domain mechanism nodes were moved out of requirement semantics.

### Resolved findings

The draft now has accepted dispositions for **all 20 original findings**:

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
17. remote-initiated-flow return affinity — moved from `VPNG0002-R2.R6` to direct child
    `VPNG0003-R4`; the same-path Statement is retained, while flow/network-property stability
    is stated in Purpose. It remains separate from `VPNG0003-R3` baseline/availability preference;
18. second VPN lifecycle evidence gate `VPNG0007-R7.R7.R1.R1` — removed from the requirement
    tree as a process/evidence sequencing rule rather than a product obligation; EXP-050 remains
    historical evidence and current trace is redirected to the applicable integration, safety
    and lifecycle requirements;
19. priority-only continuity — moved from `VPNG0004-R4.R3.R1` to `VPNG0003-R3.R9`; the
    non-disruptive reorder guarantee is retained while route-copy/staging implementation detail
    is removed from requirement semantics;
20. reload/configuration update — configuration update is now part of `VPNG0005`,
    `VPNG0005-R5` and `VPNG0005-R5.R6`; `VPNG0005-R5.R6.R4` and its `.C1` are removed,
    because `reload` is an optional interface mechanism rather than a mandatory product capability.

The adjacent timing/hysteresis constraint was also moved to sibling
`VPNG0003-R3.R6.R3.R1.C2`, so it no longer depends on Device-default/Profile-override reuse.

### Remaining unresolved findings

None. All original findings have an accepted disposition and are applied to the corrected-tree
draft.

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

## Final coherent-tree integrity pass

After the final two dispositions were applied, the corrected tree was rechecked as one
structure rather than as isolated findings.

Structural checks:

- **181** normative VPNG nodes: 7 primary Requirements, 151 derived Requirements and
  23 Constraints;
- no duplicate requirement IDs;
- no missing immediate parents in the actual VPNG tree;
- no active `RESEARCH UNRESOLVED` marker;
- removed `VPNG0004-R4.R3.R1` and `VPNG0005-R5.R6.R4*` do not remain in the corrected
  tree.

Semantic checks for the final changes:

- `VPNG0003-R3.R9` is causally owned by `VPNG0003-R3`: it preserves practical path
  continuity while applying a change in effective preference and no longer carries a
  route-copy/staging implementation prescription;
- the expanded `VPNG0005` has an explicit additional external Basis from the 2026-11-21
  project-holder decision that configuration update belongs in the lifecycle obligation;
- `VPNG0005-R5` now explicitly owns both lifecycle state and application of changed
  configuration;
- `VPNG0005-R5.R6` requires a supported way to apply changed configuration and safe final
  state, without requiring a distinct `reload` command;
- removal of the former reload Requirement and alpha Constraint does not remove Release-1
  capability: restart remains a valid way to apply changed configuration.

No new product decision was required by this coherent-tree pass.

## Verdict

**PASS — ALL ORIGINAL PURPOSE/PARENT FINDINGS ARE RESOLVED AND THE CORRECTED TREE IS INTERNALLY COHERENT.**

All original 20 findings are resolved in the research draft. The corrected-tree draft,
decision record, unresolved list and impact assessment are aligned with each other.

Normative promotion is no longer blocked by a missing product-holder decision or by the
coherent-tree integrity review. The next step is an atomic trace remap across current
architecture/configuration/registry documents together with normative promotion. Historical evidence
remains preserved according to `PROJECT-CONVENTIONS.md`, including the required historical
requirement context when an experiment referenced a subsequently removed R/C.
