# NG2 autonomous review — free-slot route-priority transactions

**Date:** 2026-11-14  
**Branch:** `code-cycle-20261114-empty-slot-routing-v2`  
**Scope:** availability-driven route priority, implicit free metric, Linux fast-path
materialization, and the adjacent runtime contracts.

## Scope reviewed

Reviewed:

- `availability-routing-model.md`;
- `PayloadProfileRequest -> RoutingDomainSpec -> LinuxRoutingDesired` projection;
- `linux_route_priority.py`;
- `linux_network_route_priority_only_change()`;
- `LinuxNetworkExecutor.materialize_route_priority()`;
- PayloadRules state interaction;
- EXP-027 kernel evidence;
- Linux Adapter privileged integration A3/A4;
- runtime transaction-serialization wording.

Review questions:

- unused/redundant artifacts;
- unjustified complexity;
- contradiction with EXP-027/kernel evidence;
- hidden loss of eligible routes during permutation;
- ambiguity between all-live, mixed and all-non-confirmed layouts;
- leakage of technical gap state into user configuration;
- transaction interleaving.

## Findings and dispositions

### F1 — fixed-slot `ip route replace` could temporarily remove an eligible path

**Classification:** accepted and fixed.

The earlier fast path could replace a metric occupant before that path had another route
copy. That violated the stronger invariant agreed during review: availability changes
priority but must not intentionally remove any eligible path while reordering.

Production transition now uses exactly one primitive:

```text
add moving path at current free metric
delete only its old copy
```

Between the two commands the moving path is the only duplicate. After the delete the old
metric becomes the next free position.

EXP-027 now proves that primitive for ordinary prefix and default routes.

### F2 — modelling EMPTY as a configured/persistent object was unnecessary

**Classification:** accepted and fixed.

The gap is not a path, binding, route, configuration item or durable allocator object.

The runtime carries only derived `confirmed_live_prefix_length`. Linux projection derives
the unused metric from that boundary:

- mixed state: gap immediately before the first non-confirmed path;
- all live: no steady-state gap; the next unused metric is scratch for a transition;
- all non-confirmed: metric 10 is unused and routes begin at metric 20.

No `RouteSlotGap` model exists.

### F3 — `ordered_paths` alone cannot distinguish availability state from admin reorder

**Classification:** accepted and fixed.

The same path order can mean either an administrative order with all paths live or an
availability state with a non-confirmed tail. Lower-domain materialization therefore needs
the live/dead boundary in addition to effective order.

`confirmed_live_prefix_length` was added only to transient runtime routing intent. It is
not part of normalized user configuration.

Concrete-generation projection adjusts the prefix length when an interface generation is
absent.

### F4 — semantic-only `None -> N` live-prefix transition caused needless structural rebuild

**Classification:** accepted and fixed.

Availability can become authoritative while all paths are live without changing any Linux
route. Rebuilding nft/RPDB and toggling forwarding in that case is unjustified.

LinuxNetworkRulesAdapter now performs fresh verification when old and new compiled Linux
desired states are identical. On successful verification it commits the new semantic
intent without mutation. Drift still falls back to structural repair.

### F5 — route-slot projection logic was duplicated

**Classification:** accepted and fixed.

The compiler originally reimplemented the same prefix/gap index arithmetic represented by
`route_slots()`.

`compile_linux_routing_desired()` now uses the canonical helper directly.

### F6 — planner correctness needed coverage beyond hand-picked bubble examples

**Classification:** accepted and fixed.

Added exhaustive rootless coverage for all four-path permutations and every possible free
slot position, current -> desired.

For every elementary move the test proves:

- target slot was free;
- source contained the moving path;
- after add the complete path set remains and exactly one route is extra;
- after delete the complete path set remains and exactly one free position exists;
- the plan converges to the requested target.

### F7 — live-prefix divergence must not be confused with exposure safety

**Classification:** accepted and fixed.

A different live-prefix changes routing preference, not firewall/NAT permission.

PayloadRules state regression now requires such divergence to be `DIVERGED / SAFE`, with
service left UNKNOWN until convergence.

### F8 — superseding availability input must not interleave an active route transaction

**Classification:** accepted and deferred behind the **runtime availability-wiring gate**.

Required invariant:

```text
active current -> target plan is immutable
new same-Profile availability state updates pending/latest desired only
next plan starts only after current final verification
```

The current executable Adapter/Executor call is synchronous, so a single invocation cannot
be modified mid-plan. The Event Delivery / availability -> payload runtime queue is not yet
implemented, so there is currently no executable asynchronous source to coalesce.

Re-entry condition: the first executable RuntimeStateManager/Event Delivery wiring that
turns availability evidence into repeated PayloadTrafficStateRequest updates. That review
unit must implement per-Profile/routing-domain serialization before it is accepted.

A speculative lock/scheduler was not added to the lower Linux Driver because that would
invent concurrency policy below the runtime boundary and unnecessarily serialize unrelated
domains.

## Evidence

Latest executable test-bearing head reviewed in this unit passed:

- NG2 unit suite: **248 tests PASS**;
- privileged NG2 Linux integration: PASS;
- EXP-027: PASS for ordinary prefix and default;
- Linux Adapter A3: pure priority permutation stays route-only;
- Linux Adapter A4: availability demotion/recovery moves the implicit live/dead boundary
  without forwarding or nft mutation;
- Linux instance and nft syntax gates: PASS;
- NG1 Python validation: PASS.

EXP-027 additionally covers:

```text
ABGD.VEJ -> ABVGD.EJ
ABVGD.EJ -> ABGD.VEJ
ABGDEJ.V -> ABVGDEJ
ABVGDEJ -> ABGDEJ.V
```

## Final verdict

**PASS for the route-priority materialization review unit.**

The lower route algorithm is coherent, kernel-proven and does not require a persistent gap,
staging table, ECMP semantics or per-flow pinning.

The only intentionally unfinished item is the runtime serialization/coalescing mechanism in
F8. It does not block this lower-domain slice because the executable asynchronous runtime
path does not yet exist; it is a mandatory gate for the next availability-runtime wiring
unit.
