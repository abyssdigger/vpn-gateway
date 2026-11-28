# VPN-GATE NG3 — development milestones

This log records **major verified steps** in the active NG3 lineage, not individual commits,
reviews, experiments or transient implementation details. Requirements, architecture and
evidence remain authoritative in their own artifacts.


## 2026-11-28 — Managed Device reclaim activated in the verified development candidate

The #41 normal lifecycle uses domain-wide `managed_reclaim = "careful" | "strict"`
(default careful). It separates structural demand, retained/retiring/deferred decisions and
exact realization eligibility, preserves mandatory reserve on exact lifecycle capacity,
and replaces legacy ordinary-GC authorization with dependency-confirmed exact retirement
and non-recursive F2 recovery. Current operator status and paired EN/RU documentation
describe this distinction.

The implementation/test baseline passed integrated verification (EV-00310); [independent
terminal acceptance of #41](https://github.com/abyssdigger/vpn-gateway/issues/41#issuecomment-7239133255) is recorded at `52c2da248269b42ac1be757981a3a8fbfe488dc7`.
The separate [independent #48 closure review](https://github.com/abyssdigger/vpn-gateway/issues/48#issuecomment-7239178657)
accepted architecture closure of R7.R4/R1/R2; final #41 documentation reconciliation and
local component materialization accounting are recorded in EV-00310. No released 0.1.0 capability
or main publication is implied.


## 2026-11-25 — Generalized managed-WireGuard recovery requirement family closed

The complete `VPNG-U001-R1.R3.R8*` family is now accepted as architecture-closed. The
current implementation supports multiple Profile-derived recoverable groups on one managed
WireGuard interface, independent group owners, per-peer technical checks, optional group
end-to-end checks, group-local ordinary stickiness/reserve failback, exact confirmed
`AllowedIPs` convergence including no-owner state, and ownership-generation invalidation of
stale Profile availability evidence without requiring a common-interface restart.

Closure rests on the already accepted generalized configuration, D.002/D.003 runtime and
kernel evidence through `EV-00140`–`EV-00280`. No new WireGuard mechanism is introduced by
this milestone; it records that the previously implemented and reviewed cross-component R8
behavior now has no unresolved architecture decision in its current scope.


## 2026-11-25 — Managed Device lifecycle requirement branch closed

The explicitly managed Device lifecycle under `VPNG-U001-R1.R3.R7*` now has accepted
requirement closure. The current configuration contract, A.012 `ManagedDeviceManager` and
D.001 managed WireGuard Adapter jointly cover explicit management opt-in, preservation of
externally prepared Devices, structural-demand-driven presence, desired/confirmed generation
separation, confirmed start/stop/restart behavior, secret-sensitive generation changes and
dependency-safe teardown.

The closure review found no remaining product or architecture decision inside the R7 scope.
Packet-triggered activation and idle-time disconnect remain deliberately outside R7.R3 rather
than hidden unfinished Device-manager work. The existing implementation/evidence in
`EV-00070`, `EV-00080` and `EV-00090` remains the acceptance basis; no duplicate lifecycle
implementation was added.


## 2026-11-25 — WireGuard ownership changes now invalidate stale Profile availability evidence

Generalized managed-WireGuard recovery now closes the remaining R8.R6 currentness gap. The
runtime first confirms the complete shared probe plane, then reconciles D.002 group ownership,
then binds A.007 availability context to the resulting Device-wide ownership generation before
accepting fresh Profile evidence or converging effective route priority.

The dependency is explicit: ordinary/non-D.002 paths remain independent, an applicable but
unconfirmed WireGuard ownership realization cannot contribute current remote evidence, and a
confirmed no-owner state still has a valid generation. Changing ownership behind the same
`LogicalPathId` and unchanged `wg0` ifindex invalidates previous A.007 confirmation without
conflating that evidence with A.004 routing stickiness. Runtime evidence is recorded as
`EV-00280`; unchanged-interface split ownership remains established by `EV-00190`.


## 2026-11-25 — Explicitly managed Device base lifecycle materialized

Release-1 runtime now accepts canonical `managed_vpn` intent and composes A.012 over the
production D.001 WireGuard Adapter. Managed base realization is converged after creation of the
Private network and before fresh VPN-path observation, is rechecked before normal dependent
reconciliation, and publishes desired/confirmed generation truth into A.008.

Shutdown now has an explicit ownership order: forwarding is contained, product-owned
payload/return-affinity dependencies are confirmed removed, A.012 confirms managed Device
absence, and only then may A.001 destroy the Private network. Failure to prove dependency
release or managed absence leaves teardown unstarted rather than manufacturing lifecycle
success. Kernel evidence is recorded as EV-00090. WireGuard peer selection/shared-prefix
ownership remains the separate R8 D.002/D.003 frontier.


## 2026-11-24 — Release scope gate corrected; full Protective mode materialized

The first 0.1.0 publication-preparation attempt is explicitly failed because it had no prior
approved release-specific projectholder scope and therefore incorrectly treated the
`VPNG-U004-R5.C1` omission as available. `release/0.1.0/RELEASE-SCOPE.md` is now the
approved Release-1 contract: 0.1.0 does **not** exercise that omission and requires full
Protective mode.

A.011 now has supported root-local operator/automation enter/leave/status control, source-scoped
requests, independent finite-cadence fresh audit/repair, serialized fresh normal-state
confirmation before final leave, and fail-closed retention after unsuccessful leave. Linux
end-to-end evidence blocks ordinary-boundary input/output and VPN-path forwarding while keeping
runtime objects intact; installed-bundle QA additionally proves enter/block, drift repair,
safe leave, failed-leave retention, recovery release and unchanged WireGuard/OpenConnect/L2TP
payload/lifecycle behavior.


## 2026-11-23 — Release-1 / 0.1.0 candidate prepared and deployment-validated

The first actual release candidate now has canonical version `0.1.0`, a self-contained source
bundle, English deployment documentation, and release-version publication through the supported
JSON and compact-text current-status surfaces.

The generated bundle was installed from its archive in a Debian 13/systemd QA environment and
passed real payload/lifecycle checks with WireGuard, OpenConnect, and L2TP/PPP. The persistent
QA record is `release/0.1.0/QA-REPORT.md`; the version-specific fulfillment review is
`design/reviews/NG3-0.1.0-2026-11-23-release-fulfillment-review.md`.

At that time the candidate was considered ready for a separate projectholder release decision;
the 2026-11-24 release-scope correction later invalidated that readiness verdict as publication
basis because no approved release-specific scope had preceded the attempt. No `v0.1.0` was
published from it.


## 2026-11-23 — Release development and implementation fulfillment made explicit

NG3 now has an accepted release-based development branch under `VPNG-D001-R3*`. Actual
product releases must have a project release-numbering/accounting/publication method, a
source-state identity, a prerelease requirement-fulfillment review and a separate subsequent
release decision. The current pre-first-release development state remains intentionally free
of release-candidate/version discipline under `VPNG-D001-R3.C1`; no `VERSION` file or
actual release candidate is created by this change.

Structured architecture now records `full`, `partial` or `none` on every component
requirement edge. This exposes the previously coarse A.011 state precisely: supported
operator/control wiring is incomplete for `VPNG-U004-R5/R5.R1`, and the finite-cadence
periodic confirmation required by `VPNG-U004-R5.R4` is not materialized. A.008 also records
release-version status publication as `none` until an actual release is prepared.

Canonical component headings now use bracketed IDs such as `[A.011]`; traceability guards
check Annex placement, per-edge materialization state and complete component-to-file edges.
The same block repaired C.010 Annex placement, stale Annex-C notation, missing manifest edges
and shared E.002/E.004 host-routing trace. Acceptance review:
`design/reviews/NG3-2026-11-23-release-fulfillment-methodology-review.md`.

## 2026-11-22 — Aggressive host-routing continuous Manager materialized

E.003 `AggressiveHostRoutingManager` now has production continuous ownership. Initial
activation requires a confirmed E.004 composite postcondition; a finite-cadence audit loop
then re-observes/reconciles through E.004 and escalates unconfirmed authority through its own
source-scoped A.011 request. Confirmed recovery clears only that source and remains subject
to STACK's normal-release precondition.

The final implementation also seals the E.003 -> E.004 component boundary behind an
`AggressiveHostRoutingEnforcer` facade and serializes A.011 public state/mutations for the
new concurrent request source. Release-1 configuration remains peaceful-only under
`VPNG-U001-R5.R2.C1`. E.003 is no longer `<partial>`; together with the previously
materialized E.004 this completes the accepted aggressive host-routing implementation block.
Review:
`design/reviews/NG3-2026-11-22-aggressive-host-routing-manager-implementation-review.md`.

## 2026-11-22 — Aggressive host-routing Enforcer materialized

E.004 `AggressiveHostRoutingEnforcer` now has production implementation. Activation
freshly confirms the independent escape guard before aggressive routing capture and accepts
success only after a new owner/RPDB/guard observation. Earlier foreign RPDB policy is no
longer invisible: it makes authority unconfirmed while the escape guard keeps managed
traffic fail-closed.

The production guard incorporates EXP-085 full-tunnel exemptions for host-local delivery and
managed-boundary return traffic. Deactivation reconfirms the guard, removes routing capture,
verifies that removal and only then releases the guard. E.004 is no longer `<partial>`.
Review:
`design/reviews/NG3-2026-11-22-aggressive-host-routing-enforcer-implementation-review.md`.

## 2026-11-22 — Protective mode Manager core materialized

A.011 now has a production source-scoped Manager core composed with C.010. Independent
operator/automation and aggressive-failure sources cannot clear one another; the final source
cannot release containment until the normal release precondition is confirmed. A failed or
unconfirmed gate release immediately attempts safety re-containment and distinguishes
confirmed re-close from an explicit safety-reclose failure.

A.011 remains `<partial>`: periodic runtime scheduling, supported operator/control wiring
and restart semantics for outstanding requests are intentionally not claimed by the callable
core. Review:
`design/reviews/NG3-2026-11-22-protective-mode-manager-core-implementation-review.md`.

## 2026-11-22 — Protective payload gate materialized

Accepted architecture component C.010 `ProtectivePayloadGate` now has production Python
implementation. The bounded Enforcer strictly observes one dedicated owner-marked nft table,
mutates only absent or proven-owned state, repairs owned drift by one nft transaction and
freshly verifies the resulting postcondition. Conflicting/foreign state is refused rather
than adopted.

The live C.010 integration passed enable, owned-drift repair, disable and foreign-conflict
refusal while the same job retained EXP-083 and C.005 evidence. C.010 is no longer
`<partial>`; A.011, E.003 and E.004 remain partial pending their own implementation.
Implementation review:
`design/reviews/NG3-2026-11-22-protective-payload-gate-implementation-review.md`.

## 2026-11-22 — Aggressive routing and protective architecture accepted

The previously reviewed aggressive/protective candidate was simplified and materialized into
the current Space/Annex architecture. Aggressive ownership is now E.003
`AggressiveHostRoutingManager` plus child E.004 `AggressiveHostRoutingEnforcer`; the
EXP-084 escape guard remains an independently verifiable Enforcer-owned state rather than a
separate component. Protective mode is A.011 `ProtectiveModeManager` plus C.010
`ProtectivePayloadGate`.

Protective requests are source-scoped so operator/automation and aggressive-failure
escalation cannot clear one another's protection. The final source may release the gate only
after the normal release precondition is freshly confirmed. The accepted architecture review
is `design/reviews/NG3-2026-11-22-aggressive-protective-architecture-acceptance-review.md`.

All 11 aggressive/protective nodes moved from `pending_closure` to `closed`. Current
normative inventory is 213 nodes: 200 `closed`, 10 `postponed`, 3 `permanent`, and
zero `open`, `pending_closure` or `rejected_closure`. This milestone is architecture
closure only; production implementation remains a separate development block.

## 2026-11-22 — Aggressive routing and protective mode re-entered and researched

The postponed aggressive host-routing and administrative protective-mode branches were
explicitly re-entered for a focused CDC. EXP-081 demonstrated that the former EXP-074-only
authoritative-routing closure was incomplete: an earlier foreign RPDB rule can bypass the
managed dispatch while the old owner still reports its own state exact. The old closure was
therefore rejected during research; EXP-074 remains valid narrow evidence against competing
routes inside host table `main`.

EXP-083 selected a simpler protective lower candidate: one dedicated Private-network nft
table can block ordinary-boundary INPUT/OUTPUT and all IPv4 FORWARD traffic while preserving
runtime topology. EXP-084 selected an independent aggressive escape guard that blocks a
managed destination if ordinary host policy redirects it to a non-managed egress, making
fail-closed safety independent of drift-detection latency. The requirements were refined so
continuous aggressive observation includes relevant competing policy, aggressive local
containment is separated from broader protective escalation, and protective mode now has
explicit control, traffic, state-preservation and continuous/safe-leave descendants.

The accepted research direction is now materialized as authoritative-architecture §2.11,
explicitly marked as a **pending closure candidate** rather than current Residents/component
specs. All 11 affected aggressive/protective nodes therefore have exact architecture
references and are `pending_closure`; no implementation or final architecture acceptance is
claimed. Current inventory is 213 normative nodes: 189 `closed`, 11 `pending_closure`,
10 `postponed`, 3 `permanent`, and zero `open` or `rejected_closure`.
The research and candidate reviews are
`design/reviews/NG3-2026-11-22-aggressive-protective-research-review.md` and
`design/reviews/NG3-2026-11-22-aggressive-protective-architecture-candidate-review.md`.

## 2026-11-22 — Requirement status made mandatory and permanent principles classified

The Requirement/Constraint model now uses one mandatory `requirement status` enum:
`open | pending_closure | closed | rejected_closure | postponed | permanent`. Missing status
is no longer an implicit open state. `permanent` identifies obligations that remain applicable
to current and future architecture and therefore cannot be finitely architecture-closed; the
status is explicitly non-inherited.

Current NG3 inventory is 190 `closed`, 14 `postponed`, 3 `permanent`, and zero
`open`, `pending_closure`, `rejected_closure` or statusless nodes. The permanent nodes
are `VPNG-D001`, `VPNG-M001` and `VPNG-M001-R3.R1`; weak-device suitability parent
`VPNG-M001-R3` is explicitly postponed with the Raspberry Pi 2 resource-evidence branch.
Traceability tests now enforce mandatory/mutually exclusive status, closure references and
postponement records. The integrity and current permanent-conformance review is
`design/reviews/NG3-2026-11-22-requirement-status-permanent-integrity-review.md`.

## 2026-11-22 — Current requirements closure frontier cleared

The remaining 17 `pending_closure` Requirement/Constraint nodes were re-reviewed against the
current authoritative architecture and executable evidence and moved to `closed`. The closure
covers Device-scoped NAT/firewall policy, Profile source identity, canonical configuration,
peaceful host-routing automation, packet matching, availability criterion aggregation,
priority-only reorder, established-flow return affinity and managed-policy non-interference.

No postponed capability was re-entered or silently narrowed. The current normative inventory is
therefore 190 `closed`, 0 `pending_closure`, 13 `postponed`, 0 `rejected_closure`, plus
the four intentionally statusless open roots/frontier nodes. The acceptance record is
`design/reviews/NG3-2026-11-22-remaining-pending-closure-review.md`; the reviewed executable
baseline is `NG3 Python` run `45027427711`, which passed all 21 jobs on the same main tree.

## 2026-11-22 — Operational logging and administrator runbook verified

The alpha now has configurable operational logging with canonical
`error | warning | info | debug` threshold semantics, normalized component log tags,
transition-driven INFO/DEBUG emission and standard journald priority preservation. Current
status remains a separate truth surface rather than being reconstructed from logs. Developer
execution tracing is explicitly separate and remains blocked pending its own contract.

A concise `design/NG3/admin-runbook.md` now covers installation, Device/Profile
configuration, supported OpenVPN/systemd preparation, start/stop/restart, runtime status,
traffic verification, monitoring and operator reactions to log severities. EXP-051 executes
the material runbook path on Debian 13/systemd, including VPN-only endpoint regeneration and
journal-priority filtering.

## 2026-11-22 — Structured architecture becomes authoritative

The sequential architecture restructuring is complete. `design/NG3/architecture-ng.md`
is now the single current NG3 architecture source for component/API/interaction contracts and
requirement closure. The former flat `design/NG3/architecture.md` has now been removed from the current tree;
its last full body remains available in Git history at
`38607e247f39a87a361a4541e3dace6585c8d52a`. Residual material was audited: the only
architecture-level item not already represented elsewhere, the deliberate omission of
unrequired generic machinery, was transferred to structured architecture §2.9.4.

## 2026-11-22 — Development and operational cost requirements separated

Engineering requirements are now classified by the lifecycle cost they optimize rather than
by who implements them. Development-cost requirements moved from the former `VPNG-U007` tree
under the owner-imposed `VPNG-D001` root; lifecycle/observability requirements moved from the
former `VPNG-U005`/`VPNG-U006` roots under the owner-imposed operational-cost `VPNG-M001`
root. Functional/user-facing VPN behavior remains in the `VPNG-U001`–`VPNG-U004` range.

The previously preliminary weak-device/resource-efficiency expectation is now normative under
`VPNG-M001-R3`. The long-requested compact human current-state report is now normative under
`VPNG-M001-R2.R2`, with Devices/Profiles sections, four-space hierarchy, numbered current
effective path order and normalized availability wording. Its architecture is separated into
the existing truthful `RuntimeStatusAgent` snapshot and a pure
`RuntimeStatusTextRenderer`; the concrete delivery path remains replaceable. The installed
alpha now publishes this view atomically as `/run/vpn-gate-alpha/status.txt` beside the JSON
snapshot; EXP-051 proves zero-path, first-path and VPN-endpoint-recreation updates, while unit
evidence proves truthful unknown state and independent per-path availability rendering.

Because NG3 is still alpha, the requirement model now permits project-holder-authorized ID
migration with complete current trace remapping. Historical review/research/experiment
records retain their original IDs and carry migration notes to current IDs; removed nodes
without direct successors retain their original compact-form wording.

## 2026-11-20 — Core host-network ownership boundary separated from routing helpers

Core VPN-GATE forwarding is now explicitly independent from ordinary-host routing ownership:
an administrator may provide equivalent host integration manually, while Release 1 provides a
configuration-disableable peaceful lifecycle helper for routine host-route setup/cleanup.
Authoritative continuous host-routing ownership is a separate postponed aggressive capability;
EXP-074 now closes only its narrow authoritative-routing child. Administrative payload
containment remains an independent postponed safety capability. The authoritative host-routing
owner is retained only as executable aggressive-helper evidence and has been detached from the
default alpha path. Release 1 now separates helper scope from ownership policy:
`helper_routing_interfaces = ":none"` is the non-invasive default, with explicit
`:local`, `:external`, `:any` and exact-ingress selection, while
`helper_routing_policy = "peaceful"` is the Release-1 default/only policy. EXP-077 retains
main-first and non-destructive lifecycle evidence, EXP-078 proves scoped dispatch, and EXP-079
hardens STACK-origin no-recapture with an absolute RPDB bypass. Explicit non-default
administrator routes remain stronger inside the selected helper scope, while EXP-080-backed
selector-paired preserve+dispatch rules leave administrator RPDB ordering outside that scope
unchanged. There is no periodic peaceful host-route ownership.
The host-routing helper is also explicitly outside the automatic Rust production cutover:
its Python implementation may remain after the first release, and moving that helper to Rust
requires a separate project-holder decision rather than following automatically from the
core runtime migration.

The same cleanup removed the redundant zero-path safety child that had encoded host
`ambient/main` fallback into the requirement tree: Profile persistence, valid concrete-path
membership and fail-closed managed forwarding are now traced to their existing independent
requirements, while ordinary-host routing remains outside that core safety promise.

Recovery scope was also narrowed so `VPNG-U005-R5.C1` (moved to `VPNG-M001-R1.R1.C1`) limits mandatory automatic
forensic/adoption behavior after unsupported root/admin intervention without acting as a
second blanket safety root. Fail-closed/readiness reactions now trace to the concrete
invariant and its existing safety/lifecycle requirements.

Onboarding acceptance evidence was likewise separated from its first concrete Linux
realization: `VPNG-U001-R1.R3.C1.R1.R1` now requires reproducible proof of the published
administrator onboarding contract without embedding managed-domain placement, logical-path
binding or forwarding mechanisms in the Requirement itself. Those checks remain independently
required where their own R/C apply to the selected integration.

External VPN runtime lifecycle ownership was separated from administrator provisioning:
the former nested systemd-specific constraint is now a sibling first-release constraint with
a mechanism-neutral lifecycle-integration compensation requirement. Policy-neutral VPN
configuration documentation moved under the administrator onboarding contract, while
client-side VPN transport/control intent moved to the Device transport-policy branch.
Systemd service/dependency details remain the selected Release-1 Linux architecture rather
than requirement semantics.

## 2026-11-19 — Project governance model consolidated

Project-wide development rules were refactored so repository authorization, CD cadence,
review outcomes, development blocks/snapshots, declarations/deferrals, experiment evidence,
language policy and changelog ownership have explicit subject ownership and cross-references.
CD timing
now starts from real wall-clock cycle start rather than first-commit time, and failed commit
publication is a mandatory stop condition.

## 2026-11-19 — Gateway-SNAT semantic blocker removed and behavior lanes materialized

The ordinary-side gateway-SNAT requirement was restated in observable behavioral terms and
accepted without requiring Profile identity to cross the host boundary. EXP-064 fixed
host-behavior lanes were selected; managed-stack lane routing and an authoritative host nft
behavior owner were materialized. Full alpha lifecycle wiring and removal of the `+snat`
fail-fast remain later implementation/evidence work.

## 2026-11-19 — Rust production-boundary parity established for availability state

The Rust production boundary was introduced without changing current alpha behavior and then
extended across adjacent pure availability contracts: confirmation, effective-order
calculation and bounded active-path projection. Python remains the executable reference while
the safe-Rust replacement surface grows behind parity evidence.

## 2026-11-19 — Continuous availability path assembled in the alpha

The Release-1 ICMP availability path was connected end to end from canonical configuration
through probe policy, current physical observation, bounded confirmation, effective route
ordering and runtime status. EXP-068 then supplied accepted real two-path failover and sticky
recovery evidence; descendant workflow evidence also accepted the multi-subject runtime
semantics.

## 2026-11-18 — Selected host-boundary return handling integrated

The executable alpha integrated the selected host bootstrap, default stateful return and
explicit `+route-return` path under one lifecycle with runtime drift containment and owned
cleanup.

## 2026-11-18 — Live runtime status integrated

The executable alpha gained a live current-state projection independent from the temporary
JSON renderer. Runtime status composes authoritative controller state rather than creating a
second state owner.

## 2026-11-17 — VPN server publication integrated into the NG3 runtime

Canonical Device `publish_vpn_server` was materialized in the reference alpha/beta runtime
with owner-scoped host publication, fail-closed overlap validation, external TCP evidence and
owned cleanup.

## 2026-11-17 — First functioning NG3 alpha

The first installed systemd NG3 alpha transferred payload through an independently managed
OpenVPN instance while the controller remained live, detected VPN endpoint replacement and
reconciled current policy without requiring its own restart.

## 2026-11-17 — Clean active NG3 lineage

The active `main` was established as an NG3-only development line. Historical RC and NG1/NG2
material remains on `legacy-main-rc` and `legacy-main-ng1-2`; the former mixed NG3 line
remains on `legacy-main-ng3`. Active-line hygiene prevents legacy payload from silently
reappearing.

---

The previous active-line changelog is preserved verbatim as
[CHANGELOG-OLD.md](CHANGELOG-OLD.md). The substantially longer earlier RC/NG1/NG2
development log remains available on `legacy-main-ng1-2:CHANGELOG.md`; historical branches,
rather than this milestone log, remain the source for detailed legacy chronology.
