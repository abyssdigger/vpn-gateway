# NG3 evidence index

**Status:** normative stable evidence-address registry  
**Architecture:** `design/NG3/architecture-ng.md`

Evidence IDs are stable addresses. New top-level entries normally advance by 10
(`EV-00000`, `EV-00010`, ...); intermediate values may be inserted later without
renumbering existing references.

Architecture references the EV ID. Ephemeral CI run IDs, commit SHAs and concrete experiment
artifacts stay inside the EV entry or its linked review/result artifact.

## EV-00000 — lifecycle decomposition and implementation-trace baseline

**Status:** accepted  
**Scope:** decomposition of managed-network lifecycle into environment / managed-L3 boundary /
ordinary-side portal; independent host publication Adapter; initial bidirectional
architecture-to-code marker discipline.  
**Review:** `design/reviews/NG3-2026-11-21-partial-decomposition-lifecycle-review.md`  
**Reviewed implementation baseline:** `b35095144ceffa74265ce3b2e34a1680546903f2`  
**Executable evidence:** GitHub Actions `NG3 Python` run `44932489415` — PASS.  
**Stable architecture snapshot:** Main snapshot 151,
`2073808bc1ba61af9d79bdac1d97fccb9319fcf6`.

This entry preserves the concrete historical evidence without requiring stable architecture
text to depend on the workflow provider's run identifier.



## EV-00010 — lower-boundary roles and complete bidirectional traceability

**Status:** accepted  
**Scope:** reusable lower-boundary applicability decision; role-correct Driver/Reader/Backend
classification; exact-contract nft Reader reuse; complete closed requirement -> structured
architecture entry-point invariant; structured production-runtime language boundary.  
**Review:** `design/reviews/NG3-2026-11-21-lower-boundary-reuse-trace-cdc.md`  
**Reviewed implementation baseline:** `f2e045285510c8d202db95efef450811bfcdfa87`  
**Executable evidence:** GitHub Actions `NG3 Python` run `44949136760` — PASS,
21/21 jobs; unit suite 790 tests PASS.  
**Trace invariants:** 144/144 closed Requirement/Constraint IDs have a structured architecture
entry point; 109/109 production Python units are present in the implementation trace manifest.

The evidence confirms that the terminology/reuse comb did not change required network
behavior and that the completed traceability rules are mechanically enforced.


## EV-00020 — private peer observation and transport-provenance separation

**Status:** accepted  
**Scope:** demand-scoped observation of a point-to-point interface private/inner peer; exact
association with the current interface generation; separation of that inner peer from an
external VPN transport/server endpoint.  
**Review:** `design/reviews/NG3-2026-11-23-private-peer-path-firewall-design-review.md`  
**Executable evidence:** EXP-039 — PASS; the generic TUN address observation exposes the
private/inner peer while not providing the userspace VPN transport endpoint.

This entry is the stable evidence address for architecture that consumes the private-peer fact
without treating it as transport provenance.


## EV-00030 — protective-mode lower containment selection

**Status:** accepted  
**Scope:** feasibility and selection of the dedicated Private-network protective containment
state while preserving namespace, interfaces, routes and normal policy state.  
**Reviews:** `design/reviews/NG3-2026-11-22-aggressive-protective-architecture-acceptance-review.md`;
`design/reviews/NG3-2026-11-22-protective-payload-gate-implementation-review.md`.  
**Executable evidence:** EXP-082 — PASS / not selected two-barrier composition;
EXP-083 — PASS / selected single owned protective gate.

This entry preserves both the rejected-complexity comparison and the selected one-gate lower
mechanism behind one stable architecture evidence address.


## EV-00040 — aggressive routing authority and escape protection

**Status:** accepted  
**Scope:** authoritative host-routing verification, independent fail-closed escape protection,
activation/deactivation ordering and full-tunnel exemptions.  
**Reviews:** `design/reviews/NG3-2026-11-22-aggressive-protective-architecture-acceptance-review.md`;
`design/reviews/NG3-2026-11-22-aggressive-host-routing-enforcer-implementation-review.md`;
`design/reviews/NG3-2026-11-22-aggressive-host-routing-manager-implementation-review.md`.  
**Executable evidence:** EXP-074 — retained narrow routing mechanics; EXP-081 — accepted
negative evidence against owned-object-only authority; EXP-084 — PASS prefix-scoped escape
protection; EXP-085 — PASS full-tunnel escape-protection exemptions.

This entry is the stable evidence address for E.003/E.004 routing-authority and containment
decisions.

## EV-00050 — WireGuard same-prefix peer ownership and managed-realization boundary

**Status:** selected  
**Scope:** one WireGuard interface with multiple peers that can serve the same remote prefix;
exclusive `AllowedIPs` ownership; permanent peer-specific in-tunnel probe prefixes; runtime
owner transfer without interface restart; safe no-owner base configuration; restart reset;
fresh confirmation and generation-scoped stale-evidence rejection.  
**Reviews:** `design/reviews/NG3-2026-11-24-EXP-086-wireguard-multipeer-availability-review.md`;
`design/reviews/NG3-2026-11-24-EXP-087-wireguard-runtime-allowedips-review.md`;
`design/reviews/NG3-2026-11-24-EXP-088-wireguard-ten-peer-result-review.md`.  
**Executable evidence:** EXP-086 — PASS / ordinary Linux route priority cannot select
same-prefix peers behind one `wg0`; EXP-087 — PASS / two-peer runtime ownership feasibility;
EXP-088 — PASS / ten-peer base lifecycle, ordered failover, restart reset and
generation-scoped confirmation.

EXP-088 additionally observed one live 200-packet A-to-B transition with zero packet loss and
no third-peer payload replies. This observation is not a universal transactional-atomicity
guarantee for `wg set`; selected architecture A.012/D.001/D.002/D.003 therefore confirms
exact post-apply `AllowedIPs` state before publishing a new realization generation.

