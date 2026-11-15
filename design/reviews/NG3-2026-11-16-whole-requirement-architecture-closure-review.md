# VPN-GATE NG3 — Whole Requirement/Architecture Closure Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-final-gates-40m`  
**Scope:** complete current NG3 requirement tree and architecture closure state.

## Review purpose

Verify that the current requirement tree is fully architecture-closed after resolution of
the two remaining human gates, without confusing architecture closure with implementation
completion.

## Human gates resolved in this cycle

### H1 — availability criterion

Accepted semantics:

- the user defines what observation constitutes practical path usability;
- configuration carries an availability-check mechanism and optional target;
- first release supports ICMP echo only;
- explicit target is used as configured;
- omitted target requests derivation from the accepted/current VPN endpoint/network facts;
- unresolved/ambiguous target or local inability to execute the check produces
  diagnostic/`no_evidence`, not automatic negative path evidence;
- future TCP/UDP/HTTP mechanisms are separate future capabilities.

Historical NG2 evidence independently confirms the architecture shape:

- probe request carried mechanism/path/target separately;
- physical-plane identity used mechanism/path/target;
- payload priority contract deliberately excluded probe transport details;
- late NG2 first-release transport was ICMP.

The exact historical external spelling `icmp/<ip>` was not found in the retained normative
artifacts during this review. NG3 therefore preserves the accepted semantic contract while
leaving the external field name/string grammar replaceable.

### H2 — safe priority transition

Accepted semantics:

- a pure priority permutation of an unchanged eligible path set must preserve forwarding
  representation of every eligible path;
- Linux implementation uses N+1 ordinary metric positions for N eligible routes;
- move primitive is duplicate-before-delete:
  `add X at free metric -> delete old metric copy`;
- one route may therefore temporarily exist twice at different metrics;
- broader structural policy transitions may use restrictive/fail-closed convergence.

Historical NG2 `availability-routing-model.md`, handoff material and EXP-027 provide
reusable evidence for the materially identical Linux kernel claim.

## Whole-tree mechanical validation

Current tree:

```text
requirement/constraint nodes: 83
closed:                       83
pending_closure:               0
rejected_closure:              0
open:                          0
```

Traceability/integrity:

```text
unique architecture requirement refs:     83
closed without architecture reference:     0
malformed normative requirement lines:     0
active decomposition blocks:                0
broken decomposition links:                 0
blocked node with invalid closure state:    0
stale architecture "still open" claims:     0
```

Process integrity:

```text
requirement refinement steps: 1..12 contiguous
Purpose/Reason escalation gate: present
closure lifecycle model: present
```

## Closure semantics reminder

This verdict means:

> every current NG3 R/C has an accepted architecture answer for the current scope.

It does **not** mean:

- implementation is complete;
- all implementation tests/evidence pass;
- all external syntax/documentation has been written;
- no future requirement can reopen architecture;
- all technical implementation choices are fixed.

Implementation conformance and evidence remain separate downstream gates.

## Architecture quality review

The fully closed tree still preserves the anti-overengineering constraints:

- no automatic VPN provisioning Manager in first release;
- no global lifecycle Engine;
- no universal configuration super-object;
- no universal probe framework;
- no availability evidence history/replay;
- no separate route-priority writer;
- no global retry queue;
- no RuntimeStateManager as a second source of truth;
- no semantic requirement-change journal.

The few accepted specialized mechanisms are directly justified:

- network namespace / explicit managed-domain boundary;
- ConfigurationAdapter;
- VPNPathAdapter;
- PayloadTrafficManager and pure Calculators;
- AvailabilityProbeAgent + ICMP Driver;
- NetworkPolicyAdapter/Executor;
- N+1 metric-slot priority transaction;
- RuntimeStatusAgent;
- local Manager reconciliation.

## Purpose / Reason review

The final additions have explicit human-approved causal meaning:

- user-selected availability criterion exists because the product cannot universally decide
  what practical path usability means for every deployment;
- ICMP-only is an explicit first-release constraint, not an accidental implementation leak;
- its child contract exposes the user adaptation caused by that constraint;
- priority-transition continuity exists to avoid a planned outage when only preference among
  already allowed paths changes;
- structural fail-closed transition remains allowed because safety must not be traded for
  continuity when policy meaning itself changes.

No final node required inventing a Purpose/Reason from architecture.

## Verdict

**PASS — COMPLETE CURRENT NG3 REQUIREMENT/ARCHITECTURE CLOSURE.**

All 83 current requirement/constraint nodes are architecture-closed.

The next phase may move from requirements/architecture closure into implementation/evidence
planning, subject to the ordinary per-unit requirement/design gate and without reopening
closed semantics unless implementation evidence reveals a real contradiction or constraint.
