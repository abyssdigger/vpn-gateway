# EXP-077 — Release-1 peaceful host-routing helper

## Status

COMPLETE — PASS — SELECTED as privileged acceptance evidence for `VPNG0001-R2.R2`.

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


## Result

See `EXP-077-result-20261120.md`.

Workflow run `44741376166`, job `linux-host-managed-routing`
(`136305711716`) completed with `EXP077_RESULT=PASS`.

## Post-result lifecycle

- Logical evidence state: **PROVEN FACT / SELECTED**.
- Current disposition: **selected for Release-1 peaceful host-routing helper**.
- Applicability: exact acceptance evidence for `VPNG0001-R2.R2`.

### Coverage transition

Previous coverage:

- `VPNG0001-R2.R2` had accepted lifecycle semantics but no selected lower realization;
- EXP-059/060/072 provided reusable facts for main-route specificity preservation,
  stack-ingress bypass and managed-L3 device-only routing;
- EXP-074 proved the intentionally stronger authoritative behavior now assigned to the
  postponed aggressive helper.

Current coverage:

- `VPNG0001-R2.R2` <- EXP-077 for the selected Release-1 Linux lowering;
- EXP-074 remains selected for `VPNG0001-R2.R3.R1` and is not superseded by EXP-077.

Transition:

- the simple helper was separated from authoritative host-routing ownership, so its accepted
  realization must allow later administrator non-default routes to win without reconciliation
  and must preserve foreign replacements during lifecycle cleanup.

EXP-077 does not supersede EXP-059/060/072 as technical facts; it reuses their proven lower
properties in the current weaker lifecycle-helper contract.
