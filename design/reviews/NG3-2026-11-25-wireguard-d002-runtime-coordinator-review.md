# NG3 D.002 runtime coordinator core review — 2026-11-25

**Review unit:** retained D.002 runtime coordinator core  
**Reviewed implementation head:** `3d3860e7bc253444bb3072d1f37ae6d562ce284c`  
**Requirement:** `VPNG-U001-R1.R3.R8*`  
**Architecture:** A.001, C.001, D.001, D.002, D.003  
**Evidence:** `EV-00230`

## Verdict

**PASS — the accepted D.002 Manager can now be retained and driven through exact current
D.001/C.001/D.003 runtime prerequisites without introducing a second selection authority.**

This review accepts only the coordinator core. Alpha does not call it yet, so this unit does
not claim the periodic/explicit production trigger, A.008 publication, or R8.R6 generation
coupling.

## Findings and dispositions

### F1 — one retained Manager must own each current managed Device context

**Decision:** accepted.

The coordinator retains one `WireGuardPeerManager` per Device across reconciliation calls, so
ordinary-owner stickiness and reserve failback semantics survive periodic triggers. When the
Device has no accepted current path, the retained Manager is discarded rather than preserving
stale ownership evidence for a later path generation.

### F2 — D.001 generation must be authoritative before D.002 executes

**Decision:** accepted after review hardening.

The coordinator requires desired-present / confirmed-present D.001 state, a non-problem
realization, and exact equality of desired and confirmed base generations. Inconsistent or
unconfirmed base state fails before any remote probe or D.003 mutation.

### F3 — accepted C.001/D.002 context must be exact before mutation

**Decision:** accepted after review hardening.

For each current Device, exactly one current logical path is required. Its interface name must
match the managed WireGuard base. The coordinator also requires the typed peer/group owner
sets and every typed D.002 path binding to match the accepted current assembly before invoking
the Manager.

### F4 — physical attempts require fresh owner-scoped readiness

**Decision:** accepted.

Every peer and group check fresh-observes the complete structural policy snapshot and invokes
`verify_probe_execution_precondition_scoped` for exactly that semantic owner against the
full accepted union. Sibling semantic evidence is not merged.

### F5 — group endpoint readiness must follow the D.003 postcondition

**Decision:** accepted and directly tested.

The focused ordering test observes:
`fresh peer readiness -> peer probe -> D.003 convergence -> fresh group readiness -> group probe`.
Thus a group endpoint check after ownership transfer does not reuse a pre-transfer C.001
snapshot.

### F6 — no-owner and local runtime failure remain different states

**Decision:** accepted.

When no peer has positive technical evidence, D.002 may confirm an exact no-owner
`AllowedIPs` realization. The coordinator reports that result as confirmed but not ready.
Local/unconfirmed Manager problems instead make the coordinator result unconfirmed. Global
alpha READY/DEGRADED policy is intentionally not invented in this unit.

### F7 — production invocation is still absent

**Decision:** remaining scope, not a finding against this unit.

`alpha_runtime.py` does not yet instantiate/call this coordinator, does not feed its
realizations to A.008, and does not couple A.007 evidence freshness to D.002 generation.

## Evidence

- coordinator implementation: `f540c2f00d73dfc2a6bb5cc4e35e78dc8b4d3ffd`;
- focused tests + exhaustive trace: `0e28a0abba2e2412f37b4f995bdfb87700cf4eaa`;
- review hardening: `3d3860e7bc253444bb3072d1f37ae6d562ce284c`;
- run `45587522999`, unit job `139112974553` — **PASS**;
- actual-main lineage run `45587523111` — **PASS**.

## Remaining frontier

Wire the coordinator into alpha after the full probe-plane lower convergence has been
confirmed, invoke it on initial and periodic/explicit normal reconciliation, publish returned
`WireGuardPeerRealization` values through A.008, and then bind A.007 evidence freshness to
the applicable D.002 generation.
