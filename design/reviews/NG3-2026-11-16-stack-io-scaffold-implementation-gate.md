# NG3 implementation gate — four-chain managed nft scaffold

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-config-format-35m`

## Scope

Extend the already accepted invariant nft scaffold implementation from:

```text
payload_forward
payload_postrouting
```

to the complete currently accepted invariant managed-stack set:

```text
stack_input
payload_forward
stack_output
payload_postrouting
```

No local/system allow rules are part of this unit.

## Requirements

**Implements:**

- `VPNG-U004-R4.R6.R1.R5`;
- `VPNG-U004-R4.R6.R1.R5.R1`;
- `VPNG-U004-R4.R4`;
- `VPNG-U004-R4.R2`;
- existing nft ownership/safe-transition requirements already implemented by the scaffold
  prepare path.

All governing R/C nodes are `[closed]`.

## Evidence prerequisite

EXP-040 passed in GitHub Actions run `43910097781` and proves the exact INPUT/OUTPUT base
chain metadata and terminal behavior.

## Components

No new component is required.

- existing pure scaffold Calculator/classifier: recognize all four exact invariant chains;
- existing Linux nft scaffold backend: create/add only those exact chain specs;
- existing guarded scaffold Executor operation: close/recheck `ForwardingGate`, mutate only
  classified missing invariant chains, reobserve and verify exact postcondition.

## Safety

The existing scaffold-only executor remains intentionally restrictive:

- unclassified rules/objects block repair;
- wrong metadata is conflict, not adoptable state;
- root forwarding remains disabled throughout mutation;
- success requires fresh exact postcondition.

Adding INPUT/OUTPUT chains therefore does not grant authority to create their future allow
rules.

## Tests/evidence

Required:

- rootless exact/missing/conflict tests for all four specs;
- backend script-generation tests;
- privileged scaffold observation integration;
- privileged guarded create/repair integration;
- complete NG3 Python workflow.

## Simplification

Do not introduce:

- a second scaffold executor;
- separate INPUT/OUTPUT lifecycle owner;
- user firewall parsing;
- system-exception policy;
- generalized arbitrary base-chain builder beyond the exact accepted invariant specs.

## Requirement-state inventory

### `decomp`

Six links, all resolved; pending: none.

### `unreal`

none

### `[rejected_closure]`

none

## Gate verdict

**PASS — implementation may proceed.**
