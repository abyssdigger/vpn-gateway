# RESEARCH OVERLAY

**Scope:** research semantics for an active continuous execution loop.

This document is a work-mode overlay on `EXECUTION-LOOP.md`. It owns research frontier,
evidence classification, source/evidence discipline and research-specific continuation/
escalation semantics.

It does not grant repository/GitHub authorization, define product requirements or architecture,
or replace project experiment-artifact conventions.

## 1. Entering research

An explicit projectholder request to start/resume a research loop activates the generic loop and
this overlay.

Inside an already active loop, the current work may enter the research overlay when a bounded
unknown must be resolved to continue within the accepted scope. This does not start a new clock
or widen authority.

A normal one-shot request to research/check something does not by itself activate continuous
execution.

Before research continues:

1. establish the generic loop/control state;
2. read this document if not already read unchanged;
3. identify the concrete research question and nearest unknown;
4. establish the evidence/source boundary and any freshness requirement;
5. establish any external communication frontier;
6. preserve the existing authorization boundary.

## 2. Evidence classification

For each material claim classify its evidence explicitly when the distinction matters:

- **DOCUMENTED** — supported by current authoritative documentation;
- **OBSERVED** — directly observed in the relevant environment/execution;
- **INFERRED** — follows plausibly from evidence but is not directly established end-to-end;
- **UNKNOWN** — current evidence is insufficient;
- **EXPERIMENT NEEDED** — documentation/inspection cannot establish the required behavior and a
  bounded empirical check is justified.

Do not upgrade one class into another by wording. In particular:

- availability/configuration is not execution evidence;
- a component event is not end-to-end composition evidence;
- one account/environment does not establish another;
- a successful steady-state path does not establish restart/recovery semantics;
- possession of a tool/credential does not establish permission to use it.

## 3. RESEARCH_NEXT

`RESEARCH_NEXT` is the research specialization of generic `EXEC_NEXT=WORK`.

For each bounded research step:

1. identify the nearest unknown that can change the decision/frontier;
2. choose the cheapest sufficient source/check;
3. distinguish facts from assumptions and non-implications;
4. update the research frontier;
5. either perform the next bounded research step, propose the minimum useful experiment, enter
   `WAIT`, or reach a real holder/setup gate;
6. return to generic `EXEC_NEXT`.

Do not jump from an unresolved unknown directly to architecture merely because a plausible
composition can be imagined.

## 4. Source and freshness discipline

Prefer the most authoritative source capable of proving the claim.

For platform/API/current-product behavior, use current official documentation and current
observable product/tool surfaces where available. Mark account/environment-specific entitlement
or behavior UNKNOWN unless actually observed.

When documentation and observation differ, preserve both facts and investigate the boundary;
do not silently choose the more convenient one.

A failed tool call proves only what was actually attempted and observed. A pre-invocation error,
for example, does not automatically prove absence of the product capability behind that tool.

## 5. Experiments and emulation boundary

Use the cheapest sufficient evidence before constructing an experiment.

A research experiment must:

- state the exact property being tested;
- state prerequisites and authorization separately;
- define PASS / FAIL / INCONCLUSIVE;
- record what the result does **not** prove;
- minimize state mutation and external side effects;
- distinguish experimental stimulus from the target autonomous behavior.

Experiments may establish facts; they do not create product requirements, architecture decisions
or new execution authority.

Persistent experiment dossier/history rules remain owned by `PROJECT-CONVENTIONS.md`.

No separate emulation overlay is defined yet. If a future case requires rules for simulated
actors/environments that are materially different from research/experiment semantics, add that
overlay through the normal process-correction gate rather than anticipating it here.

## 6. Human/setup gates

Do not escalate to the projectholder merely because research has become inconvenient.

A real holder/setup gate exists when:

- the next discriminating observation requires a UI/account action unavailable to the active
  execution;
- a new credential/resource/connection/approval would be required;
- a product/project decision is genuinely unresolved by accepted constraints;
- execution authority would need to expand.

Keep these distinct:

- holder project decision inside existing authority;
- setup/entitlement action;
- execution-authority expansion.

A decision or setup action does not automatically imply the others.

When only one minimal holder action is required, request exactly that action and keep independent
research in `WAIT`/continue other unblocked work as appropriate.

## 7. Research transport and frontier

When an external Issue/message/event lane carries research coordination:

- use stable message/task IDs when available;
- maintain the last processed semantic frontier;
- separate task/result transport from holder decision transport and execution-authority changes;
- account for duplicate, late and missed delivery where the transport can exhibit them;
- do not assume exactly-once logical work unless proven.

The interactive overlay owns live waiting mechanics when ID is active.

## 8. Research stop/continuation semantics

Completion of one capability map, document review, experiment proposal or peer response is not
by itself a stop basis.

If useful research remains, return to `RESEARCH_NEXT` / generic `EXEC_NEXT`.

If research is blocked on a real external/holder/setup dependency:

- use `WAIT` when an active bounded interaction lane can observe the dependency;
- otherwise the generic external-blocker/human-decision stop basis may apply.

Before finalization, apply the generic `PRE_FINAL_GATE` and any active ID final-lane check.

## 9. Research handoff additions

The common handoff is owned by `EXECUTION-LOOP.md`.

When research is active, additionally include:

- current research question/frontier;
- material claims by evidence class;
- unresolved UNKNOWN / EXPERIMENT NEEDED items;
- experiments proposed/executed and their verdict boundaries;
- exact holder/setup dependency, if any;
- next cheapest discriminating step.

Do not present an inference or proposed experiment as an accepted architecture/product decision.
