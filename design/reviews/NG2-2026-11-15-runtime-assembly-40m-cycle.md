# NG2 cycle — runtime assembly

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-runtime-assembly-40m`  
**CYCLE_INTERVAL:** 40 minutes  
**Base:** `b4fbdff832d236dd827baf4179bf28f34ad559d8`

## Review unit

Assemble the already-tested payload/probing contracts without reintroducing availability
evidence mediation.

Target flow:

```text
normalized runtime/config projection
    +--> AvailabilityProbeSetRequest
    +--> AvailabilityPriorityConfig
    +--> PayloadTrafficStateRequest

AvailabilityProbeManager
    -> ProbeExecutionPlan
    -> ProbeExecutionAgent
         +--> AvailabilityGoodNews -> PayloadTrafficManager
         +--> AvailabilityTick     -> PayloadTrafficManager
         +--> ProbeExecutionDiagnosticInfo -> diagnostics/status
```

The review unit includes only the smallest runtime assembly required to connect these
existing contracts, plus deterministic/privileged tests and autonomous review.
