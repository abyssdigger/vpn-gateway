# NG3 R8.R6 runtime generation-ordering review — 2026-11-25

**Review unit:** D.002 ownership-generation currentness in A.007 availability evidence  
**Reviewed source head:** `42a0a27cfcf0a518841fa930b481c0dd2a5da08d`  
**Requirement:** `VPNG-U001-R1.R3.R8.R6`  
**Architecture:** A.001, A.004, A.007, C.001, D.002, D.003  
**Evidence:** `EV-00280`

## Verdict

**PASS — R8.R6 is materially closed in the current executable reference runtime.**

One normal managed-WireGuard reconciliation now orders the relevant responsibilities as:

`C.001 full probe-plane preparation -> D.002 reconcile/generation -> A.007 context synchronization + fresh observation -> A.004 priority convergence`.

An A.007 result can no longer remain current merely because `LogicalPathId`, `wg0` and
ifindex are unchanged after a D.002 ownership-context change.

## Findings and dispositions

### F1 — old monolithic availability cycle could apply A.007 evidence before D.002 transfer

**Decision:** accepted  
**Resolution:** fixed

`linux_availability_cycle.py` now exposes a lower C.001 preparation phase and a subsequent
A.007/A.004 phase. The alpha runtime inserts retained D.002 reconciliation between them on
startup, normal periodic reconciliation and the normal-state check used by Protective-mode
release.

The legacy monolithic wrapper remains only for callers without a D.002 ownership dependency.

### F2 — absent dependency and applicable-but-unconfirmed dependency require different states

**Decision:** accepted  
**Resolution:** fixed

`ProbeOwnershipDependency` is typed as `not_applicable`, `confirmed(generation)` or
`unconfirmed`. A non-D.002 subject proceeds normally. An applicable managed-WireGuard subject
whose D.002 realization is not current synchronizes to an unconfirmed context but performs no
remote availability attempt and accepts no remote evidence. Independent subjects in the same
tick remain observable.

### F3 — confirmed no-owner is a valid current generation

**Decision:** accepted  
**Resolution:** fixed

A confirmed D.002 no-owner realization has a non-null Device-wide generation and therefore
produces `confirmed(generation)`, not `unconfirmed`. Later acquisition or other ownership
change changes that generation and invalidates the old A.007 context.

### F4 — generation change behind the same path/interface must invalidate evidence, not routing history

**Decision:** accepted  
**Resolution:** fixed

The focused AvailabilityManager acceptance test creates negative A.007 evidence under D.002
generation A, then synchronizes the same `LogicalPathId` and same `wg0@ifindex` under
generation B. The availability-problem confirmation is immediately discarded and stale
generation-A evidence is rejected.

The test also preserves ordinary-path routing stickiness. This is intentional: A.004 routing
history is separate Manager state and is not itself stale A.007 evidence.

Existing `EV-00190` supplies the complementary kernel fact that exact split group ownership
can change while the common `wg0` ifindex remains unchanged.

### F5 — architecture status edit accidentally changed the wrong broad R8 edge

**Decision:** accepted  
**Resolution:** fixed

An overly broad mechanical edit in the first architecture pass changed A.004 R8
`partial -> full` while leaving D.002 `partial`. Review caught the error before acceptance.
Commit `e192f99cbb43ec4c73590b4287caff62551caebd` restored A.004 to its honest
component-local `partial` contribution and changed only D.002 broad R8 to `full`.

### F6 — A.004 retained stale wording that assigned it direct D.002-generation ownership

**Decision:** accepted  
**Resolution:** fixed

A.004 does not own D.002 currentness. The generation is part of A.007 observation identity;
A.004 consumes the already recalculated effective-order projection. Commit
`42a0a27cfcf0a518841fa930b481c0dd2a5da08d` corrected the stale gap text while retaining
the honest broad R8 component-local `partial` edge.

## Evidence

Implementation lineage:

- `70bdccb6eb19afe51144b94eac24b23659e34e3a` — typed A.007 ownership dependency;
- `912362d8636c77eac78ec3a66c9925e6fa53c02c` — C.001/D.002/A.007/A.004 runtime ordering;
- `7e544324805d87cb30f85b3f7131fa4965d4f89e` — same-endpoint generation invalidation acceptance;
- `d280c987c4a39fc8ffaacbc3faf1827c2b26d730` — architecture closure pass;
- `e192f99cbb43ec4c73590b4287caff62551caebd` and
  `42a0a27cfcf0a518841fa930b481c0dd2a5da08d` — review corrections.

Exact reviewed-head GitHub Actions run `45603272998`:

- unit `139167589571` — PASS;
- `linux-probe-runtime` `139167589540` — PASS;
- `linux-wireguard-peer-ownership` `139167589253` — PASS;
- `linux-wireguard-multipeer` `139167589690` — PASS;
- `linux-alpha-smoke` `139167589811` — PASS;
- frozen `release-0-1-0-deployment-qa` `139167589538` — PASS;
- actual-main lineage `45603273406` — PASS.

No new privileged kernel experiment is required for this unit: `EV-00190` already proves the
unchanged-interface ownership-transfer condition; the new executable evidence proves the
previously missing generation-to-A.007 invalidation contract.

## Closure consequence

A.007 now directly materializes `VPNG-U001-R1.R3.R8.R6` as `full`. D.002's generalized
R8 contribution is `full`. C.001 and A.004 retain broad R8 `partial` edges only because each
owns a bounded component-local contribution rather than the complete cross-component R8
behavior; their gap text no longer describes an outstanding R8.R6 implementation defect.
