# NG2 cycle — availability collector/materializer simplification

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-availability-collector-materializer-40m`  
**CYCLE_INTERVAL:** 40 minutes  
**Cycle base:** `a5e5d8ea90d4c96b023c767783af9af1b086dbaf`

## Review unit

Replace the current availability execution/event assumptions with the agreed minimal model:

- per channel, good-news arrivals are colorless and aggregate into a saturating counter;
- the counter saturates at the configured recovery-good-news requirement;
- tick is a single pending fact, not a queued/counting event;
- a collector owns channel status and degradation/recovery policy;
- GOOD -> BAD can happen only while processing a tick;
- BAD -> GOOD can happen only while processing good news;
- accumulated good news is boolean-significant while GOOD and count-significant while BAD;
- collector snapshots are handed synchronously to one transactional materializer;
- materialization is assumed orders of magnitude faster than the tick cadence, so events accumulated during materialization are processed afterward as current observations;
- the materializer compares the desired snapshot with the last successfully materialized snapshot and converges only on a difference.

The unit must review and remove architecture/code machinery that exists only to support queued logical boundaries, catch-up interval counting, or logical evidence epochs when those concepts are no longer required by this model.

No new EventEnvelope machinery will be introduced in this unit.
