# NG3 — developer execution trace decision gate

**Status:** BLOCKED — explicit project-holder decision required  
**Created:** 2026-11-22  
**Requirement:** `VPNG-D001-R2`

## Accepted need

VPN-GATE needs a separately enableable developer execution trace capable of reconstructing
internal execution paths more deeply than the ordinary DEBUG operational log.

The intended distinction is:

```text
INFO   = what materially changed in the environment/lifecycle
DEBUG  = how a component reacted at semantic component level
TRACE  = how execution proceeded inside the component
```

Operational logging work must not silently implement TRACE semantics.

## Blocked decisions

Architecture and implementation remain blocked until the project holder separately decides at
least:

- exact function-entry/function-return coverage boundary;
- which branch decisions must be recorded;
- parameter/result representation and truncation rules;
- explicit destination/file lifecycle and rotation expectations;
- acceptable timing/performance perturbation;
- secret/sensitive-data policy for arguments and returned values;
- whether the trace format has any stability promise;
- whether trace instrumentation is source-level/manual, generated, runtime-assisted or a
  combination.

## Re-entry condition

Resume only after an explicit decision on the trace contract. Until then no production
instrumentation, config field or logging level named `trace` should be added merely as an
extension of operational logging.

## Requirement-state inventory

- `VPNG-D001-R2`: `decomposition: incomplete`, intentionally without architecture closure;
- active `decomp`: none introduced;
- active `unreal`: none;
- active `broken`: none;
- `rejected_closure`: none.
