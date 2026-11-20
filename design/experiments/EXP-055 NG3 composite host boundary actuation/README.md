# EXP-055 — NG3 composite host-boundary actuation

## Status

PREPARED — evidence pending.

## Purpose

Validate the production-shaped host-boundary pipeline after EXP-053/054:

1. canonical Release-1 config -> host-boundary intent;
2. fresh underlay observation for every captured VPN client endpoint;
3. exact owned/external pin classification;
4. Linux desired-state lowering, including split-default full tunnel;
5. bounded route/RPDB + nft convergence;
6. cleanup in capture-first reverse order.

Two independent scenarios are required:

- full-tunnel outbound bootstrap with an external VPN transport endpoint;
- inbound stateful return for a forwarded LAN flow.

## PASS criterion

PASS requires both scenarios and final owner cleanup to succeed in one privileged run.

Run:

```sh
PYTHONPATH=design/NG3/code/python sudo --preserve-env=PYTHONPATH python3 \
  "design/experiments/EXP-055 NG3 composite host boundary actuation/exp055_host_boundary_actuation.py"
```
## Post-result lifecycle

- Logical evidence state: **PREPARED / UNPROVEN**.
- Current disposition: **historical_only**.
- Applicability: **утратил применимость до завершения эксперимента**.

The composite host-boundary actuation pipeline depended on the removed host-return/bootstrap
architecture. It was never completed, and current code contains no compatibility owner for it.

