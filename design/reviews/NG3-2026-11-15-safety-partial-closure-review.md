# VPN-GATE NG3 — Safety Partial Closure Review

**Cycle:** `ng3-design-cycle-20261115-managed-domain-contract-40m`  
**Scope:** independently settled safety requirements under `VPNG-R4`.

## Closure decisions

### VPNG-R4.R1 — fail closed on missing policy certainty

**Verdict:** ACCEPT CLOSURE.

The declarative configuration boundary rejects ambiguous semantic input before dependent network mutation, and payload policy is materialized only from one accepted deterministic structural result.

Missing/ambiguous policy therefore does not create implicit VPN forwarding.

### VPNG-R4.R2 — fail closed on unverified effective state

**Verdict:** ACCEPT CLOSURE.

`NetworkPolicyExecutor` observes current state, applies desired state, verifies the postcondition and does not report desired state as confirmed merely because commands were issued.

When the required postcondition cannot be confirmed, the architecture prefers a restrictive result.

### VPNG-R4.R4 — protective startup boundary

**Verdict:** ACCEPT CLOSURE.

The managed network domain is isolated from ambient host networking, and lifecycle orchestration establishes the protective boundary before payload readiness is reported.

Startup success is tied to postconditions rather than process existence.

### VPNG-R4.R5 — recovery after partial mutation

**Verdict:** ACCEPT CLOSURE.

After a partial lower-network failure, the Executor re-observes authoritative current state before planning another mutation and either converges safely or leaves the affected traffic restricted.

### VPNG-R4.R3 — safe transition

**Verdict:** KEEP OPEN.

The architecture has the correct Executor responsibility and safety invariant, but it intentionally does not yet define the concrete lower-network transition algorithm.

For some desired-state changes, command ordering and kernel semantics may determine whether an unsafe intermediate state exists.

Closing this node therefore requires a lower transition design plus sufficient evidence.

### VPNG-R4 parent

**Verdict:** KEEP OPEN.

The parent remains materially dependent on the unresolved safe-transition requirement.

## Simplification review

No separate SafetyManager is needed.

Safety is enforced at the boundaries that own configuration acceptance, lifecycle readiness and network-policy convergence.

## Verdict

**PASS — partial closure only.**

Accept closure for:

- `VPNG-R4.R1`;
- `VPNG-R4.R2`;
- `VPNG-R4.R4`;
- `VPNG-R4.R5`.

Keep `VPNG-R4.R3` and the parent `VPNG-R4` open.
