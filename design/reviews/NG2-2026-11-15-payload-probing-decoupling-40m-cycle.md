# NG2 cycle — payload/probing decoupling cleanup

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-payload-probing-decoupling-40m`  
**CYCLE_INTERVAL:** 40 minutes  
**Base:** `ccfb625cbe7d60274991c920bd960f91f4cbec5a`

## Ordered work

1. Remove superseded probing concepts from payload contracts/ownership.
2. Quantify code/artifact reduction before testing.
3. Run deterministic and privileged CI evidence that needs no new external experiment.
4. Only after positive tests, revise payload-management architecture/documentation as a whole.

Cleanup targets follow the preceding payload-tail review and include structural Request
purity, probe-independent availability-priority input, cadence/hysteresis separation,
inactive-availability true no-op, stale runtime snapshot fields and neutral lower routing
boundary terminology.
