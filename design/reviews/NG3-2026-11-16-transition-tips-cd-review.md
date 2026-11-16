# VPN-GATE NG3 — Transition Tips / NG2 Architecture Snapshot CD Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-transition-tips-cd-40m`

## Inputs

This review combines:

- current NG3 requirements and architecture;
- `design/NG3/config-model.md`;
- `design/NG3/experiment-evidence-transition.md`;
- `design/NG3/transition-tips.md`;
- recovered NG2 component/message-flow architecture snapshot;
- historical experiment evidence through EXP-027.

The recovered NG2 snapshot is treated as transition evidence, not as a command to restore NG2
component names or code contracts.

## 1. Snapshot principles retained

### 1.1 Components exchange meaning

Retained.

Current NG3 already requires explicit semantic contracts and lower implementation details not
to cross boundaries without need.

The snapshot reinforces this rule, but does not require restoration of exact NG2 CODE types.

### 1.2 Async events only where ownership requires them

Retained.

Events connect independent long-lived owners. Calculators, Adapters, Executors and Drivers
may remain synchronous Machinery.

No generic conversion of every internal call into Event delivery is justified.

### 1.3 Profile versus transport separation

Retained and strengthened by current Device/Profile recovery.

Profile is the payload/routing need. Device/binding provides transport capability and concrete
logical paths.

### 1.4 Availability changes priority, not membership

Retained.

Current NG3 expresses this with subject-specific availability evidence and bounded
confirmation state.

The snapshot's GoodNews/Tick event names are not restored because current NG3 has a later,
requirement-derived `positive | negative | no_evidence` contract.

### 1.5 Shared lower network-policy machinery with semantic owners

Retained.

Current architecture now explicitly records:

- payload owner scope;
- probe-observation owner scope;
- one shared lower NetworkPolicyAdapter/Executor;
- owner conflicts rejected/fail-closed before unsafe physical application.

A separate physical ProbeRulesAdapter remains unjustified.

### 1.6 Publication failure is not physical failure

Retained.

Current architecture now distinguishes:

```text
apply + fresh verify succeeded
publication failed
```

from mutation failure.

Transient publication retry must not blindly repeat an already verified physical operation.

### 1.7 Audit does not rewrite matched state

Retained.

Matched authoritative state requires no physical mutation; audit may republish current state.
Drift/recoverable failure causes fresh reconciliation.

### 1.8 Route-priority transaction serialization/coalescing

Retained.

For one Profile/routing domain:

- one priority transaction mutates metrics at a time;
- active plan is not cancelled;
- newer desired states may coalesce to latest;
- next transaction starts from fresh verified materialized state;
- unrelated Profiles do not require global serialization;
- no replay of every intermediate availability state is required.

## 2. Route-slot correction

The previous NG3 wording over-specified the route working layout as an always-present
`N+1` representation with exactly one free metric.

EXP-027 and the recovered snapshot support a weaker and more accurate invariant:

```text
a route move needs one currently unused ordinary metric
free metric is inferred operationally
free metric is not a semantic/config object
```

EXP-027 explicitly proved:

```text
all-live steady state
    -> no materialized/configured gap required
```

Current NG3 architecture has been corrected accordingly.

The make-before-break primitive remains unchanged:

```text
add duplicate at unused metric
delete only old copy
```

## 3. Component vocabulary conflict

The recovered NG2 snapshot states that `Engine` and `Executor` were not generic component
categories at that point.

Current NG3 has a later accepted normative `design/component-model.md`:

```text
Engine family:
    Manager
    Agent

Machinery:
    Calculator
    Adapter
    Executor
    Driver
    Runner
```

This is not a blocker.

Transition rule:

> recover responsibility boundaries from NG2; classify them using the current NG3 component
> model.

No current component-model rollback is justified by the snapshot.

## 4. Historical OPEN items versus current NG3 decisions

The snapshot listed several items as OPEN.

They do not all remain NG3 blockers.

### Final Profile status aggregation

Historical OPEN.

Current NG3 intentionally does not invent one Profile verdict. RuntimeStatusAgent composes
truthful current authoritative snapshots.

Therefore no blocker.

### Audit cadence

Historical OPEN.

Current NG3 makes exact audit interval a local implementation parameter unless recovery
latency becomes product-visible.

Therefore no blocker.

### Full Device/Profile/binding model

Historical OPEN.

Current recovery has now established Device/Profile user semantics, binding selectors/quotas,
stable logical path slots and normalized Profile policy contracts.

Therefore historical OPEN status does not reopen them.

### Bare ICMP target derivation

Historical formalization gap.

Current NG3 has accepted subject-specific deterministic derivation above probe runtime.

Therefore no blocker.

### Route executor API/name

Historical OPEN.

Current requirements do not make the public/internal class name observable. Current Executor
responsibility is sufficient.

Therefore no blocker.

## 5. EXP-024..026 correction

The former assumption that EXP-024..026 were unused numbers was wrong because normal search
had been anchored to the default branch.

Current evidence:

- EXP-024: privileged CI PASS + Debian 13 target PASS;
- EXP-025: target-confirmed STALE-INHERITANCE negative finding;
- EXP-026: privileged CI preliminary PASS; Debian 13 target confirmation open.

EXP-026 target confirmation has been moved to operational TODO/reminder and is not a current
product-semantics blocker because NG3 has not selected that exact remediation as mandatory
architecture.

If the implementation selects EXP-024-style conntrack-carried probe identity, explicit
generation invalidation is mandatory.

## 6. Device/config recovery closure

The recovered material now has architecture coverage for:

- strict canonical user config;
- Device/Profile identities and placeholders;
- expected-interface selectors/quotas;
- Device transport-policy ownership;
- explicit NAT semantics at product level;
- restrictive Device envelope;
- Device publication ownership;
- distinction between stable semantics and unresolved prototype grammar.

Exact traffic-envelope/publication grammar remains deliberately non-normative under
`VPNG-R1.R2.R4.R6.C1`.

That is a valid closure: the product constraint is precisely that NG3 must not guess the
grammar.

## 7. Human/product blocker discovered by transition review

### Multi-path inbound/bidirectional return-path semantics

Affected requirements:

- `VPNG-R2`;
- `VPNG-R2.R3`;
- `VPNG-R2.R3.R3`.

Current config semantics allow:

```text
direction = inbound | bidirectional
and
multiple simultaneously eligible paths
```

Historical EXP-014 was prepared specifically to test safe remote-initiated multi-path return
pinning, but was not completed.

No recovered later experiment proves equivalent behavior.

The architecture must not silently choose any of these assumptions:

- normal priority routing is enough;
- asymmetric return is always acceptable;
- fwmark/connmark pinning is already proven;
- first release supports only one inbound path.

### Required human decision

Choose one resolution class:

1. support multi-path inbound/bidirectional and accept/prove return-path architecture; or
2. explicitly constrain first-release support and define config/runtime behavior for the
   unsupported case.

This is the only current blocker found by this transition CD review.

## 8. Closure decisions

Accept architecture closure for the recovered config/Device/Profile/availability/route and
lifecycle refinements that are not dependent on the inbound multi-path gate.

Keep open:

```text
VPNG-R2
└── VPNG-R2.R3
    └── VPNG-R2.R3.R3
```

No other open product-semantic gate was found.

## Verdict

**PASS WITH ONE HUMAN PRODUCT/EVIDENCE GATE.**

The transition-tips pass materially reduced historical ambiguity and found one real unsupported
promise rather than generating additional architecture.
