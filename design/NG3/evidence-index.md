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
