# VPN-GATE NG3 — EXP-087 WireGuard runtime AllowedIPs review

**Date:** 2026-11-24  
**Review unit:** single-interface WireGuard peer failover feasibility  
**Evidence source:** `4ae88f67d3cd02f64f04f99e9a62cb3876abea76`  
**Evidence run:** `45333802569`, job `138241133580`  
**Result record:** `EXP-087-result-20261124.md`

## Scope

Review whether EXP-087 establishes a credible experimental mechanism for keeping multiple
alternative WireGuard peers behind one interface, observing them independently, and changing
shared payload-prefix ownership at runtime.

This review does not select production integration, service-manager ownership, user-facing
configuration or a Release-1 architecture change.

## Findings

### F1 — WireGuard runtime AllowedIPs mutation is sufficient for the tested switch

**Decision:** accepted.  
**Resolution:** fixed by evidence; no production change in this unit.

EXP-087 changed complete peer `AllowedIPs` sets using `wg set` while `wg0` remained up.
No `wg0.conf` rewrite or reload participated. Real payload followed the resulting owner.

This is the required lower primitive for a single-interface peer switcher.

### F2 — the WireGuard transport endpoint is not the current ICMP probe target

**Decision:** accepted.  
**Resolution:** fixed by experiment design.

The underlay peer IP was reachable on the underlay but failed when the current VPN-GATE ICMP
shape forced it through `wg0`. A WireGuard UDP transport endpoint therefore cannot simply be
substituted for the current in-path ICMP target.

The successful discriminator was instead one permanent peer-specific in-tunnel `/32`.

### F3 — the minimal experimental WireGuard desired state is clear

**Decision:** accepted.  
**Resolution:** fixed by evidence.

For one `wg0`, the tested lower desired state is:

```text
peer:
    permanent probe target /32
    + shared payload prefixes iff this peer is selected
```

The probe target must remain assigned even while that peer is not the current payload owner,
otherwise availability of a standby peer cannot be observed independently.

The shared payload prefix remains exclusive, consistent with EXP-086.

### F4 — existing generic path availability cannot represent both peers directly

**Decision:** accepted.  
**Resolution:** no production change; integration remains gated.

Current availability evidence is owned by
`ProbePolicyOwner(profile_id, LogicalPathId)`, and a current `LogicalPathId` binds to a
concrete interface generation. Two peers inside one `wg0` do not become two generic logical
paths.

Creating synthetic `LogicalPathId` values for WireGuard peers would falsify the accepted
binding model and is rejected.

### F5 — useful availability machinery is reusable only below/around the subject identity

**Decision:** accepted.  
**Resolution:** integration deferred.

The tested probe execution shape itself remains useful: one exact target, forced through one
exact current interface, produces a technical reply/no-reply signal. Existing bounded
observation and confirmation concepts can inform a future implementation.

However, a future WireGuard integration needs a peer-specific observation subject and
WireGuard desired-state owner. It cannot simply feed two peer outcomes into the current
Profile/logical-path availability owner without an explicit architecture decision.

### F6 — EXP-087 intentionally leaves switching safety questions open

**Decision:** accepted.  
**Resolution:** deferred to any future production-integration review.

The experiment does not prove:

- zero-loss or transactional atomicity while payload is concurrently flowing;
- that one peer probe target proves reachability of every payload prefix behind that peer;
- stale-handshake/roaming behavior across all supported WireGuard deployments;
- production observation/verification/recovery semantics after a failed `wg set` apply.

Those questions do not invalidate lower feasibility, but they are acceptance gates for a
production owner.

### F7 — production adoption is explicitly postponed

**Decision:** accepted.  
**Resolution:** deferred.

The projectholder requested experiment-only work and explicitly does not want the mechanism
integrated into the VPN-GATE service manager before normal Release-1 operational trial.

Re-entry gate: a later explicit product decision after that Release-1 trial.

No current requirement, architecture, service-manager or Release-1 configuration change is
authorized by this experiment.

## Verdict

**PASS — FEASIBILITY CONFIRMED; PRODUCTION ADOPTION DEFERRED.**

EXP-086 remains correct that generic Linux route-priority availability cannot choose same-prefix
peers inside one `wg0`. EXP-087 proves a different mechanism: preserve peer-specific probe
ownership and move shared payload `AllowedIPs` at WireGuard runtime.

The mechanism removes the technical need for one WireGuard interface/listen port per alternative
peer, at the cost of introducing a future WireGuard-specific observation/desired-state owner.