## EV-00060 — direct managed WireGuard base lifecycle

**Status:** accepted  
**Scope:** direct kernel WireGuard base realization for D.001: secret-file preconditions,
same-name foreign-object rejection, confirmed create/present/restart/absent postconditions and
technical interface ownership marker.  
**Result:** `design/experiments/EXP-089 NG3 direct managed WireGuard lifecycle/EXP-089-result-20261124.md`  
**Review:** `design/reviews/NG3-2026-11-24-EXP-089-direct-wireguard-lifecycle-review.md`  
**Executable evidence:** EXP-089 — PASS, GitHub Actions run `45467124175`, job
`138705009864`.

This entry selects the direct kernel lifecycle as the WireGuard-specific lower realization.
It does not select a universal process/service driver for daemon-based VPN integrations.

## EV-00070 — production D.001 managed WireGuard Adapter

**Status:** accepted  
**Scope:** production realization of the selected D.001 WireGuard base-lifecycle contract:
safe secret-file preconditions, explicit ownership, foreign-object rejection, confirmed
present/absent, idempotent unchanged generation, same-path secret rotation, and strict
separation from D.002-owned peer preference and mutable payload `AllowedIPs`.  
**Implementation:** `design/NG3/code/python/rou/managed_wireguard_adapter.py`.  
**Integration evidence:** `design/NG3/code/python/rou/tests/integration_managed_wireguard_adapter.py`.  
**Review:** `design/reviews/NG3-2026-11-24-managed-wireguard-adapter-implementation-review.md`.  
**Executable evidence:** GitHub Actions run `45477609885`, job
`linux-wireguard-multipeer` `138741997228` — PASS; `unit`,
`linux-alpha-smoke`, and frozen Release-0.1.0 isolation also PASS on source
`3435600145081f08275a943b1d6a20c544e8398d`.

The production integration proves that D.001 does not restart the base interface for a peer
preference reorder or for D.002-owned mutable `AllowedIPs`; a private-key change at the same
configured file path produces a new confirmed base generation and resets mutable shared-prefix
ownership through the selected absent-before-present restart.

## EV-00080 — A.012 managed Device orchestration core

**Status:** accepted / partial materialization  
**Scope:** current-only orchestration of explicit managed-Device demand over D.001: external
Devices remain out of scope; structurally demanded managed Devices request confirmed presence;
desired and confirmed base generations remain distinct; desired absence waits for explicit
dependency release; removed management remains tracked until owned absence is confirmed; D.001
failures become problem state rather than false confirmation.  
**Implementation:** `design/NG3/code/python/rou/managed_device_manager.py`.  
**Unit evidence:** `design/NG3/code/python/rou/tests/test_managed_device_manager.py`.  
**Review:** `design/reviews/NG3-2026-11-24-managed-device-manager-core-review.md`.  
**Executable evidence:** GitHub Actions run `45479580505`, job `unit`
`138748981952` — PASS on source
`eef712648e60c112e9276a865599f3e80964a240`.

This evidence does not claim runtime materialization. Alpha startup/reload/stop wiring,
dependency-release confirmation from current product policy, and A.008 publication remain
explicit follow-up work.

## EV-00090 — A.012 managed Device runtime composition

**Status:** accepted / full A.012 materialization  
**Scope:** Release-1 runtime composition of explicit managed-Device base lifecycle over D.001:
startup after Private-network creation and before fresh path observation; current
desired/confirmed generation projection into A.008; product-owned dependency release before
managed absence; and confirmed managed absence before Private-network teardown.  
**Implementation:** `design/NG3/code/python/rou/alpha_runtime.py`,
`design/NG3/code/python/rou/controller_startup.py`,
`design/NG3/code/python/rou/runtime_status.py`.  
**Integration evidence:** `design/NG3/code/python/rou/tests/integration_managed_device_runtime.py`.  
**Review:** `design/reviews/NG3-2026-11-25-managed-device-runtime-composition-review.md`.  
**Executable evidence:** GitHub Actions run `45519755877`: `unit` job
`138888449127` — PASS; `linux-alpha-smoke` job `138888449063` — PASS;
`linux-managed-device-runtime` job `138888449316` — PASS on source
`1fd69c02f3d8e3e520076dc0cdaf06343dca5fff`.

The kernel integration confirms that the A.012-created WireGuard interface is part of the first
fresh startup path observation, that A.008 receives the exact current base generation, that
owned payload/return-affinity dependencies are removed before A.012 is allowed to converge
absent, and that the managed namespace is destroyed only after confirmed managed-Device
absence. The runtime stop path deliberately does not invoke Private-network teardown when
dependency release or A.012 absence is unconfirmed.

## EV-00100 — production D.003 WireGuard peer ownership Enforcer

**Status:** accepted / full D.003 materialization  
**Scope:** exact full-state `AllowedIPs` observation and convergence for one current D.001-owned
WireGuard interface; rejection of stale interface generation or unexpected/incomplete peer set;
single complete runtime owner-state application; and fresh exact postcondition confirmation.  
**Implementation:** `design/NG3/code/python/rou/wireguard_peer_ownership.py`.  
**Unit evidence:** `design/NG3/code/python/rou/tests/test_wireguard_peer_ownership.py`.  
**Integration evidence:** `design/NG3/code/python/rou/tests/integration_wireguard_peer_ownership.py`.  
**Review:** `design/reviews/NG3-2026-11-25-wireguard-d003-peer-ownership-review.md`.  
**Executable evidence:** GitHub Actions run `45552662807`: `unit` job
`138997218110` — PASS; dedicated `linux-wireguard-peer-ownership` job
`138997218400` — PASS on source
`dbb0d80381e875b7092684eebecba5dafd69c4f3`.

