# VPN-GATE NG3 — Availability Hysteresis Closure Review

**Cycle:** `ng3-design-cycle-20261115-managed-domain-contract-40m`  
**Scope:** `VPNG-R3.R3`, `VPNG-R3.R4`, `VPNG-R3.R5` and confirmation children.

## Review questions

1. Can adaptation semantics be closed without deciding the concrete probe transport?
2. Does local probe execution failure avoid becoming false path evidence?
3. Is confirmation state bounded and sufficient?
4. Does availability remain a priority modifier only?

## Architecture result

The Manager consumes normalized semantic evidence:

```text
AvailabilityEvidence:
    logical_path_id
    observation_context
    outcome = positive | negative | no_evidence
```

Only fresh evidence for the current logical path/context enters hysteresis.

Per path, the Manager keeps only:

```text
availability_problem: bool
degradation_progress: bounded counter
recovery_progress: bounded counter
```

Finite degradation/recovery thresholds are local availability-policy parameters. They are
not assumed user-configurable.

Transition rules are asymmetric by current state:

- healthy state confirms degradation from negative evidence;
- problem state confirms recovery from positive evidence;
- opposite evidence resets in-progress confirmation;
- `no_evidence` fabricates neither degradation nor recovery.

## Closure decisions

### VPNG-R3.R3 — degradation demotion

**Verdict:** ACCEPT CLOSURE.

After the finite degradation threshold is reached, `availability_problem` becomes true and
the AvailabilityPriorityCalculator demotes that path relative to allowed paths without an
established problem.

### VPNG-R3.R4 — recovery failback

**Verdict:** ACCEPT CLOSURE.

After the finite recovery threshold is reached, the problem flag clears and effective order
returns to configured preference.

### VPNG-R3.R5 — stable adaptation

**Verdict:** ACCEPT CLOSURE.

A single observation cannot change state when thresholds require more than one accepted
evidence item. The architecture supports finite threshold policy without requiring
unbounded history.

### VPNG-R3.R5.R1 — degradation confirmation

**Verdict:** ACCEPT CLOSURE.

Bounded degradation progress and a finite threshold implement the required confirmation.

### VPNG-R3.R5.R2 — recovery confirmation

**Verdict:** ACCEPT CLOSURE.

Bounded recovery progress and a finite threshold implement the required confirmation.

## Explicitly still open

### VPNG-R3.R6.R3 — evidence adequacy

The hysteresis consumes already-classified semantic evidence, but the architecture still has
to prove what concrete observed property/mechanism is sufficient to classify supported path
failures as positive/negative.

This is independent from hysteresis.

### VPNG-R3.R6 and VPNG-R3 parent

Remain open because adequacy of the observation mechanism is part of their promise.

## Simplification review

No evidence history, time window, attempt journal, replay, logical epoch or universal
availability state machine is required.

Local probe execution failure is represented as diagnostic/`no_evidence` unless the
selected observation contract proves it is itself path evidence.

## Purpose escalation check

The Purpose chain remains clear. The remaining uncertainty is technical adequacy of the
observation mechanism, not uncertainty over why availability evidence is needed.

No human requirement escalation is required.

## Verdict

**PASS — partial closure.**

Accept closure for:

- `VPNG-R3.R3`;
- `VPNG-R3.R4`;
- `VPNG-R3.R5`;
- `VPNG-R3.R5.R1`;
- `VPNG-R3.R5.R2`.

Keep `VPNG-R3.R6.R3`, `VPNG-R3.R6` and `VPNG-R3` open.
