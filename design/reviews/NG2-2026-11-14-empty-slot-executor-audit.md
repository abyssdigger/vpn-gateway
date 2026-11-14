# NG2 — EMPTY-slot / per-Profile Executor post-checkpoint audit

**Date:** 2026-11-14  
**Branch:** `code-cycle-20261114-empty-slot-executor-audit`  
**Audited baseline:** `code-cycle-20261114-live-boundary-empty-slot` @ `d459024b229449402fa9a6871659bf194a7e92a2`  
**Latest executable reviewed:** `d7efb889bab2760ff721c1274db62a2acc089afd`

## Verdict

**PASS after correction.**

The persistent-EMPTY route algorithm itself was sound. The post-checkpoint audit found one
architectural mismatch in transaction ownership and corrected it: the previous global
`PayloadTrafficManager` lock prevented interleaving, but the agreed caller-visible
transaction boundary is **one route-order Executor per Profile**.

## F1 — steady route-slot invariant is correct

For an availability-managed Profile with `N` eligible paths:

```text
N eligible routes
N + 1 ordinary metric slots
exactly one EMPTY slot
EMPTY immediately after confirmed-live prefix
terminal blackhole remains separate at metric 65536
```

`priority_prefix_length` carries the semantic live/non-confirmed boundary. Linux
`route_slots()` projects that boundary into the one unused metric.

Interface fail-closed projection also recomputes the prefix length from surviving live
members instead of retaining a stale numeric boundary.

## F2 — one elementary move never removes an eligible route

The production primitive is only:

```text
add X at current EMPTY metric
delete old X route
```

After add:

- every eligible path is still present;
- there are `N+1` routes;
- exactly one path has two copies.

After delete:

- every eligible path has exactly one route;
- the old metric becomes the new EMPTY.

No live or non-confirmed eligible path is used as disposable scratch state.

## F3 — planner is generic, not a collection of recovery/death cases

`plan_route_slot_moves()` treats the problem as a permutation of:

```text
paths + EMPTY
```

If desired wants a path in the current EMPTY, that path moves there. If desired also wants
EMPTY there while another permutation cycle remains, the planner deterministically opens
that cycle by moving one mismatched occupant through EMPTY.

The same algorithm therefore covers death, recovery, failback, dead-tail movement and
ordinary administrative priority permutations.

The unit suite now exhaustively checks **every pair of layouts for 1..4 paths**. Every
intermediate add/delete phase is checked for full path-set preservation and exactly one
duplicate during the add phase.

## F4 — original single-flight implementation had the wrong boundary

The checkpoint implementation used one Manager-wide lock around `handle_request()`,
`audit()` and `shutdown()`.

That was safe against interleaving but architecturally wrong for the agreed model. It
made the complete payload domain the transaction owner.

**Corrected.**

Pure route-priority diffs now use one lazily retained:

```text
ProfileRouteOrderExecutor(profile_name)
```

per Profile.

The Executor has one lower transaction operation bound at construction. Its public
contract is:

```text
execute(target_domain) -> completed ActionResult
```

A second `execute()` for the same Profile waits until the first call returns. The lower
operation returns only after the NetworkRules Adapter has completed its
apply/materialize/fresh-verify/commit attempt.

Different Profiles have distinct Executor gates.

## F5 — Profile transaction and Linux transaction are deliberately different

The caller-visible transaction is:

```text
ProfileRouteOrderExecutor
    -> NetworkRulesAdapter.apply
        -> LinuxNetworkExecutor
            -> add/delete kernel operations
            -> fresh verification
        -> Adapter commit
    -> Executor return
```

Linux route mutation is **not** claimed to be atomic. The transactional guarantee is the
Direct completion boundary seen by the Profile Executor's caller.

The shared aggregate NetworkRules owner still needs a lower implementation lock so two
Profile operations cannot lose each other's aggregate committed state. This lock is
separate from and does not replace the per-Profile Executor model.

## F6 — later Profile transactions use completed state, not failed desired state

A second issue was found while checking multi-Profile requests.

If Profile A failed and Profile B was processed next, B must not inherit A's uncommitted
desired order merely because both targets came from one full payload snapshot.

**Corrected.** Before each Profile apply, the Manager obtains fresh authoritative
`NetworkRulesState` from the Adapter and merges only that Profile's target into this
completed observed/committed base.

Therefore:

- a failed A target is not smuggled into B's transaction;
- B may converge independently against the completed A state;
- the full payload snapshot remains the Manager's current desired intent;
- normal audit/reconcile can later retry any still-divergent Profile.

A dedicated regression covers this failure path.

## F7 — pure priority classification remains narrow

A request is eligible for Profile route-order execution only when unchanged:

- Profile set;
- path membership;
- destinations;
- terminal disposition;
- dispatch;
- filter/traffic permissions;
- flow-initiation permissions;
- NAT policy.

Only `ordered_paths` and/or `priority_prefix_length` may differ.

Membership or other structural change remains on the aggregate structural path and cannot
masquerade as an EMPTY-slot priority transaction.

## Documentation audit

Normative descriptions were aligned in:

- `design/NG2/availability-routing-model.md`;
- `design/NG2/payload-traffic-manager.md`;
- `design/NG2/runtime-event-model.md`;
- `design/NG2/network-rules-adapter.md`;
- `design/NG2/code/python/rou/README.md`;
- `CHANGELOG.md`.

The old live-boundary review and checkpoint are retained as historical evidence, but now
carry an explicit post-checkpoint correction where their global single-flight wording was
wrong.

## Evidence

Executable gate for `d7efb889bab2760ff721c1274db62a2acc089afd`:

- **255 NG2 unit tests: PASS**;
- privileged NG2 Linux integration: PASS;
- EXP-027 ordinary prefix: PASS P1-P4;
- EXP-027 default: PASS D1-D4;
- Linux Adapter A3 route-only fast path: PASS without nft or forwarding mutation;
- LOCAL_PROCESS integration: PASS;
- dataplane integration: PASS;
- NG1 Python validation: PASS.

## Remaining scope

Production good-news/window delivery and RuntimeStateManager wiring still remain a separate
unit. They must provide Profile target order/live-prefix to the existing Executor boundary
without reintroducing per-attempt reply correlation.

No remaining blocker was found in the EMPTY-slot route-transition / Profile transaction
slice.