The kernel integration confirms exact initial ownership by peer A, full owner-state transfer to
peer B, preservation of both permanent peer-specific probe /32 prefixes, and unchanged current
WireGuard interface identity across the transfer. D.003 does not choose a peer, publish a
peer-realization generation, or claim Profile availability; those remain D.002/downstream
responsibilities.

## EV-00110 — reusable WireGuard peer-probe lower seam

**Status:** accepted historical lower-seam evidence  
**Historical baseline disposition:** C.008 full; C.001 partial for R8 at this review baseline.  
**Current materialization superseded by:** `EV-00200`, `EV-00210`, `EV-00280`.  
**Scope:** removal of A.007 semantic-owner coupling from the physical ICMP Driver; distinct
`WireGuardPeerProbeOwner(device_id, peer_id)`; shared deterministic probe resource allocation;
peer-specific /32 route/RPDB/local-admission projection through one current path; and generic
fresh execution-precondition gating without creating a peer `LogicalPathId`.  
**Implementation:** `design/NG3/code/python/rou/icmp_probe_driver.py`,
`design/NG3/code/python/rou/network_policy_layout.py`,
`design/NG3/code/python/rou/wireguard_peer_probe_policy.py`,
`design/NG3/code/python/rou/probe_precondition.py`.  
**Review:** `design/reviews/NG3-2026-11-25-wireguard-peer-probe-seam-review.md`.  
**Executable evidence:** GitHub Actions run `45553552569`, `unit` job
`139000197586` — PASS on source
`5a2e112dc3d13880d212dd23eb62c993f612cd38`.

The tests prove that the peer-owner projection is physically equivalent to the already proven
A.007 probe route/RPDB/local-admission shape while retaining a distinct semantic owner, and
that the extracted physical ICMP context renders the same command as the legacy A.007 wrapper.
No new Linux mechanism is introduced, so separate kernel evidence is not required for this
refactor/projection seam. At this historical baseline, runtime composition of peer-probe demand
remained a D.002-dependent C.001 gap. That gap was later closed by the combined probe-plane
composition/runtime and generation-currentness work registered at `EV-00200`, `EV-00210`
and `EV-00280`; EV-00110 must not be read as the current C.001 materialization status.

## EV-00120 — D.002 WireGuard peer Manager core

**Status:** accepted / partial D.002 materialization  
**Scope:** current-only ordered peer selection, sticky current-owner behavior without automatic
failback, confirmed-owner failover, conservative current-owner local-error handling, complete
D.003 desired-state construction and peer-realization generation publication only after fresh
D.003 confirmation.  
**Implementation:** `design/NG3/code/python/rou/wireguard_peer_manager.py`.  
**Unit evidence:** `design/NG3/code/python/rou/tests/test_wireguard_peer_manager.py`.  
**Review:** `design/reviews/NG3-2026-11-25-wireguard-d002-manager-core-review.md`.  
**Executable evidence:** GitHub Actions run `45554305306`, `unit` job
`139002651040` — PASS on source
`77a4e9a53862990710314bab84ef7f0dd51446ee`.

The core evidence confirms first suitable selection in configured order, sticky retention of a
still-replying current owner, failover only after confirmed current-owner no-reply, no false
failover on current-owner local execution error, exact no-owner realization when no peer is
confirmed suitable, generation change across owner/base/interface/order context changes, and
no generation publication when D.003 is unconfirmed. The production C.001/C.008/D.003 lower
seams are separately accepted by EV-00110/EV-00100; runtime composition remains explicit
follow-up work.

## EV-00130 — confirmed D.002 WireGuard peer-probe executor

**Status:** accepted / partial D.002 runtime-composition materialization  
**Scope:** production composition from one D.002 peer identity to the already accepted C.001
exact execution precondition and C.008 physical ICMP Driver, without converting peer identity
into a Profile/path availability subject.  
**Implementation:** `design/NG3/code/python/rou/wireguard_peer_probe_executor.py`.  
**Unit evidence:** `design/NG3/code/python/rou/tests/test_wireguard_peer_probe_executor.py`.  
**Review:** `design/reviews/NG3-2026-11-25-wireguard-peer-probe-executor-review.md`.  
**Executable evidence:** GitHub Actions run `45554729474`, `unit` job
`139003923124` — PASS on source
`a3ec1d1cb2705d87883c9e9b292ac85c0f7e7b66`.

The executor refuses physical I/O unless the exact
`(WireGuardPeerProbeOwner, ICMP, probe_target, InterfaceIdentity)` key belongs to a freshly
confirmed peer-specific precondition. Owner/peer mismatch, Device/path mismatch, missing
readiness and stale interface generation are rejected before the shared physical Driver is
invoked. The Linux ICMP mechanism itself is unchanged and already covered by the C.008
evidence selected in EV-00110.

## EV-00140 — Profile-derived WireGuard group normalization

**Status:** accepted / full A.002 generalized R8 configuration materialization  
**Scope:** canonical derivation of one WireGuard recoverable group per enabled
`(Profile, managed WireGuard Device)` membership; payload bundle from
`Profile.destinations`; optional group-local ordered peer subset with `:reserve`; reuse of
a qualifying in-group Profile ICMP description without merging semantic evidence; and strict
rejection of invalid membership/peer references.  
**Implementation:** `design/NG3/code/python/rou/release1_config.py`.  
**Unit evidence:** `design/NG3/code/python/rou/tests/test_wireguard_group_config.py`.  
**Review:** `design/reviews/NG3-2026-11-25-wireguard-group-normalization-review.md`.  
**Executable evidence:** GitHub Actions run `45562870491`, unit job
`139030635335` — PASS on source
`aa26d7845435c12b164070e97377eab2693923af`.

