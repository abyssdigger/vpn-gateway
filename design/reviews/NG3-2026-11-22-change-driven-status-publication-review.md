# NG3 2026-11-22 — change-driven runtime status publication review

**Scope:** `VPNG-M001-R2.R1.R5`; deduplicate runtime status publication while keeping
periodic observation/reconciliation unchanged.

## Verdict

**PASS — ACCEPT ARCHITECTURE CLOSURE AND IMPLEMENTATION.**

## Requirement / architecture

`VPNG-M001-R2.R1.R5` requires a new publication only after semantic
`RuntimeStatusSnapshot` change. Re-observing an equivalent snapshot must not itself create
another publication event.

`A.008 RuntimeStatusAgent` owns the corresponding change-driven publication decision.
Periodic audit/reconcile cadence remains independent and may continue unchanged.

## Implementation

`RuntimeStatusFilePublisher` retains only the last **successfully published** immutable
snapshot.

- first snapshot: publish JSON + compact text;
- semantically equal later snapshot: no writes;
- changed snapshot: publish both surfaces;
- failed publication: the candidate is not remembered as published, so a later attempt is not
  suppressed.

The alpha's one-second audit/reconcile loop remains intact. Its previous unconditional
status-file writes now call the publisher, so a stable state does not cause periodic file
replacement.

## Evidence

NG3 Python run `44960588066`, source commit
`aa20ff1cddc24c7a7f7ee52913da9ea693a04714`:

- unit job `137018285187`: **PASS**, **794 tests**, OK;
- installed alpha smoke job `137018285297`: **PASS**;
- all other completed jobs at review time: PASS.

Installed alpha evidence holds a stable current state across more than two one-second audit
ticks and confirms that neither `status.json` nor `status.txt` receives a new mtime:

```text
EXP051_RUNTIME_STATUS_CHANGE_DRIVEN_PUBLICATION=PASS
EXP051_RESULT=PASS
```

Existing status markers for zero-path, first-path and recreated VPN generation also remain
PASS, proving that real semantic changes continue to publish the new current state.

## Findings and dispositions

### F1 — periodic reconciliation had been coupled to periodic presentation writes

**Decision:** accepted.  
**Resolution:** fixed.

Observation cadence remains periodic; publication is now change-driven.

### F2 — deduplication must not hide a failed publication

**Decision:** accepted.  
**Resolution:** fixed.

The remembered snapshot advances only after both current alpha presentation writes return
successfully.

### F3 — deduplication must compare semantic status, not rendered text or timestamps

**Decision:** accepted.  
**Resolution:** fixed.

The publisher compares immutable `RuntimeStatusSnapshot` values directly. Rendering remains
a downstream presentation detail.

## Closure decision

`VPNG-M001-R2.R1.R5` may move from `pending_closure` to `closed`.
