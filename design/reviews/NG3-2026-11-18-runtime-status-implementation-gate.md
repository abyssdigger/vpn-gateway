# NG3 2026-11-18 — RuntimeStatusAgent alpha implementation gate

## Scope

Implement the accepted current-state observability contract for the executable Python alpha
without inventing a final stable external API.

## Requirements

**Implements:**

- `VPNG-U006-R6`;
- `VPNG-U006-R6.R1`;
- `VPNG-U006-R6.R2`;
- `VPNG-U006-R6.R3`;
- `VPNG-U006-R6.R4`;
- `VPNG-U007-R7.R1`;
- `VPNG-U007-R7.R1.R1`;
- `VPNG-U007-R7.R3`.

The complete R6 ancestry is already closed. No requirement or product-semantic change is
needed for this unit.

## Scenario

An operator needs to determine what the running alpha accepted, which VPN paths are currently
confirmed for use, whether the current policy is ready, and which current problem blocks the
required behavior without reconstructing that answer from journal messages or kernel commands.

## Components and responsibilities

### RuntimeStatusAgent

A non-owning Agent retains only the latest current snapshot for the fixed authoritative
status domains required by R6:

- accepted configured intent;
- confirmed effective path/policy projection;
- availability projection;
- lifecycle/readiness and current blocking diagnostics.

It does not actuate networking, recompute policy from kernel state, keep history, or invent one
aggregate Profile verdict.

### Alpha status presentation

The current alpha publishes the Agent's current snapshot as atomically replaced JSON under its
existing systemd-owned runtime directory.

This is intentionally an **alpha presentation mechanism**, not a stable Release-1 CLI/API
contract. The semantic `RuntimeStatusSnapshot` remains independent from the renderer/path.

## Truthfulness boundary

- accepted config is reported from the parsed/accepted `Release1Config`, not reconstructed
  from Linux state;
- effective paths are promoted to confirmed status only after the corresponding reconciliation
  result is confirmed;
- a failed/unknown reconcile invalidates current confirmed-effective status rather than
  continuing to present a previous desired/binding projection as current fact;
- availability is explicitly `disabled` for the current alpha because the alpha rejects
  `availability_check`; it is not fabricated from route state;
- current blocking diagnostics remain visible while they are current;
- no unbounded event history is stored.

## Simplification review

Rejected as unnecessary for this unit:

- status database/history/replay;
- metrics store;
- kernel polling performed by the status component itself;
- a second policy owner;
- a generic arbitrary-source event framework;
- a final stable CLI/API schema.

## Evidence plan

Rootless unit evidence must prove:

1. current-only composition, with no history semantics;
2. desired/configured state is distinct from confirmed-effective state;
3. failed reconciliation invalidates confirmed-effective state and exposes a blocking problem;
4. alpha JSON serialization is deterministic and atomically replaceable;
5. current Profile path order is reported from a successful confirmed projection.

Alpha smoke must additionally prove the installed runtime creates a readable current status
snapshot that reaches READY/confirmed state and is updated after a current endpoint generation
change.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U006-R6` -> `VPNG-M001-R2.R1`
- `VPNG-U006-R6.R1` -> `VPNG-M001-R2.R1.R1`
- `VPNG-U006-R6.R2` -> `VPNG-M001-R2.R1.R2`
- `VPNG-U006-R6.R3` -> `VPNG-M001-R2.R1.R3`
- `VPNG-U006-R6.R4` -> `VPNG-M001-R2.R1.R4`
- `VPNG-U007-R7.R1` -> `VPNG-D001-R1.R1.R1`
- `VPNG-U007-R7.R1.R1` -> `VPNG-D001-R1.R1.R1.R1`
- `VPNG-U007-R7.R3` -> `VPNG-D001-R1.R1.R3`

The original IDs in the historical body are intentionally preserved.