The focused tests confirm default all-peer ordinary membership, explicit ordered subset with
group-local reserve role, typed prefix derivation, qualified Profile availability-description
reuse, and fail-closed rejection of detail for a nonmember Device, unknown/duplicate peers and
unsupported membership suffixes. Existing whole-suite tests remain green. The legacy
`shared_prefixes` field is retained only as a temporary internal bridge for the one-group
D.002 prototype and is not part of the accepted generalized configuration contract.

## EV-00150 — generalized D.002 recoverable-group Manager core

**Status:** accepted / generalized group-selection core; D.002 overall remains partial  
**Scope:** typed per-Profile WireGuard group input; independent simultaneous group -> peer
ownership; ordinary sticky ownership; group-local reserve failback; shared fresh peer-health
cache; peer-failure recovery; per-group no-owner state; complete split-group D.003 desired-state
construction; and Device-wide generation publication only after fresh D.003 confirmation.  
**Implementation:** `design/NG3/code/python/rou/wireguard_peer_manager.py`,
`design/NG3/code/python/rou/release1_config.py`.  
**Unit evidence:** `design/NG3/code/python/rou/tests/test_wireguard_peer_manager.py`,
`design/NG3/code/python/rou/tests/test_release1_config.py`.  
**Review:** `design/reviews/NG3-2026-11-25-wireguard-d002-groups-review.md`.  
**Executable evidence:** GitHub Actions run `45571166454`, unit job
`139058000826` — PASS on source
`c93b98e256ac56eb74056d111f97ab46620da9cd`.

The focused tests prove simultaneous different owners for two groups, one technical peer probe
reused within one fresh reconciliation, ordinary stickiness, reserve failback, recovery of
only groups affected by a failed peer, coexistence of a no-owner group with another confirmed
group, invalidation on current-owner local error, and no generation publication on failed
D.003 confirmation. The old `shared_prefixes` bridge is removed; D.002 receives the accepted
A.002 typed group contract directly. Optional group-endpoint checking is deliberately rejected
before I/O until its separate semantic owner/precondition is materialized.

## EV-00160 — owner-scoped shared probe-plane readiness

**Status:** accepted / C.001 scoped-readiness lower seam  
**Scope:** read-only readiness projection from one fresh physical snapshot, one complete accepted
probe union and one requested semantic-owner subset; accepted sibling state is permitted,
requested missing state blocks, sibling missing state does not block, shared physical
probe-local rules can confirm multiple semantic owners, and unattributed reserved probe state
remains fail-closed. Legacy whole-scope readiness semantics remain unchanged.  
**Implementation:** `design/NG3/code/python/rou/probe_precondition.py`.  
**Unit evidence:** `design/NG3/code/python/rou/tests/test_probe_precondition.py`.  
**Review:** `design/reviews/NG3-2026-11-25-probe-owner-scoped-readiness-review.md`.  
**Executable evidence:** GitHub Actions run `45572212707`, unit job
`139061480440` — PASS on source
`ff608b8b6fda124dfd8e98b0a365c2f5faad066b`.

The focused tests prove that exact A.007 and WireGuard peer semantic owners can each receive a
confirmed scoped precondition from the same full physical union; a missing sibling does not
block the requested owner while the unchanged legacy whole-union verifier still reports that
missing sibling; a missing requested selector blocks; and an additional reserved RPDB object
outside the complete accepted union blocks every scoped owner. One physical nft INPUT/OUTPUT
pair simultaneously satisfies both semantic owners when their lower physical identity is
identical.

## EV-00170 — WireGuard recoverable-group probe lower seam

**Status:** accepted / full C.001 lower contribution to `VPNG-U001-R1.R3.R8.R3.R1`  
**Scope:** stable `WireGuardGroupProbeOwner(profile_id, device_id)`; deterministic shared
probe-resource allocation; group endpoint route/RPDB/local-admission projection; owner-scoped
readiness compatibility; and production execution through the existing C.008 physical ICMP
Driver only after an exact confirmed group context.  
**Implementation:** `design/NG3/code/python/rou/network_policy_layout.py`,
`design/NG3/code/python/rou/bound_probe_policy.py`,
`design/NG3/code/python/rou/wireguard_group_probe_policy.py`,
`design/NG3/code/python/rou/wireguard_group_probe_executor.py`.  
**Unit evidence:** `design/NG3/code/python/rou/tests/test_network_policy_layout.py`,
`design/NG3/code/python/rou/tests/test_wireguard_group_probe_policy.py`,
`design/NG3/code/python/rou/tests/test_wireguard_group_probe_executor.py`,
`design/NG3/code/python/rou/tests/test_probe_precondition.py`.  
**Review:** `design/reviews/NG3-2026-11-25-wireguard-group-probe-seam-review.md`.  
**Executable evidence:** GitHub Actions run `45575745380`, unit job
`139073253482` — PASS on source
`5816f965f666fa3296c3dcf40a89681de98cf75d`.

The tests prove that the group owner participates in the same deterministic collision-free
probe allocation as Profile and peer owners, projects a physically equivalent ICMP lower
contract without creating a new logical path, is accepted by the scoped-readiness verifier,
and cannot execute physical I/O without the exact confirmed
`(group owner, ICMP, group target, InterfaceIdentity)` context. The executor rejects owner /
group / Device mismatches and an out-of-group target before I/O. Peer and group projection
share `bound_probe_policy.py`; the review therefore does not accept two divergent copies of
the same physical projector.

## EV-00180 — D.002 recoverable-group endpoint candidate validation

