# VPN-GATE NG3 — cross-domain structural NetworkPolicy convergence review

**Date:** 2026-11-16  
**Cycle branch:** `ng3-design-cycle-20261116-cross-domain-structural-cont-35m`

## Scope

Review the first complete guarded structural convergence reference spanning:

- payload route tables and terminal guards;
- payload RPDB dispatch;
- Profile/Device/NAT/publication-local nft state;
- managed-netns IPv4 ForwardingGate;
- one current interface-generation observation boundary;
- verified forwarding activation only from exact lower state.

This block starts from the already accepted invariant nft scaffold. Scaffold bootstrap/repair
remains a separate lower prerequisite and is not duplicated inside the structural Executor.

## Verdict

**PASS.**

The cross-domain structural boundary is now executable for the currently materialized
Release-1 owner classes. It preserves the accepted exact-before-release ordering, re-observes
after every physical step, never treats command success as confirmation, and re-closes
forwarding when post-activation verification fails.

No human product decision is required.

## Evidence baseline

### EXP-048

EXP-048 already proved the Linux route/RPDB primitives used here:

- guarded payload table preparation does not affect traffic before RPDB dispatch;
- RPDB dispatch is the activation switch into the prepared table;
- terminal blackhole prevents ambient/main fallback when the ordinary path disappears;
- exact route/rule deletion preserves unrelated state.

Result artifact:

`design/experiments/EXP-048 NG3 structural payload route RPDB mutation/EXP-048-result-20261116.md`.

### Final code workflow

NG3 Python workflow `43949876618`: **SUCCESS**.

Relevant jobs:

- unit: **452 tests OK**;
- `linux-structural-inventory-shape`: SUCCESS;
- `linux-forwarding-barrier`: SUCCESS;
- `linux-payload-forward`: SUCCESS.

Privileged live markers:

```text
STRUCTURAL_CROSS_DOMAIN_NEW_POLICY=PASS
STRUCTURAL_CROSS_DOMAIN_ZERO_PATH_BLACKHOLE=PASS
STRUCTURAL_CROSS_DOMAIN_SAME_NAME_NEW_IFINDEX_FAIL_CLOSED=PASS
NG3 cross-domain structural convergence integration: PASS
```

## Findings

### F1 — route/RPDB mutation Driver must not own observation

A structural route/RPDB Driver that performs its own observe/apply/observe cycle would create
a second route-only authority window independent of nft state.

**Disposition:** `LinuxStructuralRoutingBackend` is mutation-only. It renders only the
EXP-048-backed exact argv forms for:

- terminal guard add/delete;
- ordinary path-route add/delete;
- payload RPDB dispatch add/delete.

Authoritative observation and postcondition verification remain in the outer structural
Executor.

### F2 — route/RPDB and nft must share one interface-generation snapshot

Independent route and nft observations could validate against different
`(ifname, ifindex)` generations.

**Disposition:** `LinuxStructuralPolicyBackend.observe_structural_snapshot()` performs:

```text
link-before
 -> full reserved route JSON
 -> full reserved rule JSON
 -> full nft ruleset JSON
 -> link-after
```

and rejects the snapshot unless the two interface inventories are identical.

Both routing and nft comparisons consume that one current interface tuple.

### F3 — structural phase order is pure and deterministic

The accepted first-release order is encoded by `select_structural_policy_step`:

```text
missing desired terminal guards
 -> stale payload RPDB dispatch
 -> stale payload routes
      ordinary path routes before stale guards
 -> missing desired ordinary path routes
 -> composite nft convergence
 -> missing desired payload RPDB dispatch
 -> exact
```

RPDB addition is therefore the last lower activation mutation before exact verification.

The planner performs no Linux I/O and contains no hidden retry.

### F4 — invariant nft scaffold is a prerequisite, not a conflict

The complete structural reference deliberately does not duplicate the already reviewed nft
scaffold bootstrap/repair unit.

Initial state classification is now explicit:

```text
scaffold absent/incomplete
    -> PRECONDITION_FAILED

reserved nft marker/shape conflict
    -> CONFLICT
```

This lets lifecycle/recovery invoke the correct lower operation instead of treating valid
absence as foreign ownership.

### F5 — command return status is not physical truth

The privileged integration injects an exception **after the final desired RPDB add has
physically succeeded**.

The Executor:

1. records the apply exception;
2. performs a fresh cross-domain observation;
3. sees strict progress/exact state;
4. does not replay the RPDB command;
5. proceeds to verified forwarding activation;
6. returns confirmed state with the apply diagnostic retained.

This directly exercises `VPNG0005-R5.R3` / retry-from-observation semantics rather than only
unit-level fake behavior.

### F6 — mixed structural state never receives forwarding activation

Every non-final structural invocation:

- first establishes and rereads `ForwardingGate=DISABLED`;
- rechecks it before mutation;
- leaves it disabled after a partial step.

