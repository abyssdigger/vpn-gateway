# NG3 2026-11-18 — continuation-rule / gateway-NAT boundary carrier — CD review

> **Historical requirement trace note (2026-11-20):** this review records the requirement
> tree that was current when the review was performed. `VPNG0002-R2.R3.R1.R1`
> was later removed from the current requirement tree when the old direction-derived host-routing
> ownership decomposition was rejected. References below to that ID are historical facts about
> what this review evaluated, not current requirement links; the review conclusions are not rewritten retroactively.

## Verdict

**PASS for the CD process and completed evidence blocks; production gateway NAT remains gated on one explicit requirement decision.**

Nominal CD window:
- start commit: `cc8d6f74e746405c43e63a13ada95fd007f883c2`;
- start time: 2026-11-18 11:28:09Z;
- default interval: 35 minutes;
- nominal boundary: 12:03:09Z.

This cycle exercised the new continuation rule rather than ending after the first completed logical block.

## CD methodology change

`CONTINUOUS-DEVELOPMENT.md` now requires that when a logical block is committed and more than three minutes remain, the cycle plans and executes the next logically adjacent sufficiently-defined block. If starting the next block requires a new product-semantic or architectural decision needing human agreement, that decision boundary is a valid early stop.

## Completed logical blocks

### 1. EXP-062 disposition consistency

The stacked line had drifted: architecture/review already treated EXP-062 as deferred while the registry/experiment artifact still said pending decision.

Corrected authoritative state:

```text
EXP-062
Result: PASS
Disposition: deferred
```

Inbound/bidirectional multipath remains a possible future functional extension and does not change the current single-path baseline.

### 2. EXP-063 — transient packet-mark boundary carrier

EXP-063 tested carrying the already-selected Profile association across the managed/host namespace boundary as transient packet metadata.

**Result: FAIL.**

Distinguishing evidence proved that packets crossed the boundary while the exported transient mark was not available to the receiving host-side consumer. Therefore this carrier is rejected; the failure does not reject Profile ordinary-side gateway NAT itself.

Registry disposition: `not_selected`.

### 3. EXP-064 — fixed host-boundary behavior lanes

The replacement experiment observed that the host needs only two already-normalized behavior bits for remote-initiated traffic:

- stateful return vs route-return;
- gateway NAT disabled vs enabled.

That yields four fixed behavior classes independent of Profile count.

**Result: PASS.**

The experiment proved all four combinations, stack-side return affinity, forwarded NAT/non-NAT behavior, route-return/stateful-return, host-local no-NAT, and unrelated-host isolation.

Final successful evidence:
- workflow `44297463633`;
- job `134778224616`;
- source commit `09a382f31537c427e614b1638e89b9935f627f87`.

### 4. Pure behavior-class projection

Added:
- `host_boundary_behavior.py`;
- deterministic Profile -> fixed behavior-class projection;
- canonical Release-1 `+snat` / `+route-return` combinations mapped to the four classes;
- unit coverage.

This is internal normalized state, not new user configuration.

### 5. Additional managed boundary infrastructure shape

`ManagedNetworkDomainSpec` now supports explicit additional owned boundary veth pairs while preserving the original primary boundary/default-route contract.

Added:
- exact reciprocal-peer and exact-address verification;
- non-overlapping boundary-network validation;
- create/destroy/rollback handling for additional pairs;
- returned current boundary interface identities;
- privileged integration coverage with an additional boundary lane.

Final relevant head evidence on code head `e304ca8c1ca93a6321ae0136e2338664a581d799`, workflow `44299046909`:
- unit — success;
- linux-payload-forward (includes managed-domain lifecycle integration) — success;
- linux-host-boundary-behavior-lanes — success;
- linux-alpha-smoke — success.

### 6. Pure Profile-table behavior-lane route projection

Added `host_boundary_lane_routing.py` and tests.

The pure contract deliberately keeps behavior-lane routes distinct from VPN LogicalPathId routes. Zero-path Profiles keep the lane dormant.

A structural integration review identifies the next implementation requirement: payload structural routing needs an explicit third observable route role for host-boundary lane routes, rather than fabricating a VPN path identity.

## Requirement decision discovered by whole-project review

The cycle found a material mismatch between EXP-064's technically sufficient mechanism and the literal current Statement of:

`VPNG0004-R4.R6.R1.R6.R1`

Its Purpose is to prevent gateway NAT of one Profile from being applied to traffic of another Profile when remote prefixes overlap or ingress paths differ.

EXP-064 satisfies that Purpose by carrying only the Profile-derived host behavior class. However the current Statement literally requires an unambiguous packet association with the already-selected **Profile** across the explicit host boundary.

With shared behavior lanes, multiple Profiles with identical host behavior intentionally become indistinguishable on the host side. Full Profile identity remains preserved inside the managed stack for established-flow return affinity, but it is not reconstructed on the host.

Therefore EXP-064 cannot yet be selected as production architecture without human review of this Requirement.

Current registry state is deliberately:

```text
EXP-063: FAIL / not_selected
EXP-064: PASS / pending_decision
```

No requirement wording was silently changed.

## Proposed requirement-resolution question

The next discussion must decide whether `VPNG0004-R4.R6.R1.R6.R1` really intends:

1. **literal Profile identity continuity across the host boundary**, even when two Profiles require exactly the same host behavior; or
2. **behavior-equivalent continuity**, sufficient to prove that the host applies exactly the return/NAT behavior derived from the selected Profile and never confuses Profiles whose required host behavior differs.

If (2) is accepted, the existing Statement should be revised/clarified before EXP-064 disposition becomes `selected`.

If (1) is retained, EXP-064 remains technically useful but insufficient, and another carrier preserving full Profile identity is required.

## Suspicious requirements

Previous open semantic suspects remain:
- `VPNG0002-R2.R1.R2`;
- `VPNG0002-R2.R2.R2`.

Previous placement/Purpose suspects remain:
- `VPNG0002-R2.R1.R1`;
- `VPNG0002-R2.R1.R2`;
- `VPNG0002-R2.R2.R1`;
- `VPNG0002-R2.R2.R2`;
- `VPNG0002-R2.R3.R3`;
- `VPNG0002-R2.R3.R3.R1`;
- `VPNG0002-R2.R3.R1.R1`;
- `VPNG0002-R2.R5.R1`.

New semantic/abstraction suspect raised by this cycle:
- `VPNG0004-R4.R6.R1.R6.R1` — its Purpose requires non-confusion of host-side gateway-NAT behavior, while its Statement may overconstrain the lower mechanism to literal cross-boundary Profile identity.

This is a discussion item, not an automatic rewrite.

## Requirement-state inventory

No new requirement state transition was made.

- resolved `decomp` occurrences: six, unchanged;
- pending `decomp`: none;
- active `unreal`: none;
- active `broken`: none;
- active `[rejected_closure]`: none.

## Remaining gateway-NAT gates

If behavior-equivalent continuity is accepted:
1. set EXP-064 disposition to `selected`;
2. add an authoritative observable structural route role for behavior-lane defaults;
3. compose lane-default routes and initial inbound Profile-table selection into one guarded structural policy generation;
4. implement authoritative host behavior owner observation/convergence;
5. wire the three additional alpha behavior lanes plus the primary lane into startup/reconcile/cleanup;
6. add end-to-end production-shaped evidence.

Until then, alpha may contain pure/infrastructure capabilities but must not claim Profile `+snat` is materialized.

## Branch / PR

Branch:
`ng3-design-cycle-20261118-continuation-rule-and-next`

Draft PR:
#27, stacked on `ng3-design-cycle-20261118-stack-affinity-integration`.

Unmerged.
