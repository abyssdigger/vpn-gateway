# VPN-GATE NG3 — Lifecycle Control Surface Review

**Cycle:** `ng3-design-cycle-20261115-managed-domain-contract-40m`  
**Scope:** product lifecycle control operations and their role in declarative operation.

## Review questions

1. Are start/stop/restart product operations explicit without exposing internal network commands?
2. Is success defined by postconditions rather than command dispatch?
3. Does the architecture require a long-lived LifecycleManager?
4. Is the control-surface architecture sufficient to remove the lifecycle blocker from `VPNG-R1.R2`?

## Requirement result

The lifecycle branch now defines:

- `VPNG-R5.R6` — explicit product operations for start, stop and restart;
- `VPNG-R5.R6.R1` — start succeeds only after required startup/readiness/safety postconditions;
- `VPNG-R5.R6.R2` — stop succeeds only after required cleanup or reports incomplete cleanup;
- `VPNG-R5.R6.R3` — restart is a safe transition that cannot hide unresolved previous-state cleanup.

This provides the missing control-operation meaning required by `VPNG-R1.R2`.

## Architecture result

The architecture uses a thin product control surface over procedural lifecycle orchestration.

It deliberately does not introduce a long-lived lifecycle Engine.

The surface may later be exposed by CLI, service manager integration, API or another interface mechanism without changing lifecycle semantics.

The architectural contract is:

```text
start   -> startup orchestration -> success only after postconditions
stop    -> cleanup orchestration -> success only after cleanup postconditions
restart -> required stop/cleanup + new start
```

## Closure decisions

### VPNG-R5.R6

**Verdict:** ACCEPT CLOSURE.

The architectural approach fully answers how lifecycle operations are represented and where their semantics live.

### VPNG-R5.R6.R1

**Verdict:** ACCEPT CLOSURE.

The start control contract is explicit. Detailed startup ordering remains owned by `VPNG-R5.R1`; that does not require a different control-surface architecture.

### VPNG-R5.R6.R2

**Verdict:** ACCEPT CLOSURE.

The stop contract is explicit and delegates actual cleanup mechanics to the already separate cleanup requirements.

### VPNG-R5.R6.R3

**Verdict:** ACCEPT CLOSURE.

Restart is defined as safe lifecycle composition rather than an independent hidden state machine.

### VPNG-R1.R2

**Verdict:** ACCEPT CLOSURE.

Its two architectural concerns are now both answered:

- declarative configuration is handled by the validated `ConfigurationAdapter` boundary;
- product control operations are handled by the thin lifecycle control surface.

The dependency link:

```text
[decomp: VPNG-R5 -> VPNG-R5.R6]
```

correctly records how the missing control-operation semantics were resolved.

## Simplification review

No LifecycleManager is justified.

A long-lived Engine would add ownership/state without a current requirement. The direct control surface plus procedural orchestration is sufficient for accepted semantics.

No specific CLI/API protocol is selected because no requirement currently makes that interface choice product-visible.

## Important non-closure

This review does **not** close:

- `VPNG-R5.R1` startup internals;
- `VPNG-R5.R2` drift recovery;
- `VPNG-R5.R3` retry behavior;
- `VPNG-R5.R4` cleanup internals;
- `VPNG-R5.R5` independent cleanup behavior.

Those requirements may need additional architecture/evidence independently.

## Verdict

**PASS.**

Accept closure for:

- `VPNG-R5.R6`;
- `VPNG-R5.R6.R1`;
- `VPNG-R5.R6.R2`;
- `VPNG-R5.R6.R3`;
- `VPNG-R1.R2`.
