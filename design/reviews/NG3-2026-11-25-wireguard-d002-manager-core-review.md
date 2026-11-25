# NG3 D.002 WireGuard peer Manager core review — 2026-11-25

**Review unit:** D.002 current-only selection/generation core  
**Source reviewed:** `77a4e9a53862990710314bab84ef7f0dd51446ee`  
**Requirements:** `VPNG-U001-R1.R3.R8`, `VPNG-U003-R3.R6.R2`  
**Architecture:** C.001, C.008, D.001, D.002, D.003  
**Stable evidence:** `EV-00120`

## Findings

### F1 — peer identity remains below the logical-path model

**Decision:** accepted  
**Resolution:** clean

The Manager uses `WireGuardPeerProbeOwner(device_id, peer_id)` and the current Device
`RoutePriorityPathRoute`; it never creates one `LogicalPathId` per peer.

### F2 — no-failback semantics match the selected architecture

**Decision:** accepted  
**Resolution:** clean

When the current owner freshly replies, the Manager probes no preferred alternative and keeps
that owner. Only confirmed current-owner `no_reply` opens failover selection. The first
fresh-confirmed suitable alternative in configured order is selected.

### F3 — technical uncertainty is not converted to peer failure

**Decision:** accepted  
**Resolution:** fixed

A current-owner `local_error` is problem/unconfirmed, not `no_reply`; D.003 is not mutated
from that evidence. During review the context boundary was also hardened to reject duplicate
peer IDs before any probe or D.003 I/O.

### F4 — D.003 confirmation is the generation publication boundary

**Decision:** accepted  
**Resolution:** clean

The Manager builds complete D.003 state for every peer: permanent probe /32 for all peers and
the complete shared-prefix set only for the selected owner. A new semantic generation is
published only after D.003 reports a fresh exact postcondition. D.003 failure or ambiguous
state invalidates the current owner/generation rather than retaining stale evidence.

### F5 — context generations are explicitly distinct

**Decision:** accepted  
**Resolution:** clean

The peer-generation token includes the confirmed D.001 base generation, exact interface
identity, ordered peer context, shared-prefix set and selected owner. A peer-order-only config
change therefore resets peer selection/generation without pretending D.001 base generation
changed.

### F6 — stale Profile availability invalidation is not yet materialized

**Decision:** accepted  
**Resolution:** open by design

The core produces a peer-generation change that can invalidate dependent A.007 evidence, but
alpha does not yet publish/consume that generation and A.007 does not yet receive a context
change when ownership moves behind the same `LogicalPathId`/ifindex. This is the principal
remaining D.002 runtime-composition gap and keeps both reviewed requirement edges partial.

## Verification

GitHub Actions run `45554305306`, `unit` job `139002651040` — PASS, including D.002
selection/generation tests and full architecture traceability.

Separate accepted lower evidence already covers the mechanisms invoked by this core:
EV-00100 for production D.003 kernel ownership transfer and EV-00110 for the reusable
C.001/C.008 peer-probe seam.

## Verdict

**PASS for D.002 core / partial materialization.** The Manager semantics are ready for runtime
composition. R8 remains open until peer-probe demand, trigger/execution, status publication and
A.007 stale-evidence invalidation are wired end to end.
