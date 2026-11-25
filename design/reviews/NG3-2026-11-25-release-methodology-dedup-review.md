# NG3 release methodology deduplication review — 2026-11-25

**Review unit:** release-methodology ownership cleanup and stable-document identity cleanup  
**Reviewed source head:** `db788897bacedb43c521595a182d133be9751db3`  
**Governing requirements:** `VPNG-D001-R3*` and current documentation/traceability conventions  
**Evidence:** `EV-00260`

## Verdict

**PASS — general release methodology is now release-scope driven rather than technology-specific, current normative documents no longer carry stale cycle/version identity, and the already frozen 0.1.0 release records remain byte-for-byte outside this unit.**

## Findings and dispositions

### F1 — general release methodology duplicated one release's integration list

**Disposition:** accepted / fixed.

PROJECT-CONVENTIONS §10.4 previously named WireGuard, OpenConnect and L2TP as mandatory NG3
Release-1 walkthroughs. The general rule now derives the concrete mandatory walkthrough set
from the approved `release/<version>/RELEASE-SCOPE.md` together with the published
administrator/user documentation of that release.

The methodology still requires every release-specific documented integration/example path and
mandatory operator capability to be executed end to end; it no longer owns product technology
names.

### F2 — 0.1.0 must not be silently rewritten to implement the methodology cleanup

**Disposition:** accepted / fixed during review.

An initial draft attempted to move the concrete three-integration list into the current-tree
0.1.0 RELEASE-SCOPE. The release QA correctly failed because touching the frozen release
surface exposed divergence between current requirements and the historical project snapshot.
Repository inspection confirmed that `release/0.1.0` is frozen at reviewed candidate
`8055eb0dd655de91a7a93e77669e426493dbc6e6` and no `v0.1.0` publication tag exists yet.

The draft release-record mutation was therefore reverted exactly. Final source diff contains no
`release/0.1.0/*` file. For that candidate, the approved scope's release-supported integration
boundary plus its published DEPLOYMENT.md already identify the WireGuard, OpenConnect and
L2TP/PPP walkthroughs that QA executed.

PROJECT-CONVENTIONS now states explicitly that frozen candidate-bound release records/project
snapshot are historical state and are not synchronized with later main development; a
scope/record change affecting candidate meaning requires a new candidate SHA and applicable
QA/review.

### F3 — current requirements carried a historical development-cycle identity

**Disposition:** accepted / fixed.

The current requirement tree is now headed as the current normative NG3 requirement tree,
links its normative model and current architecture, and no longer names the obsolete
`ng3-research-20261120-...` cycle or calls itself a design-cycle draft.

### F4 — stable architecture named a concrete release version

**Disposition:** accepted / fixed.

The A.008 runtime-observability coverage statement no longer says
`Release-1 / 0.1.0`; it describes the current Release-1 architecture without embedding a
specific release version. Release-specific historical identity remains in release records.

### F5 — projectholder terminology drifted in current governing documents

**Disposition:** accepted / fixed.

Current PROJECT-CONVENTIONS and requirements now use `projectholder` rather than
`project holder`, `project-holder` or `владелец разработки` for the same decision actor.
Historical review/release snapshots were not rewritten.

### F6 — recurring drift needs a mechanical guard

**Disposition:** accepted / fixed.

The architecture/requirements consistency suite now rejects:
- stale current `**Cycle:**` / `design-cycle draft` requirement headers;
- concrete `Release-N / x.y.z` or `release/x.y.z/` identity in stable architecture;
- WireGuard/OpenConnect/L2TP names inside general §10.4 release methodology;
- noncanonical projectholder variants in current PROJECT-CONVENTIONS/requirements.

## Evidence

- initial cleanup draft: `b904631856622399fbb577786557381ef961c80e`;
- frozen-record restoration: `b329a19c2bc94250b4a8a0b3a4781afc8ef76ac7`;
- regression guards: `9a342df0f43dc0728a7490d37e93fca9bacde58f`;
- explicit frozen-record ownership clarification:
  `db788897bacedb43c521595a182d133be9751db3`;
- draft run `45595367549`: unit `139139901655` PASS; release job
  `139139903264` FAIL usefully on stale frozen project snapshot after the draft release-record
  mutation;
- corrected run `45595690581`: unit `139141146853` PASS and
  release-0.1.0 deployment job `139141147878` PASS;
- final docs-only head lineage run `45595865021` — PASS.

## Remaining scope

The component-level `Covers:` and §2.10 `Requirements:` label vocabulary remains a separate
possible terminology cleanup; it is not needed for correctness after EV-00250's typed
structured coverage gate. R8.R6 product/runtime work is also unaffected by this process unit.
