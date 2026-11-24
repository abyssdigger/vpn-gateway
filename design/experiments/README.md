# Experiment stand: operational runbook

This document governs the preparation and execution of VPN-GATE experiments that
use a live or disposable stand. The project-level experiment registry and evidence
policy remain in [PROJECT-CONVENTIONS.md](../../PROJECT-CONVENTIONS.md) and
[CONTINUOUS-DEVELOPMENT.md](../../CONTINUOUS-DEVELOPMENT.md).

## Explicit stand baseline

Every experiment must identify the exact stand used.

- When the stand changes, describe the new stand completely: nodes, roles,
  significant interfaces/addresses, connections, traffic direction and injection
  points for artificial disturbances.
- When reusing a stand, explicitly cite the experiment that describes it and list
  all deviations. Never rely on implicit inheritance from prior chat context.

## Preflight sequence

Before running an experiment, follow this order:

1. **Diagnose** the current stand with read-only commands: identify which required
   components already exist, are running, are stopped or differ from the expected
   baseline.
2. **Restore only what is missing** to the known starting state.
3. **Verify** the restored stand and baseline connectivity.
4. Only then run the experiment's mutation/test commands.

The experiment description must give the diagnostic, restoration and verification
commands in execution order. Do not mechanically copy all of them into the harness:
a harness should automate the experiment itself and only prerequisites necessary
for safe execution.

Preflight must validate actual relevant prerequisites, such as concrete interface
identity, `IFF_UP`, peer/address mapping, baseline routing and reachability of
the test endpoint through every required path.

When service startup is asynchronous relative to socket/listener readiness,
`systemctl start` alone is not proof of endpoint readiness. An interactive
check may specify a short wait; automation should prefer bounded readiness polling.

Before a copy/paste command block that launches the harness in an interactive
terminal, explicitly separate earlier terminal output with `clear`; if the
terminal is corrupted, use `reset`. This avoids accidentally copying old
output or commands into the new experiment.

## Coordinated manual actions

If the harness enters a polling window and requires an operator action on a
different node, supply all of the following **before launching** the harness:

- exact manual-action command;
- node on which to execute it;
- exact output marker that triggers the action;
- polling-window timeout;
- exact cleanup/restore command.

The harness must print an unambiguous action marker before the window, for example
`ACTION REQUIRED NOW: create primary outage`. A neutral message such as
`will wait up to ...` is insufficient as the sole signal for an action that must
be performed now. Do not rely exclusively on instructions printed after polling
has already started.

## Evidence provenance

Record the stand baseline, any deviations, execution evidence and result in the
experiment dossier under `design/experiments/`. A technical `Result` is not the
project's `Disposition`; the latter belongs in the central registry
`design/vpn-gateway-experiments.md`.