**Status:** accepted / full D.002 component-local contribution to
`VPNG-U001-R1.R3.R8.R3.R1`  
**Scope:** bounded candidate evaluation for endpoint-bearing WireGuard recoverable groups:
fresh technical peer suitability, exact D.003 ownership confirmation, fresh group endpoint
check through that ownership, group-local candidate rejection on confirmed `NO_REPLY`,
fail-closed handling of `LOCAL_ERROR`, exact no-owner convergence when candidates are
exhausted, reserve failback compatibility, and generation invalidation when group endpoint
policy changes.  
**Implementation:** `design/NG3/code/python/rou/wireguard_peer_manager.py`.  
**Unit evidence:** `design/NG3/code/python/rou/tests/test_wireguard_peer_manager.py`.  
**Review:** `design/reviews/NG3-2026-11-25-wireguard-d002-group-endpoint-review.md`.  
**Executable evidence:** GitHub Actions run `45576973824`, unit job
`139077314434` — PASS on source
`7e9cc424ef2d23f00eb49465eb3a96ee4ea03ae6`.

The tests prove that a group endpoint is checked only after D.003 has confirmed the complete
candidate ownership map; confirmed endpoint `NO_REPLY` moves only that group to its next
allowed technical candidate while sibling ownership is preserved; `LOCAL_ERROR` invalidates
the current D.002 realization rather than acting as remote unavailability; exhausting all
candidates converges an exact no-owner state; and a failed end-to-end check of a recovered
preferred ordinary peer can restore the still-valid reserve owner. A change of the configured
group endpoint changes the Device-wide D.002 generation.

## EV-00190 — production D.003 split-group WireGuard ownership

**Status:** accepted / full D.003 generalized R8 lower materialization  
**Scope:** production-kernel exact complete `AllowedIPs` convergence with two independent
payload group bundles simultaneously owned by different managed WireGuard peers, while each
peer retains its permanent technical probe /32 and the shared WireGuard interface identity is
preserved.  
**Implementation:** `design/NG3/code/python/rou/wireguard_peer_ownership.py`.  
**Kernel evidence:** `design/NG3/code/python/rou/tests/integration_wireguard_peer_ownership.py`.  
**Review:** `design/reviews/NG3-2026-11-25-wireguard-d003-split-ownership-review.md`.  
**Executable evidence:** GitHub Actions run `45577901507`,
`linux-wireguard-peer-ownership` job `139080276853` — PASS on source
`ae1b626a0f52f87b53996872793473e51bc0cc75`; unit job `139080276823` — PASS.

The kernel run emitted `D003_WG_SPLIT_GROUP_OWNERSHIP=PASS` after fresh-confirming a complete
state in which `10.77.0.0/24` belonged only to peer A and `10.88.0.0/24` belonged only to
peer B. Both permanent peer probe /32s remained present, the old opposite group ownership was
absent, and the common `wg0` ifindex remained unchanged.

## EV-00200 — combined A.007 + D.002 probe-plane desired composition

**Status:** accepted / pure C.001 full-union composition seam; runtime wiring remains partial  
**Scope:** one deterministic collision-free probe allocation and one complete desired union
covering A.007 Profile owners, D.002 WireGuard peer technical owners and stable recoverable-
group owners; exact current-path binding; fail-closed Profile/path membership; duplicate-owner
rejection; and input-order invariance without semantic evidence merging.  
**Implementation:** `design/NG3/code/python/rou/probe_plane_desired.py`,
`design/NG3/implementation-traceability.md`.  
**Unit evidence:** `design/NG3/code/python/rou/tests/test_probe_plane_desired.py`.  
**Review:** `design/reviews/NG3-2026-11-25-probe-plane-union-composition-review.md`.  
**Executable evidence:** GitHub Actions run `45582035756`, unit job
`139094358081` — PASS on source
`8d905151b2f13c356585504f66c0de1e1c46380f`.

The seven focused tests prove one shared allocation/full desired union across Profile, peer and
group owners; semantic separation when Profile and group use the same physical ICMP target;
determinism under peer-input reordering; exact rejection of a stale same-path/different-ifindex
D.002 binding; current Profile/path membership for both Profile and group owners; and duplicate
semantic-owner rejection. The preceding run `45581842029` had all seven focused tests PASS but
failed the exhaustive production-code trace guard only; commit
`8d905151b2f13c356585504f66c0de1e1c46380f` added the required
`A.007 + C.001 + D.002` edge and the complete unit suite passed.

## EV-00210 — production alpha combined probe-plane lower runtime

**Status:** accepted / production combined lower convergence and A.007 scoped consumption;
D.002 scheduling/status/generation coupling remain partial  
**Scope:** projection of current managed-WireGuard peer/group probe demand onto accepted
current paths, one production A.007+D.002 probe desired union, full-union local/routing
materialization, and A.007-only execution readiness/evidence consumption.  
**Implementation:** `design/NG3/code/python/rou/probe_plane_desired.py`,
`design/NG3/code/python/rou/alpha_runtime.py`,
`design/NG3/code/python/rou/linux_availability_cycle.py`,
`design/NG3/code/python/rou/availability_observation_tick.py`.  
**Unit evidence:** `design/NG3/code/python/rou/tests/test_alpha_runtime.py`,
`design/NG3/code/python/rou/tests/test_availability_observation_tick.py`, plus the existing
owner-scoped precondition suite.  
**Review:** `design/reviews/NG3-2026-11-25-probe-plane-alpha-runtime-review.md`.  
**Executable evidence:** GitHub Actions run `45583717575`, unit job
`139100000005` — PASS on source
`4ae8735965970103690780e134f93ee4e64deee3`.

The alpha build-current test proves that one current managed WireGuard path contributes
Profile, peer and recoverable-group owners to the same production probe plane and that only
Profile intents enter `AvailabilityProbeRuntime`. The combined-tick test supplies a full union
containing a D.002 peer owner and proves A.007 still attempts only its Profile owners.
The runtime cycle converges the complete desired union and uses the previously accepted
owner-scoped readiness verifier for exactly the A.007 owner subset. No D.002 peer/group probe
is executed merely because its lower state is materialized.

## EV-00220 — A.008 D.002 realization status projection

