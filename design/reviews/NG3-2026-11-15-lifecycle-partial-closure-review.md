# VPN-GATE NG3 — Lifecycle Partial Closure Review

**Cycle:** `ng3-design-cycle-20261115-managed-domain-contract-40m`  
**Scope:** independently settled lifecycle requirements under `VPNG-R5`.

## Closure decisions

### VPNG-R5.R1 — predictable startup

**Verdict:** ACCEPT CLOSURE.

The accepted architecture defines startup as procedural orchestration behind the product
`start` control surface.

Startup must:

- establish the isolated/protective managed-network boundary first;
- create/initialize required owned domains according to their explicit prerequisites;
- verify required safety/readiness postconditions;
- report start success only after those postconditions hold.

A separate LifecycleManager is not required to express this architecture.

The exact command ordering inside independent lower domains is implementation detail unless a
later requirement or experiment proves additional ordering semantics are product-relevant.

### VPNG-R5.R4 — owned-state cleanup

**Verdict:** ACCEPT CLOSURE.

The architecture distinguishes VPN-GATE-owned state from externally administrator-owned VPN
provisioning.

Owned lower-network state is cleaned through its domain Adapter/Executor boundary, and the
product `stop` operation succeeds only after required cleanup postconditions or reports
incomplete cleanup.

### VPNG-R5.R5 — independent cleanup attempts

**Verdict:** ACCEPT CLOSURE.

Procedural shutdown orchestration attempts cleanup for independent owned domains even if a
different cleanup fails and preserves all material failures for observability.

No global all-or-nothing cleanup transaction is introduced.

### VPNG-R5.R2 — drift recovery

**Verdict:** KEEP OPEN.

The ownership/convergence boundary exists, but the architecture has not yet settled the
trigger by which externally caused drift is detected during otherwise idle operation.

A periodic audit, environment event, operation-triggered observation or combination are
architecture choices that must not be guessed merely because NG2 used one.

### VPNG-R5.R3 — retry after recoverable failure

**Verdict:** KEEP OPEN.

The Executor supports safe re-observation/retry semantics, but the architecture has not yet
settled what causes a recoverable failed desired state to be retried when no new external
request arrives.

This shares the unresolved trigger question with `VPNG-R5.R2`.

### VPNG-R5 parent

**Verdict:** KEEP OPEN.

The parent requires autonomous recovery from ordinary recoverable environmental changes, so
it cannot close while R5.R2/R3 trigger semantics remain unresolved.

## Purpose/Reason escalation check

The open R5.R2/R3 purposes remain clear:

- R5.R2 exists so ordinary drift does not require manual reconstruction;
- R5.R3 exists so a temporary technical failure does not permanently disable the function.

The uncertainty is architectural (`how/when to re-observe/retry`), not semantic
(`why these obligations exist`), so no human escalation is required at this point.

## Verdict

**PASS — partial closure only.**

Accept closure for:

- `VPNG-R5.R1`;
- `VPNG-R5.R4`;
- `VPNG-R5.R5`.

Keep R5.R2, R5.R3 and parent R5 open.
