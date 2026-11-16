# NG2 review — ProbeExecutionAgent publisher failure isolation

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-publisher-failure-recovery-40m`  
**Scope:** process-local publisher exceptions from ProbeExecutionAgent

## Verdict

**PASS after test stabilization and one cleanup.**

## Failure modes reviewed

ProbeExecutionAgent has three process-local publication paths:

```text
logical tick
    -> AvailabilityTick publisher

successful physical reply
    -> AvailabilityGoodNews publisher(s)

local execution state
    -> ProbeExecutionDiagnosticInfo publisher
```

A subscriber exception must not corrupt unrelated Agent execution.

## F1 — tick publisher exception could abort due processing / scheduler thread

**Disposition:** accepted and fixed.

Tick publication is isolated per item. A failing tick subscriber is logged and remaining
due physical sends are still launched.

The Agent does not reinterpret the failure as availability state.

## F2 — one good-news consumer could block fanout to other logical consumers

**Disposition:** accepted and fixed.

Good-news publication is isolated per logical consumer. One subscriber exception is
logged and fanout continues for the remaining current consumers of the same physical
plane.

No retry queue is introduced.

## F3 — diagnostic publisher failure could suppress good news

**Disposition:** accepted and fixed.

READY/ERROR diagnostic publication is now isolated. A diagnostic subscriber exception does
not abort the worker before good-news fanout.

## F4 — failed diagnostic publication poisoned duplicate suppression

**Disposition:** accepted and fixed.

The diagnostic cache records the candidate state before publication to serialize competing
workers. If publication raises, that exact cache entry is removed again.

A later identical diagnostic may therefore be published again.

## F5 — first retry regression raced worker cleanup

**Disposition:** test defect, fixed.

The interrupted cycle's last CI had 304/305 tests passing. The failing regression scheduled
the next physical send immediately after observing the first driver call, but diagnostic
publication occurs before the worker's `finally` releases the in-flight key.

The corrected regression first observes good news, which proves the worker advanced past
the failed READY publication, then retries scheduling until the next physical send is
accepted.

No production rollback was required.

## F6 — broad exception catch around the entire scheduler loop

**Disposition:** accepted and fixed.

After known publisher failures were isolated at their actual boundaries, a broad
`except Exception` around `process_due()` became counterproductive: it would hide an
unexpected internal Agent defect and leave a silently degraded long-lived scheduler.

It was removed. Known external callback failures remain locally isolated and logged;
unexpected Agent failures remain visible.

## Delivery semantics

Publisher failure isolation is deliberately **best-effort local containment**, not a new
reliable event bus:

- tick/good-news callbacks are not journaled or replayed;
- one failed good-news callback does not block other consumers;
- a failed READY/ERROR diagnostic can be retried when the same state is observed again;
- failed INACTIVE diagnostic publication is logged but not persisted as a retry queue.

Adding reliable delivery here would reintroduce queue/revision machinery without a
current product requirement.

## Evidence

Final code head for this review unit:

`f699095d20a45cd758070ec0f3f89bdc6551ae27`

GitHub Actions `NG2 Python` run **719**:

- compile: PASS;
- **305 rootless unit tests PASS**;
- selective probe-process isolation: PASS;
- EXP-025: PASS;
- EXP-026: PASS;
- EXP-027: PASS;
- nft ICMP selector: PASS;
- Linux instance lifecycle: PASS;
- Linux Adapter: PASS;
- Linux LOCAL_PROCESS: PASS;
- Linux dataplane: PASS.

No external experiment is required.

## Remaining review direction

Check adjacent process-local publisher boundaries for the same exception-propagation
mistake. Do not introduce reliable delivery/retry infrastructure unless an explicit status
or event contract later requires it.
