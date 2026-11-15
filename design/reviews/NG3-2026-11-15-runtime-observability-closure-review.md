# VPN-GATE NG3 — Runtime Observability Closure Review

**Cycle:** `ng3-design-cycle-20261115-managed-domain-contract-40m`  
**Scope:** `VPNG-R6` current-state observability.

## Review questions

1. Can an operator determine configured intent, effective path state and blocking problems without reading kernel commands?
2. Does the status architecture preserve the distinction between desired, confirmed and unknown state?
3. Does status composition create a second policy/state owner?
4. Is history required?

## Architecture result

The architecture introduces `RuntimeStatusAgent`.

It subscribes to current-snapshot InfoEvents from the Engines that own authoritative domains
and retains only the latest relevant snapshot per source.

It composes:

```text
RuntimeStatusSnapshot:
    configured_intent
    confirmed_effective_state
    availability_state
    readiness
    blocking_problems
    unknown_or_unconfirmed_fields
```

The Agent never actuates the represented domains and never decides their policy.

## Closure decisions

### VPNG-R6.R1 — configured intent visibility

**Verdict:** ACCEPT CLOSURE.

Accepted/configured intent is reported by the domain owner that accepted it and composed into
the current status snapshot. The status layer does not reconstruct configuration from kernel
state.

### VPNG-R6.R2 — effective path visibility

**Verdict:** ACCEPT CLOSURE.

Current logical path binding, effective ordering and availability state are published by
their authoritative owners and composed without changing their semantics.

### VPNG-R6.R3 — failure visibility

**Verdict:** ACCEPT CLOSURE.

Current blocking diagnostics/readiness/convergence problems are included in the status
snapshot. A failure is not required to become a historical event record to remain visible
while it is current.

### VPNG-R6.R4 — truthful effective state

**Verdict:** ACCEPT CLOSURE.

The StatusAgent explicitly distinguishes:

- configured/desired;
- confirmed actual/effective;
- unknown/unconfirmed.

Missing, stale or conflicting authoritative snapshots are surfaced as unknown/problem state,
not silently resolved into desired truth.

### VPNG-R6 parent

**Verdict:** ACCEPT CLOSURE.

The architecture provides one coherent current user-facing projection without requiring
kernel inspection or a second state owner.

## Simplification review

No RuntimeStateManager/StatusManager with policy ownership is introduced.

No event history, audit database, metrics store or replay log is required by R6.

The current presentation format remains replaceable interface machinery.

## Evidence boundary

This review accepts the architecture. Implementation evidence must later prove that source
snapshots are current and that unknown/conflict conditions are rendered truthfully.

## Verdict

**PASS.**

Accept closure for the complete current `VPNG-R6` subtree.
