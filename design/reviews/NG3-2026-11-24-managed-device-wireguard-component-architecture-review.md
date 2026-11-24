# NG3 2026-11-24 — managed Device / WireGuard component architecture review

**Review unit:** component boundary for explicitly managed Devices and same-prefix WireGuard peers  
**Architecture source:** `76776d935d2f3bea094fd1ebf1f2e2d79079a200`  
**Primary evidence:** `EV-00050`  
**Requirements:** `VPNG-U001-R1.R3.R7*`, `VPNG-U001-R1.R3.R8`

## Scope

Review whether the new open requirements have a coherent component boundary that:

- preserves the existing externally managed Device mode;
- does not turn WireGuard peers into synthetic logical paths;
- separates base VPN lifecycle from dynamic WireGuard peer ownership;
- gives stale Profile availability evidence an explicit invalidation boundary;
- preserves single-writer ownership and current VPNPathAdapter semantics;
- leaves user-facing configuration, secret handling and production materialization visibly open.

This review does not claim implementation completion or requirement closure.

## Verdict

**PASS — COMPONENT BOUNDARY SELECTED; MATERIALIZATION AND CONFIGURATION SURFACE REMAIN OPEN.**

## Findings and dispositions

### F1 — a scoped Device lifecycle Manager is now justified

**Decision:** accepted.  
**Resolution:** fixed.

A.012 `ManagedDeviceManager` is justified by the newly accepted R7 requirement branch.
It owns lifecycle state only for Devices with explicit managed intent.

This does not revive the previously rejected global LifecycleManager idea:
A.001 remains bounded product-lifecycle Machinery, while A.012 is a long-lived Manager for
one specific managed domain.

### F2 — externally managed Devices retain the old contract

**Decision:** accepted.  
**Resolution:** fixed.

No management intent means no A.012/D.001 ownership. VPN-GATE does not generate configuration,
start, restart, stop or adopt the external VPN instance.

The existing C.004 endpoint observation and PathBinding contract remains unchanged for those
Devices.

### F3 — base VPN realization and path binding remain distinct

**Decision:** accepted.  
**Resolution:** fixed.

D.001 `ManagedVPNAdapter` provides Direct, freshly verified convergence of an explicitly
owned base VPN realization. Successful service/configuration operations are not PathBinding
evidence.

C.004 remains the independent authority for the concrete endpoint generation.

### F4 — WireGuard peer selection is not logical-path identity

**Decision:** accepted.  
**Resolution:** fixed.

D.002 `WireGuardPeerManager` owns protocol-specific peer selection below one existing
logical path. D.003 `WireGuardPeerOwnershipEnforcer` owns only exact lower AllowedIPs
convergence.

Peers behind one wg0 do not become Device slots, LogicalPathId values or PathBinding values.

### F5 — three generations are intentionally distinct

**Decision:** accepted.  
**Resolution:** fixed.

The architecture now distinguishes:

1. managed base VPN realization generation — A.012/D.001;
2. concrete interface generation — C.004 PathBinding;
3. WireGuard peer-realization generation — D.002.

A change in the selected peer can therefore invalidate dependent evidence while preserving
the same LogicalPathId and interface generation.

### F6 — managed WireGuard readiness is an additional path-realization prerequisite

**Decision:** accepted.  
**Resolution:** fixed.

A bound wg0 with no confirmed shared-prefix owner is not sufficient for dependent payload
realization.

A.004 consumes the managed Device realization projection and treats an unconfirmed/problem
WireGuard peer realization as not ready, without changing logical path identity.

### F7 — peer readiness and Profile availability remain separate

**Decision:** accepted.  
**Resolution:** fixed.

Permanent peer-specific in-tunnel probe /32 values are technical WireGuard peer-readiness
facts owned by D.002.

The existing C.008 one-attempt technical Driver may be reused because its complete technical
contract matches, but the probe precondition has a distinct semantic owner and the
reply/no_reply interpretation belongs to D.002.

A.007 still owns Profile availability. Its context now includes the integration-realization
generation when one exists, so old Profile evidence cannot survive a peer switch.

### F8 — lifecycle removal is dependency-last

**Decision:** accepted.  
**Resolution:** fixed.

When structural Device demand disappears, dependent payload use and protocol-specific dynamic
state must stop using the Device before D.001 removes the base VPN realization.

On whole-product stop A.001 requests managed-Device absence through A.012 and waits for
confirmed cleanup before destroying Private network. This preserves one writer per managed
domain.

### F9 — EXP-088 supports no mandatory transition gate

**Decision:** accepted.  
**Resolution:** fixed with evidence-gated re-entry.

EV-00050 observed a complete-state A-to-B transfer with zero loss and no third-peer payload
delivery. The architecture therefore does not add a separate traffic gate solely for normal
AllowedIPs transfer.

It also does not claim wg set is universally atomic. D.003 success is defined only by fresh
exact post-apply observation; partial, ambiguous or unobservable state remains unconfirmed.

Re-enter a transition-containment mechanism if later evidence shows stale old-owner delivery
after confirmed new state, unintended third-peer delivery, an unsafe partial apply, or another
specific safety requirement.

### F10 — recovery does not invent a new failback policy

**Decision:** accepted.  
**Resolution:** fixed.

R8 requires ordered alternatives and failover to a suitable peer but does not currently
require automatic preemption merely because a more preferred peer recovered.

D.002 therefore does not invent such preemption. Adding it requires a separate normative
decision.

### F11 — configuration, secrets and implementation remain explicit gaps

**Decision:** accepted.  
**Resolution:** deferred.

The architecture defines normalized managed intent but deliberately does not select:

- final user-facing opt-in field spelling;
- secret source/storage/rotation contract;
- integration-specific generated configuration layout;
- production service-manager realization;
- production code.

Every new component edge is therefore marked `[none]` with an explicit
`Пробел материализации`.

Re-entry gate: managed-Device configuration/secret design followed by production
materialization.

## Verification

- architecture traceability/unit job on
  `76776d935d2f3bea094fd1ebf1f2e2d79079a200`: PASS;
- frozen 0.1.0 deployment QA on the same commit: PASS;
- no raw `EXP-*` evidence references were introduced into stable architecture;
- new component IDs are unique: A.012, D.001, D.002, D.003.

## Result

The component architecture is selected as the basis for subsequent managed-Device work.

R7/R8 remain open because the configuration/secret contract and production materialization
are not complete. EXP-088 may now move from `pending_decision` to `selected` as evidence
for the selected WireGuard lower mechanism.
