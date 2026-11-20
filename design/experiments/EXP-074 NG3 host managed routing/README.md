# EXP-074 — current host managed-destination routing

## Current requirement trace

This experiment is exact Linux acceptance evidence for:

- `VPNG0001-R1.R5.R1` — authoritative managed-destination routing for the opt-in aggressive
  host-routing helper.

The requirement IDs originally attached to this experiment under the removed
`VPNG0002-R2.R3.R1...` direction decomposition are historical and no longer define current
product semantics. `VPNG0002-R2.R6` remains a core STACK return-affinity requirement, but
EXP-074 is no longer used to make host routing an unconditional part of that core contract.

The aggressive helper itself is constrained out of Release 1 by `VPNG0001-R1.R5.C1`.

## Question

Does the tested authoritative host-routing realization implement one managed-destination
table such that:

- matching managed destinations are sent through `vpng0`;
- `0.0.0.0/0` captures non-local ordinary/forwarded traffic even when host `main`
  contains a more-specific route;
- packets already arriving from `vpng0` bypass managed capture and use ordinary
  `main`;
- kernel local delivery remains local;
- cleanup leaves unrelated host `main` routes unchanged?

EXP-072 remains valid lower evidence for device-only managed-L3 routing and for the older
specificity-preserving bootstrap mechanism. EXP-074 is the acceptance gate only for the
aggressive authoritative-routing child, not for the simple lifecycle helper.

## Execution

```bash
PYTHONPATH=design/NG3/code/python sudo --preserve-env=PYTHONPATH \
  python3 "design/experiments/EXP-074 NG3 host managed routing/exp074_host_managed_routing.py"
```
