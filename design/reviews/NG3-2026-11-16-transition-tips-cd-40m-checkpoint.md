# VPN-GATE NG3 — Transition Tips CD Checkpoint

**Cycle:** `ng3-design-cycle-20261116-transition-tips-cd-40m`  
**Date:** 2026-11-16

## Inputs consolidated

This cycle reviewed and consolidated:

- recovered Device/Profile/config semantics;
- runtime interface discovery/binding evidence;
- bootstrap/startup historical semantics;
- experiment evidence through EXP-027;
- recovered NG2 component/message-flow architecture snapshot;
- current NG3 requirements, architecture and component model.

Primary transition references:

- `design/NG3/transition-tips.md`;
- `design/NG3/experiment-evidence-transition.md`;
- `design/NG3/config-model.md`;
- `design/reviews/NG3-2026-11-16-transition-tips-cd-review.md`.

## Material corrections made

### Route working-space invariant

Corrected the previous over-specification that implied one permanently materialized free
metric in an N+1 steady representation.

Accepted evidence-based rule:

```text
priority move
    -> needs one currently unused ordinary metric

free metric
    -> inferred operationally
    -> not config
    -> not semantic/runtime "hole" object
```

EXP-027 explicitly proves that an all-live steady state does not require a configured or
materialized gap.

### Route transaction concurrency

Restored the historical per-Profile/routing-domain transaction semantics:

- one priority mutation transaction per affected Profile/domain;
- active transaction is not cancelled halfway through;
- newer desired orders may coalesce to latest;
- next transaction begins from fresh verified materialized state;
- no replay of every intermediate availability transition;
- no global serialization of unrelated Profiles.

### Probe/payload lower network-policy ownership

Restored owner-aware lower composition:

- payload and probe policy remain distinct semantic owners/scopes;
- one lower NetworkPolicyAdapter/Executor may realize both;
- unsafe inter-owner conflicts fail before physical application;
- a separate physical ProbeRulesAdapter is not required merely to preserve ownership.

### Publication and audit

Restored the distinction:

```text
physical/semantic convergence success
    !=
publication success
```

Transient publication failure retries publication from retained verified state rather than
blindly repeating already-successful physical mutation.

Audit does not rewrite already-matched lower state; it may republish current projection.

### Component vocabulary

The recovered NG2 snapshot used an older vocabulary where Engine/Executor were not generic
categories.

Current NG3 `design/component-model.md` remains normative.

Recovered ownership boundaries are reclassified using the current NG3 model rather than
rolling the vocabulary backward.

### EXP-024..026

Central experiment ledger and transition evidence now correctly record:

```text
EXP-024:
    privileged CI PASS
    Debian 13 PASS

EXP-025:
    target-confirmed STALE-INHERITANCE finding

EXP-026:
    privileged CI preliminary PASS
    Debian 13 confirmation open
```

EXP-026 target confirmation is an implementation evidence TODO, not the current product
semantics blocker.

## Current requirement state

```text
R/C nodes:          119
closed:             116
pending_closure:      0
rejected_closure:     0
open:                 3
```

Open chain:

```text
VPNG-R2
└── VPNG-R2.R3
    └── VPNG-R2.R3.R3
```

Mechanical integrity:

```text
closed without exact architecture ref: 0
extra architecture requirement refs:   0
closure label errors:                   0
```

## Single human/product gate

The current recovered Profile contract permits:

```text
direction = inbound | bidirectional
+
multiple simultaneously eligible paths
```

Historical EXP-014 was prepared to validate remote-initiated multi-path return-path pinning,
but was never completed.

No recovered later experiment proves an equivalent mechanism.

NG3 therefore cannot autonomously choose between:

1. **support multi-path inbound/bidirectional** and define/prove return-path handling; or
2. **constrain first-release support** and explicitly define/reject the unsupported
   configuration/runtime case.

The architecture must not silently assume ordinary priority routing is enough, asymmetric
return is always acceptable, fwmark/connmark pinning is already proven, or one-path inbound
is already the accepted product limitation.

## Verdict

**PASS WITH ONE HUMAN PRODUCT/EVIDENCE GATE.**

The CD cycle stops here because all other recovered semantics/evidence have been integrated
and the remaining gate requires an explicit product decision rather than further autonomous
decomposition.
