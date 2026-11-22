# VPN-GATE NG3 — development milestones

This log records **major verified steps** in the active NG3 lineage, not individual commits,
reviews, experiments or transient implementation details. Requirements, architecture and
evidence remain authoritative in their own artifacts.

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

The sequential architecture restructuring is complete. `design/NG3/structured-architecture.md`
is now the single current NG3 architecture source for component/API/interaction contracts and
requirement closure. The former flat `design/NG3/architecture.md` has now been reduced to a
tombstone; its last full body remains available in Git history at
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
