# VPN-GATE NG3 — Declarative Configuration Boundary Review

**Cycle:** `ng3-design-cycle-20261115-managed-domain-contract-40m`  
**Scope:** minimal declarative configuration contract needed by accepted NG3 requirements.

## Review questions

1. Does the configuration model express product intent rather than Linux operation sequences?
2. Can externally provisioned VPN channels be bound to logical VPN paths without defining a universal configuration framework?
3. Are invalid/ambiguous configurations rejected before dependent network mutation?
4. Does the architecture remain split into domain-specific contracts rather than one global mutable runtime model?

## Requirement result

The configuration branch now contains:

- `VPNG-R1.R2.R1` — configuration describes logical product entities/relationships rather than internal Linux actions;
- `VPNG-R1.R2.R2` — configuration can express logical VPN path identity plus binding intent;
- `VPNG-R1.R2.R3` — invalid/ambiguous declarations are rejected before dependent network mutation.

The previous onboarding block is resolved:

```text
VPNG-R1.R3.C1.R1
  [decomp: VPNG-R1.R2 -> VPNG-R1.R2.R2]
```

## Architecture result

The architecture introduces one Direct Machinery boundary:

`ConfigurationAdapter`

It translates external declarative configuration into validated normalized domain intents.

The first required contract is:

```text
VPNPathIntent:
    logical_path_id
    binding_intent
```

The Adapter does not own live configuration state, network mutation, VPN provisioning or routing policy.

Domain intents remain separate rather than being collapsed into one global runtime configuration object.

## Closure decisions

### VPNG-R1.R2.R1

**Verdict:** ACCEPT CLOSURE.

The declarative boundary and normalized domain-contract approach answer how user intent is kept independent from lower networking mechanics.

### VPNG-R1.R2.R2

**Verdict:** ACCEPT CLOSURE.

The `VPNPathIntent` contract provides the required logical path identity plus binding intent without requiring a final file/API syntax.

### VPNG-R1.R2.R3

**Verdict:** ACCEPT CLOSURE.

The Direct `ConfigurationAdapter` contract requires complete validation before dependent network mutation and rejects ambiguous semantic results.

### VPNG-R1.R3.C1.R1

**Verdict:** ACCEPT CLOSURE.

The architecture now defines the required contents of the administrator onboarding contract:

- external VPN provisioning remains administrator-owned;
- expected endpoint placement is defined;
- logical path identity/binding intent is defined;
- acceptance/rejection must be observable.

Writing the concrete per-integration instructions remains documentation implementation work, not an unresolved architecture decision.

## Simplification review

No separate ConfigManager is justified.

No current accepted requirement demands:

- live reload;
- persistent configuration database;
- configuration version graph;
- distributed config;
- dynamic plugin discovery;
- generic schema registry;
- one universal normalized runtime state object.

If later requirements need any of these, they must be introduced by a new requirement/refinement rather than assumed by the current configuration boundary.

## Closure/evidence semantics

This review is sufficient acceptance evidence for the architecture-level closure. It does not prove the future parser/adapter implementation correct.

## Verdict

**PASS.**

Accept architecture closure for:

- `VPNG-R1.R2.R1`;
- `VPNG-R1.R2.R2`;
- `VPNG-R1.R2.R3`;
- `VPNG-R1.R3.C1.R1`.

The current onboarding chain is no longer blocked by managed-domain, logical-path identity or configuration-contract semantics.
