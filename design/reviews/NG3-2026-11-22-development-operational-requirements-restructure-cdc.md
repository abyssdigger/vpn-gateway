# NG3 2026-11-22 — development / operational requirements restructure CDC review

**Scope:** separate owner-imposed development-cost and operational-cost requirements, migrate
the former lifecycle/observability/implementation-quality roots without changing their
accepted semantics, promote the human current-state and resource-suitability declarations,
and preserve historical traceability across alpha ID migration.

## Verdict

**PASS — REQUIREMENT RESTRUCTURE DEVELOPMENT BLOCK COMPLETE.**

The current requirement tree now classifies engineering requirements by the lifecycle process
whose cost they optimize:

- `VPNG-D001` — development/change/maintenance cost;
- `VPNG-M001` — administration/diagnosis/operation cost;
- `VPNG-U001`–`VPNG-U004` — functional/user-facing VPN behavior and safety.

This classification is independent of which development activity physically implements an
operational requirement.

## Requirement migration

Current semantic migrations are:

- former `VPNG-U007` -> `VPNG-D001-R1`, with former `VPNG-U007-R7...` ->
  `VPNG-D001-R1.R1...`;
- former `VPNG-U005` -> `VPNG-M001-R1`, with former `VPNG-U005-R5...` ->
  `VPNG-M001-R1.R1...`;
- former `VPNG-U006` -> `VPNG-M001-R2`, with former `VPNG-U006-R6...` ->
  `VPNG-M001-R2.R1...`.

The migrated descendants preserve their previous closure/decomposition state. The new broad
roots deliberately remain decomposition-incomplete rather than falsely claiming that all
owner-imposed cost principles are already enumerated.

The requirements model now permits project-holder-authorized ID migration only while a stage
is explicitly pre-stable/alpha, with complete migration of current references. Stable-stage
IDs remain immutable.

## Newly promoted operational requirements

The former declarations were promoted rather than left as non-normative wishes:

1. `VPNG-M001-R2.R2` and descendants require the compact human current-state report:
   `Devices` / `Profiles`, four-space hierarchy, one-line Device state, one-line disabled
   Profile state, numbered current effective path order, and normalized availability wording.
   These nodes are `pending_closure`; architecture now defines
   `RuntimeStatusTextRenderer` as a pure Calculator over the authoritative
   `RuntimeStatusSnapshot`.
2. `VPNG-M001-R3` captures practical suitability for resource-constrained gateways and weak
   devices. Its measurable resource envelope remains intentionally decomposition-incomplete;
   `R3.R1` records the preference for lower steady-state CPU/memory/allocation/state cost
   among behaviorally equivalent solutions.

The concrete status delivery mechanism remains replaceable. The text semantics are normative;
a particular CLI/file/API path is not.

## Historical traceability

Historical review/research/experiment records retain their original IDs as baseline facts.
Affected records now carry migration notes with current IDs. One earlier reload pair,
`VPNG-U005-R5.R6.R4` / `VPNG-U005-R5.R6.R4.C1`, had already been deleted before this
migration and therefore retains its complete last normative wording instead of inventing a
successor.

`PROJECT-CONVENTIONS.md` and `design/requirements-model.md` now make this behavior
normative for future migrations.

## Integrity checks

Current branch checks:

- normative nodes: **187**;
- duplicate normative IDs: **0**;
- malformed/missing decomposition labels: **0**;
- decomposition complete: **155**;
- decomposition incomplete: **32**;
- closed: **144**;
- pending closure: **39**;
- active closed requirements missing from structured architecture: **0**;
- old `VPNG-U005/0006/0007` IDs in current requirements/architecture/structured
  architecture/deployment/declarations/experiment registry: **0**.

The 39 pending-closure nodes are the prior 34 architecture candidates plus the five newly
normative human-status presentation nodes. The broad new roots/resource branch intentionally
remain without false architecture closure where their implementation/acceptance scope is not
yet complete.

No active `decomp`, `unreal`, `broken` or `rejected_closure` state is introduced by
this restructure.

## Review findings and dispositions

### F1 — ID stability rule conflicted with the project-holder-approved alpha restructure

**Decision:** accepted.  
**Resolution:** fixed.

The requirement model now distinguishes pre-stable/alpha migration from stable-stage ID
immutability and requires complete current trace migration plus historical annotation.

### F2 — human-readable status had remained a declaration after its promotion gate was met

**Decision:** accepted.  
**Resolution:** fixed at requirements/architecture level; implementation remains open.

The alpha already has an authoritative current snapshot and JSON presentation, so the former
declaration is now a real operational requirement with a dedicated presentation Calculator
boundary.

### F3 — weak-device suitability had no normative owner

**Decision:** accepted.  
**Resolution:** fixed at requirement level.

It now belongs to operational cost, not development cost. Quantitative acceptance thresholds
remain intentionally unresolved until implementation evidence makes them meaningful.

### F4 — historical records would become misleading if old IDs were silently replaced

**Decision:** accepted.  
**Resolution:** fixed.

Historical bodies remain unchanged; migration notes provide current IDs or full deleted
wording.

## Next unblocked development unit

The highest-priority adjacent operational gap is implementation/evidence for
`VPNG-M001-R2.R2`: render and publish the required compact human current-state report from the
existing `RuntimeStatusSnapshot` without creating a second status model.
