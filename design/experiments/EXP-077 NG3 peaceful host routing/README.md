# EXP-077 — Release-1 peaceful host-routing helper

## Status

PREPARED — privileged acceptance evidence for `VPNG0001-R2.R2`.

## Requirement trace

- `VPNG0001-R2`;
- `VPNG0001-R2.R2`.

## Question

Can the selected Release-1 helper provide useful ordinary-host routing assistance over the
managed L3 boundary without taking authoritative ownership of ordinary host routing?

The selected Linux order is:

```text
local
    -> local delivery

iif managed-boundary lookup main
    -> STACK-origin traffic uses ordinary host routing

lookup main suppress_prefixlength 0
    -> explicit non-default administrator main routes win

lookup peaceful-helper-table
    -> helper destinations use the managed boundary

ordinary main/default
    -> unmatched traffic remains ordinary
```

The helper table/rules use a dedicated protocol marker so lifecycle cleanup can identify its
own contributions. No periodic reconciliation is part of this experiment.

## PASS criterion

PASS requires all of the following on a real routed HOST↔STACK boundary:

1. with helper-managed `0.0.0.0/0`, otherwise-unmatched ordinary traffic enters STACK;
2. an administrator non-default `main` route wins over helper `0.0.0.0/0`;
3. a more-specific administrator route added after helper activation wins immediately without
   helper reconciliation;
4. traffic arriving from STACK is not captured back into STACK;
5. the helper does not modify ordinary `main` routes;
6. after an administrator replaces one helper-owned rule with a foreign rule at the same
   priority, peaceful cleanup leaves that replacement untouched while removing the remaining
   helper-owned state;
7. final ordinary `main` state is identical to its pre-helper state.

A PASS proves the selected Release-1 peaceful-helper lowering. It does not supersede EXP-074,
which remains evidence for the separately postponed aggressive authoritative helper.
