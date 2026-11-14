# NG2 — availability de-complexification cycle checkpoint

**Date:** 2026-11-14  
**Branch:** `code-cycle-20261114-availability-decomplexification-40m`  
**CYCLE_INTERVAL:** 40 minutes  
**CYCLE_START_COMMIT:** `6cee7ccd3785be008399bf8162714c77de158cfe`  
**T0:** `2026-11-14T17:44:16Z`

## Scope completed

The cycle replaced the attempt-oriented availability candidate with a smaller model whose
only control purpose is routing preference among already eligible paths.

The clean normative baseline is:

```text
design/NG2/availability-routing-model.md
```

Its production semantics are:

```text
eligibility is structural/admin
probe good news is positive evidence
missing good news accumulates by observation interval
confirmed-live paths bubble upward in configured priority
not-confirmed paths remain as fallback
probing never removes the last eligible payload path
```

Configured disable preserves logical probe configuration. Physical ProbeRules exist only
while at least one enabled logical consumer needs the corresponding physical plane.

## Rudiments removed

Removed from active production architecture/code:

- `AvailabilityProbePolicy` with retry interval, per-attempt timeout and recovery threshold;
- serial `run_due()` scheduler and attempt-streak state;
- per-attempt verdict policy tests;
- synchronous `ProbeDriver` dependency from `AvailabilityProbeManager`;
- Manager `attempt_once()/evaluate_once()`;
- policy-less/manual logical probe mode;
- availability-driven binding removal;
- dedicated `ProbeRulesState` / `ProbeRulesStateCalculator`;
- redundant probe `Usability` axis;
- route-priority leakage into filter/NAT ordering;
- full structural rebuild for pure path-order permutations;
- shadow/UNAVAILABLE route tier as current NG2 availability machinery.

The standalone Linux single-shot ICMP worker remains intentionally as diagnostic/evidence
machinery only. It is decoupled from logical probe requests and accepts concrete
`InterfaceIdentity + IPv4 target + technical timeout`.

## Shared state simplification

Generic NetworkRules observation now exposes one shared convergence base:

```text
NetworkRulesConvergenceState
    StateKnowledge
    RulesConvergence
```

with `assess_network_rules_convergence()`.

Payload alone retains its domain-specific `Safety` and `Service` axes.

## Route-priority evidence and implementation

EXP-027 completed PASS in privileged Linux CI.

For both an ordinary prefix and `default`, Linux accepted the bubble sequence:

```text
A10 B20 C30 D40
B10 B20 C30 D40
B10 C20 C30 D40
B10 C20 A30 D40
```

A route replacement at one metric did not remove the same interface at another metric, and
the terminal blackhole remained present.

The Linux NetworkRules backend now has a narrow verified route-priority fast path:

1. fresh verification of committed compiled state;
2. strict proof that only the same unicast path membership is permuted across the same
   metric slots;
3. top-down `ip route replace`;
4. fresh verification of final desired state;
5. automatic fallback to the existing structural fail-closed rebuild on any broader change
   or fast-path failure.

Live Adapter integration additionally proves that the fast path does not close forwarding
and does not mutate nft policy.

## Final executable evidence

Latest executable/test-bearing head:

```text
69557f2e227e3374294d9f48917ccb9f4818c699
```

GitHub CI:

- NG2 unit: PASS — 233 tests;
- NG2 privileged Linux integration: PASS;
- EXP-026 selective probe-class conntrack cleanup: PASS;
- EXP-027 route-priority bubble: PASS;
- nft ICMP selector syntax: PASS;
- Linux instance integration: PASS;
- Linux Adapter integration: PASS, including route-only `PASS A3`;
- LOCAL_PROCESS integration: PASS;
- payload dataplane integration: PASS;
- NG1 Python validation: PASS.

Intermediate failures retained as evidence:

- EXP-027 attempt 1 failed before the routing hypothesis because the initial CI dummy-link
  fixture was unavailable; the veth-based second attempt reached the hypothesis and passed;
- requiring timing policy initially exposed missed test/integration callers; those callers
  were updated without restoring policy-less mode;
- disabled-plane lifecycle initially exposed a stale publication expectation; kernel/Adapter
  integration was already green and the current-state projection was corrected/tested.

## Autonomous review

Full de-complexification review:

```text
design/reviews/NG2-2026-11-14-availability-decomplexification-review.md
```

Verdict: PASS for this scope.

The review found no remaining active dependency on per-attempt availability semantics,
availability-driven binding removal, shadow fallback or a dedicated probe-rules state
model.

## Explicit scope boundary

Route-priority changes select the preferred FIB path for routing lookups. EXP-027 does not
claim per-flow pinning across failover/failback. If preserving an already established flow
across priority changes later becomes a product requirement, it needs a separate
conntrack/mark evidence gate rather than hidden complexity in the bubble algorithm.

## Unfinished / next review unit

No blocker remains in the de-complexification unit.

The next coherent unit is production good-news/window execution integration:

- generation-bound good-news delivery;
- interval-boundary delivery;
- enabled lifecycle;
- local execution diagnostics;
- wiring `AvailabilityWindowState` into runtime priority calculation.

It must not reintroduce semantic attempt ids or reply-to-send correlation without a new
concrete requirement.
