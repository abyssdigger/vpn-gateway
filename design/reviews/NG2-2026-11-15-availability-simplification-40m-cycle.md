# NG2 cycle — availability simplification migration

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-availability-simplification-40m`  
**CYCLE_INTERVAL:** 40 minutes  
**Cycle base:** `4fe5af43b8891505bfbaae0f27b8a0c70b4471c6`

## Goal

Replace the superseded availability window/evidence pipeline with the bounded
`availability_problems` collector model and aggressively remove obsolete code/artifacts.

Expected deletions/simplifications:

- logical observation windows;
- `evidence_epoch`;
- `elapsed_intervals`;
- `ProbeWindowBoundaryInfo`;
- Manager-owned availability routing state;
- RuntimeStateManager availability-priority mediation;
- ProfileAvailabilityEvidence / ProbeProfileEvidenceCalculator;
- confirmed-live terminology and helpers where no longer needed;
- publication/source-order machinery that existed only for window boundaries.

Preserve only:

- physical ProbeRules/readiness generation guard;
- physical send cadence;
- bounded ping workers;
- tick cadence;
- local execution diagnostics;
- availability_problems collector state inside PayloadTrafficManager;
- sole serialized route materializer.
