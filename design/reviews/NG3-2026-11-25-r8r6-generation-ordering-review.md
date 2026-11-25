# NG3 R8.R6 A.007 / D.002 generation-ordering review — 2026-11-25

**Review unit:** implementation ordering required to invalidate A.007 evidence after D.002 ownership change  
**Requirement:** `VPNG-U001-R1.R3.R8.R6`  
**Architecture:** A.001, A.004, A.007, C.001, D.002  
**Status:** accepted design clarification; no materialization-status change

## Verdict

**PASS — R8.R6 cannot be implemented safely by adding a D.002 token to
`ProbeObservationContext` while keeping the current alpha ordering.**

The current Linux availability cycle converges probe routing, accepts A.007 evidence and may
change effective route priority before alpha invokes D.002. If D.002 then confirms a different
group owner behind the same `LogicalPathId` / `wg0`, the A.007 verdict just used in that
priority decision has already become stale. Waiting for the next timer tick is not sufficient
for the requirement that old evidence lose force after the ownership-context change.

## Accepted implementation ordering

One normal reconciliation for an A.007 subject depending on managed-WireGuard group ownership
must have the following semantic order:

1. converge and fresh-confirm the complete C.001 probe-routing lower plane;
2. run D.002 reconciliation, including D.003 exact ownership confirmation and any required
   group endpoint check;
3. obtain the applicable confirmed Device-wide D.002 generation;
4. synchronize A.007 context identity with that generation;
5. fresh-observe A.007 scoped readiness and perform the A.007 attempt;
6. apply only evidence belonging to that exact context;
7. converge A.004 effective route priority and publish current status.

This allows D.002 peer/group probes to stay independent of A.007 readiness while preventing a
post-transfer state from relying on pre-transfer Profile evidence.

## Findings

### F1 — context equality is already the right invalidation mechanism

`AvailabilityManager.synchronize()` retains confirmation only when
`ProbeObservationContext` is exactly equal. Extending that context with the applicable D.002
generation therefore naturally resets degradation/recovery progress when ownership generation
changes. `AvailabilityProbeAgent.accept_result()` already rejects an attempted context that is
no longer current.

### F2 — dependency absence and dependency uncertainty are distinct

A non-managed or otherwise non-D.002 path has no ownership-generation dependency. A managed
WireGuard Profile/path whose applicable D.002 realization is currently unconfirmed does have a
dependency, but no current generation token. These states must not both be encoded as an
undifferentiated `None`: the former permits ordinary A.007 observation, while the latter must
not accept remote evidence as current.

### F3 — confirmed no-owner still has a generation

D.002's exact no-owner state after D.003 confirmation has a normal non-null generation. It is
therefore a valid ownership context, distinct from D.002 local/unconfirmed problem. A later
owner acquisition changes the generation and invalidates A.007 evidence from the no-owner
context as required.

### F4 — merely re-running the old monolithic cycle after D.002 is weaker than the accepted order

A second A.007 cycle could eventually repair the final state, but the first cycle may already
have changed route priority using evidence that becomes stale when D.002 transfers ownership.
The implementation should split probe-plane preparation from A.007 observation/priority rather
than rely on a temporary stale window.

### F5 — Availability routing stickiness remains a separate Manager policy

R8.R6 invalidates evidence/confirmation tied to the old ownership context. Existing
Profile-level ordinary/reserve stickiness remains Manager-owned state and is not itself
reclassified as evidence by this clarification. Context resynchronization must nevertheless
recompute the current projection after confirmation reset before any final priority
postcondition is accepted.

## Implementation frontier

Refactor `linux_availability_cycle.py` into a lower probe-plane preparation phase and an A.007
observation/priority phase; extend A.007 context with a typed ownership dependency state; have
alpha insert D.002 reconciliation between those phases; and add focused tests proving an owner
change behind unchanged path/interface invalidates old evidence before the final priority
postcondition.