**Status:** accepted / semantic status carrier for D.002 realization; production D.002 caller
publication remains pending  
**Scope:** current-only typed retention of authoritative `WireGuardPeerRealization` values in
`RuntimeStatusSnapshot`, deterministic Device ordering, duplicate-Device rejection and JSON
serialization of D.002 generation/group ownership without changing compact-text grammar.  
**Implementation:** `design/NG3/code/python/rou/runtime_status.py`.  
**Unit evidence:** `design/NG3/code/python/rou/tests/test_runtime_status.py`.  
**Review:** `design/reviews/NG3-2026-11-25-wireguard-d002-runtime-status-review.md`.  
**Executable evidence:** GitHub Actions run `45584590216`, unit job
`139102846576` — PASS on source
`23f66a270e3b55832c2fd180583bb544bb1a29fa`.

A.008 receives D.002's owner projection rather than reconstructing group ownership from
configuration or kernel state. Equivalent snapshots remain subject to the existing
change-driven publication contract. A.009 compact text remains unchanged: its normative
Device/Profile grammar is not extended merely because a richer semantic snapshot exists.

## EV-00230 — D.002 retained runtime coordinator core

**Status:** accepted / D.002 runtime-coordinator core; alpha trigger/status feed remain pending  
**Scope:** one retained `WireGuardPeerManager` per active managed WireGuard Device; exact
confirmed D.001 base-generation prerequisite; exact current path and probe-owner-union
validation before mutation; fresh owner-scoped C.001 readiness immediately before each peer or
group physical attempt; D.003-before-group-probe sequencing; Manager-state discard when the
current path disappears; and explicit separation of confirmed no-owner from local runtime
failure.  
**Implementation:** `design/NG3/code/python/rou/wireguard_peer_runtime.py`,
`design/NG3/implementation-traceability.md`.  
**Unit evidence:** `design/NG3/code/python/rou/tests/test_wireguard_peer_runtime.py`.  
**Review:** `design/reviews/NG3-2026-11-25-wireguard-d002-runtime-coordinator-review.md`.  
**Executable evidence:** GitHub Actions run `45587522999`, unit job
`139112974553` — PASS on source
`3d3860e7bc253444bb3072d1f37ae6d562ce284c`.

The focused suite proves retained sticky Manager state across repeated triggers, state discard
when the current path disappears, fail-closed rejection of inconsistent D.001 generation and
stale D.002 owner/path inputs before probe or D.003 mutation, and exact sequencing
`fresh peer readiness -> peer probe -> D.003 -> fresh group readiness -> group probe`.
A realization with no confirmed group owner but no local problem remains a confirmed D.002
state rather than being conflated with a coordinator failure.

## EV-00240 — alpha D.002 reconciliation and status integration

**Status:** accepted / production alpha invocation and A.008 publication path; R8.R6 generation
coupling remains pending  
**Scope:** initial, periodic and protective-release D.002 trigger composition after confirmed
full-union C.001 probe-routing convergence; reuse of the retained D.002 coordinator and exact
D.003 enforcer; publication of authoritative `WireGuardPeerRealization` through A.008;
confirmed no-owner handling without false local failure; DEGRADED reporting for local D.002
problem without invalidating unrelated confirmed effective state; and stale D.002 status
invalidation when a new trigger cannot be established or D.001 is removed.  
**Implementation:** `design/NG3/code/python/rou/alpha_runtime.py`,
`design/NG3/code/python/rou/runtime_status.py`,
`design/NG3/implementation-traceability.md`.  
**Unit evidence:** `design/NG3/code/python/rou/tests/test_alpha_runtime.py`,
`design/NG3/code/python/rou/tests/test_runtime_status.py`, plus EV-00230 coordinator tests.  
**Review:** `design/reviews/NG3-2026-11-25-wireguard-d002-alpha-integration-review.md`.  
**Executable evidence:** GitHub Actions run `45588860316`, unit job
`139117569301` — PASS on source
`ac8969d706d9127308df28f1eb3ea5f5515cc57f`.

The alpha helper test proves that the current `ProbePlaneDesiredAssembly`, current path routes
and authoritative D.001 realization are passed to the retained coordinator with a fresh Linux
structural snapshot observer. Status tests prove that a D.002-local degradation can preserve
already confirmed effective state while explicitly marking only the D.002 projection unknown
when no authoritative realization exists. Code-path review confirms the same normal
reconciliation function is used by periodic audit and protective-mode explicit normal-release
checks, while startup performs an initial D.002 trigger before READY.

## EV-00250 — typed architecture traceability and stable evidence-address gate

**Status:** accepted  
**Scope:** Requirement/Constraint-typed component trace edges; closed architecture coverage from
structured direct references plus complete-child aggregation instead of arbitrary prose
mentions; EV-only stable architecture Evidence fields with registry validation; and explicit
current executable Python reference-implementation trace terminology.  
**Requirements/model:** `VPNG-D001-R1.R1.R6`, `VPNG-D001-R1.R1.R6.R1`;
`design/requirements-model.md` §14.  
**Implementation/evidence:** `design/NG3/code/python/rou/tests/test_architecture_traceability.py`,
`design/NG3/architecture-ng.md`, `design/NG3/implementation-traceability.md`.  
**Review:** `design/reviews/NG3-2026-11-25-typed-trace-evidence-gates-review.md`.  
**Executable evidence:** GitHub Actions run `45594591421`, unit job
`139137371221` — PASS on source
`ede2432af7dd2cbf32e8b13084bff37a14ec5e83`; actual-main lineage run
`45594591509` — PASS.

The strengthened gate itself exposed a previously hidden structured-coverage gap for
`VPNG-D001-R1.R1.R8` and `VPNG-D001-R1.R1.R8.R3` after their false E.002
`Constrained by` edges were removed. Their actual owner, architecture §2.9.3, now carries
the explicit direct coverage.

## EV-00260 — release methodology ownership and frozen-record consistency

