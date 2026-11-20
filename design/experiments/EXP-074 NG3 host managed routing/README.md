# EXP-074 — current host managed-destination routing

## Requirement trace

This experiment provides Linux acceptance evidence for:

- `VPNG0002-R2.R3.R1.R1`;
- `VPNG0002-R2.R3.R1.R1.R1`;
- `VPNG0002-R2.R3.R1.R1.R2`;
- the host-routing half of `VPNG0002-R2.R6`.

## Question

Does the selected current host owner implement one authoritative managed-destination
table such that:

- matching managed destinations are sent through `vpng0`;
- `0.0.0.0/0` captures non-local ordinary/forwarded traffic even when host `main`
  contains a more-specific route;
- packets already arriving from `vpng0` bypass managed capture and use ordinary
  `main`;
- kernel local delivery remains local;
- cleanup leaves unrelated host `main` routes unchanged?

EXP-072 remains historical evidence for the superseded specificity-preserving paired
RPDB bootstrap. It is not the acceptance gate for the current semantics.

## Execution

```bash
PYTHONPATH=design/NG3/code/python sudo --preserve-env=PYTHONPATH \
  python3 "design/experiments/EXP-074 NG3 host managed routing/exp074_host_managed_routing.py"
```
