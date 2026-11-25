# NG3 D.002 runtime-status projection review — 2026-11-25

**Review unit:** A.008 carrier for authoritative D.002 current realization  
**Reviewed implementation head:** `23f66a270e3b55832c2fd180583bb544bb1a29fa`  
**Requirements:** `VPNG-M001-R2.R1*`, supporting `VPNG-U001-R1.R3.R8`  
**Architecture:** A.008, A.009, D.002  
**Evidence:** `EV-00220`

## Verdict

**PASS — A.008 can now retain and publish D.002's authoritative current realization without
becoming a second ownership authority or changing the compact-text contract.**

## Findings

1. D.002 remains the semantic owner. Status accepts only typed
   `WireGuardPeerRealization`; it does not derive group owners or generation.
2. One current realization per Device is enforced and stored deterministically.
3. The semantic snapshot/JSON now exposes D.002 generation, group owners and problem state,
   satisfying the general truthful-current-projection boundary once a production D.002 caller
   supplies them.
4. A.009 compact text is intentionally unchanged. Its accepted one-line Device and Profile
   grammar is not broadened by this unit.
5. This is not production D.002 scheduling. Alpha still has no persistent per-Device
   `WireGuardPeerManager` reconciliation call and therefore does not yet feed this status
   carrier in normal operation.

## Evidence

- implementation: `23f66a270e3b55832c2fd180583bb544bb1a29fa`;
- run `45584590216`, unit job `139102846576` — **PASS**;
- actual-main lineage run `45584590315` — **PASS**.

## Remaining frontier

Add a production D.002 runtime coordinator after full C.001 probe-plane convergence. It must
retain one Manager per managed WireGuard Device, derive the exact current base generation and
path route, build peer/group scoped readiness from a fresh full-union snapshot, invoke D.002
with the existing peer/group executors and D.003 enforcer, then feed the returned
`WireGuardPeerRealization` tuple into A.008 before status publication.