**Status:** accepted  
**Scope:** technology-neutral documentation-driven release methodology; release-specific
walkthrough ownership through approved scope + published documentation; explicit
candidate-bound immutability of frozen release records; removal of stale cycle/version identity
from current requirements/stable architecture; canonical projectholder terminology; and
regression checks for these document-owner boundaries.  
**Requirements:** `VPNG-D001-R3*`; current project documentation/release conventions.  
**Review:** `design/reviews/NG3-2026-11-25-release-methodology-dedup-review.md`.  
**Executable evidence:** corrected GitHub Actions run `45595690581`, unit job
`139141146853` — PASS and release-0.1.0 deployment job `139141147878` — PASS on source
`9a342df0f43dc0728a7490d37e93fca9bacde58f`; final docs-only source
`db788897bacedb43c521595a182d133be9751db3` has actual-main lineage run
`45595865021` — PASS.

A preceding draft run deliberately remains recorded because its release job
`139139903264` failed when a proposed cleanup touched the frozen 0.1.0 RELEASE-SCOPE and
thereby exposed a stale-project-snapshot condition. The final accepted tree restores that
release record exactly and instead makes the ownership/freeze rule explicit in the general
methodology.

## EV-00270 — architecture coverage-index vocabulary normalization

**Status:** accepted  
**Scope:** canonical component-edge vocabulary (`Implements` / `Constrained by`) plus a
neutral `Coverage nodes` label for the non-component closed requirement/constraint coverage
index; preservation of explicit Rust-boundary coverage after removal of the standalone
`Covers` marker.  
**Model:** `design/requirements-model.md` §14.  
**Review:** `design/reviews/NG3-2026-11-25-coverage-label-cleanup-review.md`.  
**Executable evidence:** GitHub Actions run `45596378111`, unit job
`139143419624` — PASS on source
`16e62c5cc43f79fe31729aad34908821f09db747`; actual-main lineage run
`45596377672` — PASS.

## EV-00280 — R8.R6 D.002 generation currentness for A.007 evidence

**Status:** accepted  
**Scope:** typed A.007 ownership-dependency state; ordered runtime composition
`C.001 prepare -> D.002 reconcile/generation -> A.007 fresh observation -> A.004 priority`;
same-`LogicalPathId`/same-interface D.002 generation invalidation; confirmed no-owner
generation semantics; and blocking of remote A.007 evidence only for applicable unconfirmed
D.002 subjects.  
**Requirement:** `VPNG-U001-R1.R3.R8.R6`.  
**Architecture:** A.004, A.007, C.001, D.002; D.003 unchanged-interface ownership evidence
remains `EV-00190`.  
**Review:** `design/reviews/NG3-2026-11-25-r8r6-runtime-ordering-review.md`.  
**Executable evidence:** GitHub Actions run `45603272998` on reviewed source
`42a0a27cfcf0a518841fa930b481c0dd2a5da08d`: unit job `139167589571` — PASS,
`linux-probe-runtime` `139167589540` — PASS, `linux-wireguard-peer-ownership`
`139167589253` — PASS, `linux-wireguard-multipeer` `139167589690` — PASS,
`linux-alpha-smoke` `139167589811` — PASS, and frozen
`release-0-1-0-deployment-qa` `139167589538` — PASS. Actual-main lineage run
`45603273406` — PASS.

The focused Manager acceptance proves that only the D.002 generation changes while
`LogicalPathId` and exact interface identity stay equal: old availability-problem confirmation
loses current force and old evidence is rejected. Separate A.004 ordinary-path stickiness may
remain, demonstrating that routing history is not being misclassified as availability evidence.

## EV-00290 — trace/model hygiene and canonical architecture-edge grammar

**Status:** accepted  
**Scope:** canonical list-form component trace grammar; rejection of inline/dangling typed
edges; explicit neutral `Coverage nodes` semantics in the requirement model; optional
component-local `Evidence:` semantics with EV-only payload when present; canonical
materialization explanation label; independence of requirement status from component-local
`full|partial|none`; canonical literal `projectholder` role identifier; and historical
supersession of stale EV-00110 materialization wording.  
**Requirements/model:** `VPNG-D001-R1.R1.R5`, `VPNG-D001-R1.R1.R6`,
`VPNG-D001-R1.R1.R6.R1`; `design/requirements-model.md` §14.  
**External review:** `design/reviews/NG3-2026-11-25-external-trace-model-hygiene-review.md`.  
**Review/response:** `design/reviews/NG3-2026-11-25-trace-model-hygiene-response.md`.  
**Implementation/evidence:** `design/NG3/architecture-ng.md`,
`design/NG3/code/python/rou/tests/test_architecture_traceability.py`,
`PROJECT-CONVENTIONS.md`.  
**Executable evidence:** GitHub Actions run `45616634226` on source
`d772f9595e3989e1f4bf77b242a6d7ae9e2d2043` — **25/25 PASS**; unit job
`139213608704` — PASS. Actual-main lineage run `45616634403` — PASS.

The review confirmed that the old green gate could miss a Requirement-looking materialization
line following an inline `Constrained by` heading. The canonical grammar now permits only
list-form `Implements` and `Constrained by` blocks and rejects trace-looking lines outside
those blocks. No second/parallel validation script was introduced.

## EV-00300 — configuration-driven managed presence and safe reserve release

