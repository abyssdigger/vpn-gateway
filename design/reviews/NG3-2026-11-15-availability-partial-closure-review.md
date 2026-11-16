# VPN-GATE NG3 — Availability Partial Closure Review

**Cycle:** `ng3-design-cycle-20261115-managed-domain-contract-40m`  
**Scope:** independently settled parts of `VPNG-R3` availability architecture.

## Purpose

The availability subtree must not be marked closed as a whole while evidence/confirmation
semantics remain unresolved.

This review accepts only nodes whose architecture is independent from those open questions.

## Closure decisions

### VPNG-R3.R1 — configured preference

**Verdict:** ACCEPT CLOSURE.

`PayloadPolicyIntent.configured_preference` provides one deterministic order among already
allowed paths. `AvailabilityPriorityCalculator` consumes that order as the baseline.

### VPNG-R3.R2 — adaptation changes priority, not permission

**Verdict:** ACCEPT CLOSURE.

The architecture structurally separates:

- allowed path membership from `PayloadPolicyIntent`;
- availability state from the membership contract;
- availability adaptation as an ordering modifier only.

No availability path can be added to the allowed set.

### VPNG-R3.R6.R1 — evidence identity

**Verdict:** ACCEPT CLOSURE.

Availability observations carry logical path identity, and the logical-path binding model now
separates that stable identity from transient concrete endpoints.

### VPNG-R3.R6.R2 — evidence freshness

**Verdict:** ACCEPT CLOSURE.

The `AvailabilityProbeAgent` uses a narrow observation-generation token solely to reject
late results from superseded physical observation contexts.

The token has no routing-policy or evidence-history semantics.

### VPNG-R3.R7 — availability-neutral baseline

**Verdict:** ACCEPT CLOSURE.

When no path has an established availability problem, the effective order equals configured
preference. Availability therefore introduces no startup penalty merely because observation
is enabled.

## Intentionally open

### VPNG-R3.R3 / VPNG-R3.R4

Degradation/failback shape exists, but the exact sufficient-evidence semantics are not yet
settled.

### VPNG-R3.R5 / R1 / R2

Bounded confirmation state is selected, but the final confirmation policy remains open,
including the role/configurability of thresholds and evaluation boundaries.

### VPNG-R3.R6 / R3

Active observation is selected, but the required observation property/mechanism for
supported failure scenarios is not yet sufficiently specified to close evidence adequacy.

### VPNG-R3 parent

Remains open because the material behavior above is still unresolved.

## Verdict

**PASS — partial closure only.**

Accept closure for:

- `VPNG-R3.R1`;
- `VPNG-R3.R2`;
- `VPNG-R3.R6.R1`;
- `VPNG-R3.R6.R2`;
- `VPNG-R3.R7`.

Do not close the rest of the R3 subtree.