The privileged old-policy -> new-policy test confirms real host traffic through ALT before
the transition, then confirms no host traffic passes during every mixed step, and only after
the exact new routing+nft state is verified does traffic resume through VPN.

### F7 — activation itself has a fresh postcondition and safety re-close

Exact state while the barrier is closed is necessary but not sufficient for confirmation.

Activation performs:

```text
exact closed state
 -> recheck gate disabled
 -> set/reread enabled
 -> fresh whole cross-domain observation
 -> reread gate
 -> confirmed only if exact + enabled
```

Unit regression proves that drift detected after activation immediately triggers a
`ForwardingGate=DISABLED` convergence attempt.

Outcomes are distinct:

- `FINAL_VERIFICATION_FAILED` when the safety re-close is confirmed;
- `SAFETY_RECLOSE_FAILED` when the product cannot confirm re-containment.

The Executor never reports desired state confirmed solely because `ip_forward=1` was
written successfully.

### F8 — zero-path Profile remains in policy domain

The live integration transitions the confirmed one-path Profile to zero current paths.

The desired structural state retains:

- the Profile table;
- terminal blackhole default;
- destination RPDB dispatch;

while ordinary path routes and Profile forward accept rules disappear.

After exact verification the ForwardingGate is re-enabled and real host traffic still fails;
it does not fall through to the managed namespace ambient/main route.

This is the physical closure of the already accepted zero-path fail-closed semantics.

### F9 — same-name/new-ifindex replacement fails before mutation

After replacing the VPN interface with the same name and a different ifindex, the test reuses
the stale desired generation.

The shared comparison rejects it with:

```text
CONFLICT: desired forward endpoints are not current
```

before any new path route is materialized.

The ForwardingGate remains disabled and the reserved desired table contains no new
protocol-202 path route.

This is stronger than detecting the mismatch only after a command: stale desired endpoint
identity cannot impersonate the current concrete interface generation.

### F10 — publication-local and payload barrier semantics remain separate

Publication-local INPUT/OUTPUT mutation is included in composite nft exactness, but
`ip_forward=0` is not claimed to protect local traffic.

The publication owner retains its EXP-047 atomic full-diff mutation contract.

Probe-owned local/system rules are still excluded by the explicit implementation deferral:

`design/deferrals/NG3-probe-local-system-materialization.md`.

No generic local exception framework is introduced by this Executor.

## Component-model review

The implementation preserves the accepted component model:

- `structural_policy_plan.py` — pure Calculator behavior;
- `structural_policy_mutation.py` — bounded NetworkPolicyExecutor orchestration;
- `linux_structural_routing.py` — route/RPDB Driver;
- `linux_structural_policy.py` — Linux lower Adapter/Driver composition and authoritative
  physical snapshot boundary;
- existing composite nft Drivers — reused rather than wrapped in a second nft semantic model;
- existing ForwardingGate Driver — reused as the root payload barrier.

No new Manager, Agent, persistent transaction log, rollback journal or route/RPDB owner
process is introduced.

## Simplification review

Not introduced:

- standalone RPDB activator;
- route-only structural transaction;
- nested route and nft observations;
- persistent kernel-object registry;
- replay of stale mutation plans;
- shell-interpolated route commands;
- generic rollback transaction engine;
- delayed stale cleanup after forwarding release;
- global conntrack flush;
- a second nft desired-state model.

One physical mutation per invocation plus fresh replan remains the smallest safe recovery
model.

## Residual boundaries

This block does **not** close:

- nft scaffold creation from an absent namespace; that is the existing separate bootstrap
  prerequisite;
- full daemon/process/lifecycle assembly;
- Netlink/poll scheduling;
- final user-facing NAT/firewall/publication grammar;
- production ICMP probe execution;
- probe-local INPUT/OUTPUT materialization behind the EXP-026 target gate;
- future endpoint-provenance-dependent capabilities;
- Release-2 multi-path bidirectional return-path semantics.

These are separate already-recorded boundaries, not gaps inside this structural Executor.

## Accumulated requirement-state inventory

### `decomp`

All six accumulated links remain **resolved**:

1. `VPNG0001-R1.R2`: `VPNG0005-R5 -> VPNG0005-R5.R6`.
2. `VPNG0001-R1.R3.C1.R1`: `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`.
3. `VPNG0001-R1.R3.C1.R1`: `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`.
4. `VPNG0001-R1.R3.C1.R1`: `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`.
5. `VPNG0001-R1.R3.C2.R1`: `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`.
6. `VPNG0004-R4.R6.R1.R6.R1`: `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`.

Pending `decomp`: **none**.

### `unreal`

**none**

### `[rejected_closure]`

**none**

## Human decisions required

**none**

## Conclusion

**PASS.**

The currently materialized Release-1 payload network-policy domains now have one guarded
cross-domain structural convergence reference. Route/RPDB, nft and forwarding activation are
no longer independent physical slices: they are reconciled through one current-generation
snapshot and exact-before-release Executor boundary.