**Status:** accepted (evaluation-branch internal implementation review)  
**Scope:** current-only warm normalization; A.013 deterministic ordinary/reserve demand,
Profile-local roles and OR aggregation; explicit A.012 desired set; fresh observations
between bounded D.001 attempts; selective dependency-confirmed reserve release and
truthful A.008 diagnostic projection.  
**Requirements:** `VPNG-U001-R1.R3.R7.R3` and R1–R4 children.  
**Architecture:** A.001, A.002, A.008, A.012, A.013, C.004, D.001, D.003.  
**Review:** `design/reviews/NG3-2026-11-25-warm-presence-evaluation-implementation-review.md`.  
**Reviewed implementation baseline:** `74bfb5e3a5116cc998c6aa4578728d2bdca8ffee`.  
**Executable evidence:** GitHub Actions [NG3 Python run 45645208959](https://github.com/abyssdigger/vpn-gateway/actions/runs/45645208959)
— **25/25 jobs PASS**, unit job 139314335682 — **940/940 tests PASS**;
`linux-managed-device-runtime` job 139314334848 — PASS;
Actual main lineage guard run 45645208720 — PASS.

The kernel integration uses the production WireGuard Adapter, real network namespace,
normal C.001/probe convergence and D.003. It induces a primary-interface loss and a
separately enforced D.001 secret-permission failure, confirms reserve activation, restores
the primary with reserve still present, checks the release gate, confirms removal of
dynamic payload AllowedIPs immediately before real D.001 deletion, and checks post-release
binding and status. Stale replacement identity and D.003 failure are explicit injected
negative observations; the successful stop and kernel AllowedIPs observations are real.
No remote peer availability or payload-through-reserve claim is made by this experiment.

This evidence is isolated on the evaluation branch. It does not record a main snapshot,
release decision or projectholder acceptance of the implementation.

## EV-00310 — normal managed Device reclaim activation and exact reserve admission

**Status:** verified development result; independent terminal review ACCEPT for #41.  
**Scope:** A.002/A.004/A.008/A.012/A.013/D.001–D.003 composition; careful/strict,
exact lifecycle reserve obligation, bounded exact retirement and non-recursive F2.  
**Requirements:** `VPNG-U001-R1.R3.R7.R4`, R1/R2; preserve R7.R3 reserve behavior.  
**Task/review:** [#41](https://github.com/abyssdigger/vpn-gateway/issues/41),
[exact-capacity disposition](https://github.com/abyssdigger/vpn-gateway/issues/41#issuecomment-7239014269),
[kernel/status review](https://github.com/abyssdigger/vpn-gateway/issues/41#issuecomment-7239034859),
[independent terminal ACCEPT #41/7239133255](https://github.com/abyssdigger/vpn-gateway/issues/41#issuecomment-7239133255).  
**Verified implementation/test baseline:** `a5472336c89e54b8b20a2042cc9e7171da43b317`.  
**Executable evidence:** [NG3 Python 46143230434](https://github.com/abyssdigger/vpn-gateway/actions/runs/46143230434)
— 25/25 jobs PASS; [unit 140973642680](https://github.com/abyssdigger/vpn-gateway/actions/runs/46143230434/job/140973642680)
— 1061/1061 PASS; [linux-managed-device-runtime 140973642829](https://github.com/abyssdigger/vpn-gateway/actions/runs/46143230434/job/140973642829)
— PASS; lineage guard 46143230499 PASS.

The shared normal startup/periodic path exercises the immutable plan, replacement policy,
exact dependency cleanup/retirement, F2 and final status. The focused regression proves
that careful can retire an A.013 baseline-selected Device while retaining another exact
used survivor. Cold-start fallback, foreign same-name ordinary link and reserve withdrawal
after ordinary recovery exercise real Linux lifecycle and policy without injected positive
peer replies. Careful retained D.002, strict partial and remaining batch scenarios use
real kernel interfaces, AllowedIPs, C.001 and D.001/D.003 operations with **injected technical
peer replies**; they do not establish remote end-to-end reachability.

The red test-only baseline `e689ec3c5c34dc726ace5fe362bd3a6862d796ae` failed on missing
mandatory reserve ([unit job](https://github.com/abyssdigger/vpn-gateway/actions/runs/46143061397/job/140973110632)).
The correction `97a40135e45a46e46fb1d5dead1c0355bb445e29` keeps raw #40 contribution/floor
evidence separate from exact-capacity A.013 lifecycle demand. The foreign-link regression
confirms preserved reserve and truthful DEGRADED status. No accepted pure A.013, A.004
or reclaim selection contract changed.

**Independently accepted task candidate:** [`52c2da248269b42ac1be757981a3a8fbfe488dc7`](https://github.com/abyssdigger/vpn-gateway/commit/52c2da248269b42ac1be757981a3a8fbfe488dc7).
The terminal review binds the documentation and architecture/trace reconciliation to this exact
candidate. Exact-candidate [NG3 Python 46143677980](https://github.com/abyssdigger/vpn-gateway/actions/runs/46143677980)
— 25/25 jobs PASS; unit 1061/1061 PASS; affected linux-managed-device-runtime PASS;
[actual-main lineage 46143678005](https://github.com/abyssdigger/vpn-gateway/actions/runs/46143678005) — PASS.
The implementation/test baseline and limitations above are unchanged.

The #41 task acceptance alone did not close R7.R4/R1/R2. Final documentation/trace-only
reconciliation was independently accepted at [`28e92477b1b9b6ec4746de52d3ad2e4d021601ba`](https://github.com/abyssdigger/vpn-gateway/commit/28e92477b1b9b6ec4746de52d3ad2e4d021601ba)
([#41 final review](https://github.com/abyssdigger/vpn-gateway/issues/41#issuecomment-7239352505),
[NG3 Python 46145226957](https://github.com/abyssdigger/vpn-gateway/actions/runs/46145226957) — 25/25 jobs PASS).
The separate [independent #48 requirement closure review](https://github.com/abyssdigger/vpn-gateway/issues/48#issuecomment-7239178657)
accepted R7.R4/R1/R2 architecture closure on the established evidence; its [local-edge review](https://github.com/abyssdigger/vpn-gateway/issues/48#issuecomment-7239328302)
reconciles component materialization according to architecture §2.9. Evidence limits above remain unchanged.
Neither review authorizes main publication or claims released 0.1.0 support.
