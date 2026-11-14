## 2026-11-14 — NG2 availability de-complexification and route-priority bubble

Superseded the same-day per-attempt cadence/hysteresis candidate with a smaller routing
model derived from the actual product requirement:

- active probing no longer controls binding membership or removes payload paths;
- one valid reply is immediate good news; negative evidence is only the integral count of
  observation intervals without good news, including intervals affected by local probe
  execution errors;
- per-attempt correlation, retry cadence, recovery threshold and timeout-as-verdict-policy
  were removed from production availability semantics;
- AvailabilityProbeManager no longer depends on a synchronous ProbeDriver and no longer
  exposes attempt_once()/evaluate_once(); it owns only the probe rules/readiness-generation
  boundary until production good-news delivery is wired;
- every normalized logical probe now carries required AvailabilityWindowPolicy
  (interval_seconds + failure_intervals), while configured enable/disable is a separate
  logical request property; physical ProbeRules exist only for enabled consumers, so
  disabling the last consumer closes the plane while shared planes remain intact;
- calculate_effective_path_order() implements stable bubble promotion: confirmed-live
  paths rise in configured priority while the remaining current order is preserved; startup
  and structural/admin priority changes explicitly rebase that order;
- availability was removed from BindingCalculator semantics and now affects only
  PayloadTrafficIntentCalculator -> ordered_paths;
- payload filter/NAT generation was canonicalized independently of route priority, so a
  pure path permutation no longer masquerades as nft/NAT policy change;
- the redundant ProbeRulesState/ProbeRulesStateCalculator layer was removed; generic
  knowledge/convergence is now shared as NetworkRulesConvergenceState, while payload alone
  retains its domain-specific Safety/Service axes;
- EXP-027 PASS proved fixed-metric route-slot replacement for both an ordinary prefix and
  default: temporary duplicate paths are accepted and terminal blackhole remains;
- Linux NetworkRules gained a verified route-priority fast path: fresh pre-check, top-down
  ip route replace slot updates, fresh post-check, with automatic fallback to the existing
  structural fail-closed rebuild for any broader change or failure;
- the standalone Linux single-shot ICMP worker is retained only as diagnostic/evidence
  machinery and now accepts only concrete path + target + technical timeout, not a logical
  AvailabilityProbeRequest;
- historical cadence/verdict checkpoint documents remain preserved as superseded design
  evidence rather than being rewritten.

The clean normative model is design/NG2/availability-routing-model.md. The autonomous
de-complexification review is design/reviews/NG2-2026-11-14-availability-decomplexification-review.md.
The older same-day cadence and one-attempt entries below are retained only as chronology and
no longer define current NG2 production availability semantics.
---

## 2026-11-14 — NG2 per-probe cadence and hysteresis candidate

Extended AvailabilityProbeManager above the agreed one-attempt verdict boundary:

- added normalized per-logical-probe `AvailabilityProbePolicy` with explicit normal/retry
  cadence, timeout and failure/recovery thresholds;
- threshold defaults remain 1/1, preserving the one-attempt baseline without inventing
  wall-clock defaults;
- `run_due(monotonic_now)` provides deterministic serial cadence without threads or sleeps;
- pending contrary evidence retains the current authoritative verdict until its threshold is
  reached;
- local ERROR and invalid attempts use retry cadence but never count as remote failure;
- timing state is per `probe_id`, even when logical probes share one physical probe plane;
- policy remains outside `ProbeRulesCalculator` and physical `NetworkRulesSpec`;
- audit corrected an over-broad coupling: logical-only/policy-only changes no longer bump the
  owner-wide rules-readiness epoch or invalidate unrelated probes;
- physical rules changes and loss of READY still invalidate the complete owner-wide evidence
  epoch;
- no scheduler class, async framework, lock model or second reconciler was introduced.

Executable SHA `43c0d8b34cfe1f479d6a067bae272dc5cffd0eb6` passed 252 NG2 unit
tests, privileged NG2 Linux integration and NG1 Python validation.

The cycle checkpoint records the remaining semantic choices before outer runtime/tick
assembly.

---

## 2026-11-14 — NG2 minimal availability verdict policy candidate

Added the first policy-bearing layer above the validated raw active-probe attempt boundary:

- `attempt_once()` remains policy-free and returns only generation-valid raw observations;
- new `evaluate_once()` maps valid REPLY -> REACHABLE, NO_REPLY -> UNREACHABLE and
  local ERROR -> UNKNOWN;
- REACHABLE/UNREACHABLE retain the current `ProbeObservationGeneration`; UNKNOWN never
  claims an authoritative generation;
- READY audits preserve an already authoritative verdict from the same readiness epoch
  instead of creating a transient UNKNOWN before each attempt;
- request/rules generation changes still invalidate old evidence and return the affected
  probe to UNKNOWN until fresh evidence exists;
- repeated identical verdict publications are idempotent;
- no scheduler, retry counter, hysteresis object or new policy abstraction was introduced.

Executable SHA `7f108fec33d903eb4b599b84239abe8e78b02df2` passed NG2 Python and
NG1 Python validation. The candidate remains on its cycle branch pending maintainer
agreement on one-attempt NO_REPLY semantics and ERROR handling.

---

## 2026-11-14 — NG2 ProbeRules semantic boundary and EXP-024

Extended the common NetworkRules semantic layer far enough to represent the proven active
probe plane without introducing a second Linux policy reconciler:

- ProbeRules boundary review confirmed that a separate physical Adapter would conflict with
  the structural NetworkRulesAdapter's exclusive nft ownership;
- EXP-024 tested selective shared-namespace probe-process isolation while unrelated local
  traffic remained on ordinary routing;
- direct INPUT socket-owner matching was rejected experimentally: the reply reached the
  exact INPUT candidate rule but `meta skuid` did not identify the receiving ping socket;
- carrying admitted OUTPUT process identity through a conntrack mark passed privileged CI:
  bound probe success, unbound alternate-path rejection, wrong-target rejection and
  unaffected unrelated local traffic;
- `NetworkEndpoint.LOCAL_PROCESS` and bound-output/protocol dispatch semantics were added
  without exposing Linux uid/mark in the semantic contract;
- the concrete Linux compiler deliberately still rejects LOCAL_PROCESS until EXP-024 is
  confirmed on the Debian 13 target;
- common TrafficSelector gained exact ICMP message types; production nft output is
  kernel-syntax checked in privileged CI;
- `ProbeRulesCalculator` now derives exact ICMP echo request/reply policy and deduplicates
  logical probes that share one physical target/interface/mechanism plane;
- same target on different concrete interface generations remains distinct;
- ProbeRulesState remains deferred until physical LOCAL_PROCESS apply/renew observation
  exists, after which the mandatory comparison with PayloadRulesState must be performed;
- focused reviews and whole-slice audit passed.

---

## 2026-11-14 — NG2 Linux instance infrastructure lifecycle

Migrated the proven NG1 namespace/veth infrastructure boundary into NG2 without restoring
NG1 policy machinery:

- schema-v1 topology remains namespace + host veth + fixed inner `host0` with explicit
  IPv4 addresses and namespace default route;
- existing namespaces are dual-stack protectively closed before structural verification;
- fresh creation owns only namespace/veth/address/main-route infrastructure and creates no
  nft policy;
- partial instance state and structural drift fail closed rather than being silently
  adopted/repaired;
- existing-instance verification now proves reciprocal cross-namespace veth peer identity
  from kernel `ifindex/link_index` metadata;
- destroy closes forwarding best effort, removes owned infrastructure and freshly verifies
  absence;
- privileged CI covers fresh create, no-nft ownership, restart containment, drift rejection,
  teardown and partial-state rejection;
- focused review `NG2-2026-11-14-runtime-instance-lifecycle-review.md` passed.

---

## 2026-11-14 — NG2 protective runtime bootstrap and namespace assembly

Closed the startup forwarding window above the structural Linux Adapter and added the
first production runtime assembly path:

- runtime bootstrap now requires a fresh readback proving
  `net.ipv4.ip_forward=0` before exposing `LinuxNetworkRulesAdapter`;
- failed/unverified protective close returns no Adapter;
- bootstrap deliberately leaves stale physical policy behind the closed forwarding barrier
  until the first normal owner reconcile;
- privileged restart integration starts from stale nft state plus forwarding enabled,
  proves bootstrap closure, then proves the first Adapter reconcile removes stale policy
  before reopening forwarding;
- `NetworkNamespaceLinuxRunner` executes the Linux Driver inside one pre-existing named
  ROU namespace using argv-only `ip netns exec`, preserving stdin/check semantics;
- namespace execution does not acquire namespace/veth lifecycle ownership;
- production assembly helper builds namespace runner -> Linux Driver -> protective
  bootstrap -> Linux Adapter for an existing namespace;
- privileged Linux Adapter integration now exercises the production namespace runner
  rather than a parallel test-only implementation;
- focused reviews `NG2-2026-11-14-runtime-bootstrap-review.md` and
  `NG2-2026-11-14-runtime-namespace-assembly-review.md` passed.

Remaining runtime work starts above this boundary; namespace/veth lifecycle ownership,
host-side transport plumbing and RuntimeStateManager assembly remain separate units.

---

## 2026-11-14 — NG2 Linux lower-domain whole-code audit

Completed the post-implementation audit of the structural Linux Adapter lower domain:

- rejected rules that reference unavailable concrete generations no longer become a
  physical-but-uncommitted candidate generation; the Adapter reconciles the last committed
  fail-closed projection and returns FAILURE;
- closed-state and final verification now share one exact verifier with an explicit
  forwarding expectation;
- Adapter/Driver Protocol types and interface-generation observations were tightened;
- test-only OwnerRulesRegistry lookup/length surfaces were removed;
- defensive duplicate generation checks in independently callable compiler layers were
  retained intentionally;
- the bounded boolean nft predicate compiler was retained as justified semantic
  materialization rather than moved above the Adapter boundary;
- the existing exact-ifindex-reuse limitation remains explicit and no history heuristic was
  invented;
- no Linux allocation, nft syntax, conntrack realization or transition phase leaks above
  NetworkRulesAdapter;
- audit-clean code baseline `d56feb60d3e0b0cf7efe0686059e87044975cfcf`
  passed NG2 unit + privileged Linux integration and NG1 validation;
- whole-code review `NG2-2026-11-14-linux-lower-domain-whole-code-audit.md` passed.

Next implementation boundary is runtime/bootstrap assembly; incremental transition
optimization remains intentionally deferred.

---

## 2026-11-14 — NG2 structural Linux NetworkRulesAdapter

Implemented and live-validated the first concrete Linux lower domain behind
`NetworkRulesAdapter`:

- owner identity is mapped to monotonic opaque tokens and routing-domain identity is
  owner-scoped;
- candidate owner rules and technical allocations commit only after fresh verified physical
  success;
- absent concrete interface generations are projected fail-closed without mutating another
  owner's desired intent;
- sequential multi-owner same-name/new-ifindex transitions converge through normal per-owner
  apply operations;
- Linux routing uses owner-scoped tables, longest-prefix RPDB dispatch, protocol 201/202
  ownership tags, ordered metrics below the terminal metric, per-domain terminal
  blackholes, and a final host-ingress unreachable guard;
- nft filtering compiles numeric ifindex generation references and preserves owner
  provenance for NEW-flow conjunctions;
- source NAT maps EGRESS_ADDRESS intent to narrow MASQUERADE rules;
- exact verification covers link generation, owned routes/tables, RPDB, nft policy +
  markers, complete nft table inventory, and ip_forward;
- the first Driver intentionally supports only full structural repair behind
  `ip_forward=0`, with protective close on failure and no guessed rollback;
- dedicated ROU namespace nft policy is exclusive; foreign nft tables are drift and are
  removed under the barrier;
- live CI validates exact apply/renew/cleanup, /0 routing, generation replacement,
  multi-owner lifecycle, route/foreign-nft repair, stateful flow direction, and source NAT;
- focused review `NG2-2026-11-14-linux-network-rules-adapter-review.md` passed.

Runtime/bootstrap assembly and incremental transition optimization remain separate future
units.

---

## 2026-11-14 — NG2 semantic-slice whole-code audit

Completed a whole-code audit of the current NG2 semantic baseline with explicit component
model and subject-domain isolation criteria:

- removed unused retained PayloadTrafficStateRequest state from PayloadTrafficManager;
- moved packet/predicate execution helpers out of the production NetworkRules contract and
  into test-only code, leaving TrafficPredicate as declarative semantic AST;
- removed the unused speculative DesiredRulesByOwner implementation and its tests; opaque
  owner identity remains part of the Adapter API, while concrete owner storage/composition
  will be chosen with the real Adapter backend;
- corrected stale Manager/projector documentation and README status;
- retained predicate boolean composition as justified payload-policy semantics rather than
  backend syntax;
- retained PayloadRulesState relation logic as payload-local until a real ProbeRulesState
  model exists and can be compared;
- confirmed EXP-012/017 boundaries remain intact and no Linux mutation mechanics leaked
  above NetworkRulesAdapter;
- internal review NG2-2026-11-14-semantic-slice-whole-code-audit.md passed.

---

## 2026-11-14 — NG2 PayloadTrafficManager drift/audit reconcile

Completed and reviewed one deterministic PayloadTrafficManager audit pass:

- audit refreshes current Adapter state using the same owner identity;
- repair is triggered by rules convergence, not by payload service severity;
- MATCHED zero-path / DEGRADED / ISOLATED states are not treated as drift;
- DIVERGED or UNKNOWN convergence attempts materialization of current desired rules without
  a new RequestEvent;
- failed repair is freshly observed before publication;
- immediate successful repair may suppress transient drift history because InfoEvents
  represent current state;
- recovery after a previously published isolated state produces a READY/MATCHED transition;
- scheduler/cadence remains outside the semantic audit method;
- internal review NG2-2026-11-14-payload-traffic-manager-audit-review.md passed.

---

## 2026-11-14 — NG2 PayloadTrafficManager request path

Implemented and reviewed the first executable PayloadTrafficManager control path:

- valid PayloadTrafficStateRequest is converted to desired NetworkRulesSpec before it is
  accepted as current managed intent;
- invalid/unrepresentable request does not mutate Adapter state;
- NetworkRulesAdapter calls use the Manager instance itself as opaque owner identity;
- apply/renew operation failures remain separate from observed payload-rules state;
- stale observation after failed operations produces UNKNOWN rather than synthetic FAILED;
- PayloadTrafficStateInfo publication goes only through the Event Delivery Environment port;
- repeated semantically identical InfoEvents are deduplicated;
- shutdown delegates Adapter cleanup with the same owner identity;
- audit/retry scheduling remains intentionally separate from this request-path unit;
- internal review NG2-2026-11-14-payload-traffic-manager-request-review.md passed.

---

## 2026-11-14 — NG2 payload rules relation and traffic-state projection

Extended the reviewed payload-state model:

- PayloadRulesState now enforces core cross-axis invariants;
- semantic equality no longer depends on ordering of routing domains, destinations, or
  allow-only filtering collections;
- conservative divergent relation proofs can classify narrow SAFE restrictions and
  provable UNSAFE endpoint-pair permission widening;
- safe rules restriction does not automatically imply DEGRADED service;
- PayloadTrafficStateInfo now publishes aggregate PayloadRulesState plus requested
  Profiles' observed paths only;
- unknown/stale rules knowledge suppresses current path claims;
- authoritative absence of a requested logical domain is represented as an empty path
  tuple, while foreign observed domains are not promoted to upper-domain Profiles;
- raw NetworkRulesState and Linux/network-stack details remain below the event boundary;
- internal reviews NG2-2026-11-14-payload-rules-relation-review.md and
  NG2-2026-11-14-payload-traffic-state-info-review.md passed.

---

## 2026-11-14 — NG2 multidimensional PayloadRulesState

Added and reviewed the first `PayloadRulesStateCalculator`:

- renamed the earlier generic `PayloadStateCalculator` concept to
  `PayloadRulesStateCalculator`, reflecting that it assesses rules handling payload rather
  than the payload/data plane itself;
- `PayloadRulesState` is explicitly multidimensional: `knowledge`, `convergence`,
  `safety`, and `service`;
- stale observations are non-authoritative and cannot produce a current assessment;
- exact rules can be simultaneously `MATCHED` while service is `READY`, `DEGRADED`
  or `ISOLATED`;
- divergent proven isolation is classified `SAFE + ISOLATED`;
- non-isolated divergence remains conservative `UNKNOWN` until a semantic relation can be
  proven;
- the calculator consumes only desired/observed network-rules contracts and does not
  re-read payload config;
- a future review is explicitly required after `ProbeRulesState` exists to determine
  whether both state models justify a common rules-state type;
- internal review `NG2-2026-11-14-payload-rules-state-review.md` passed.

---

## 2026-11-14 — NG2 Adapter owner identity registry

Added and reviewed the first Adapter-internal owner-lifecycle utility:

- `DesiredRulesByOwner` keys ownership by Python object identity, not semantic names,
  equality or hashes;
- registered owners are kept strongly alive until explicit removal, preventing `id()`
  reuse while a scope exists;
- registry removal is idempotent and is only the internal registration step of the broader
  Adapter `cleanup(owner)` contract;
- the registry deliberately does not merge policies, assign owner priority or interpret
  caller type/domain;
- NG2 Python CI was added and passed on Python 3.13;
- internal review `NG2-2026-11-14-adapter-owner-registry-review.md` passed.

---

## 2026-11-14 — NG2 semantic payload NAT contract

Completed and reviewed the payload NAT projection:

- `PayloadNatMode.NONE` emits no source-translation intent;
- `PayloadNatMode.MASQUERADE` becomes network-rules
  `SourceNatTarget.EGRESS_ADDRESS`;
- Linux/nft `postrouting` and `masquerade` mechanics remain below the Adapter boundary;
- source NAT is bound to concrete generation-aware egress identity;
- more-specific Profile destinations are excluded from broader NAT intents;
- NAT projection stays independent from traffic-envelope filtering semantics;
- internal review `NG2-2026-11-14-payload-nat-review.md` passed.

---

## 2026-11-14 — NG2 payload filtering and Adapter ownership boundary

Completed the first reviewed payload-filtering contract slice:

- `NetworkRulesAdapter` ownership is now opaque caller-instance identity rather than a
  semantic `NetworkRulesScope`; the contract includes idempotent `cleanup(owner)`;
- independent owner policies remain semantically isolated and may be physically composed
  only inside the Adapter backend;
- `host0` no longer leaks into the payload/network-rules contract; `LOCAL_NETWORK` is
  used as the semantic host-facing endpoint;
- payload traffic-envelope types are independent from network-rules selector types and are
  explicitly converted by `PayloadRulesCalculator`;
- filtering is allow-only with separate effective `traffic_allows` and
  `flow_initiation_allows` semantics;
- first-match Device envelope behavior, default allow/drop, and overlapping Profile
  precedence are preserved before the Adapter boundary;
- terminal routing policy is semantic `DROP | REJECT`; Linux blackhole/unreachable route
  types remain Adapter implementation details;
- canonical `InterfaceIdentity` moved to a neutral cross-domain module;
- internal review `NG2-2026-11-14-payload-filtering-review.md` passed after accepted
  boundary-cleanup findings were fixed.

---

## 2026-11-14 — NG2 first executable network-rules slice

Started the NG2 Python reference under `design/NG2/code/python/rou`:

- introduced `NetworkRulesSpec` routing/dispatch contracts;
- kept Adapter ownership/context as a separate `NetworkRulesScope` method argument rather
  than embedding caller usage into the common rules structure;
- added generation-aware interface references and explicit Adapter state/result contracts;
- added the first `PayloadRulesCalculator` routing slice with ordered paths,
  longest-prefix dispatch, zero-path terminal blackhole, and duplicate-destination
  ambiguity rejection;
- added 11 rootless unit tests across the two new modules.

Filtering, NAT and the Linux Adapter implementation remain intentionally deferred to the
next slices rather than being copied wholesale from NG1.

---

## 2026-11-14 — NG2 PayloadTrafficManager contracts

Defined `design/NG2/payload-traffic-manager.md`:

- `PayloadTrafficManager` remains the payload-domain Engine;
- `PayloadRulesCalculator` maps payload intent to abstract `NetworkRulesSpec`;
- `PayloadStateCalculator` maps observed network-rules state back to payload semantics;
- `NetworkRulesAdapter` is a Direct semantic boundary with explicit
  `apply/renewState/getLastState` contracts;
- Adapter action result is separated from observed state;
- Linux numeric allocation, safe transition/barrier logic, mutation ordering and fresh
  verification are hidden behind the Adapter boundary;
- legacy NG1 metric-history and central Planner responsibilities are assigned to their NG2
  domains instead of being preserved as PayloadTrafficManager state.

The generic component model was also refined: Machinery is expected to be Direct by
default; Indirect semantics are exceptional, explicitly marked and treated as a design
review warning.

---

## 2026-11-13 — NG2 Engines/Machinery taxonomy and runtime boundary correction

The reusable component model was refined into two component families:

- `Engines` are asynchronous event-space participants: `Manager` and `Agent`;
- `Machinery` is invoked from another execution flow: `Calculator`, `Adapter`,
  and `Driver`;
- Machinery is additionally classified as `Direct` or `Indirect` depending on whether
  the requested result returns through the call or arrives later through event space;
- Machinery is externally stateless to its caller even when its hidden implementation is
  internally stateful;
- `Adapter` now denotes a semantic/domain boundary and may hide an arbitrarily complex
  lower subsystem;
- `Driver` denotes the direct technical boundary to an external mechanism;
- the complete synchronous dependency graph inside each visible domain must be a DAG, and
  an adapted lower domain must not establish an independent synchronous back-edge into the
  caller's domain.

The NG2 runtime model was corrected accordingly:

- future VPN process/device lifecycle management is no longer modeled as a current
  `DeviceManager`;
- active path checks are owned by `AvailabilityProbeManager`, whose managed domain is the
  probe subsystem rather than endpoint availability itself;
- `TrafficManager` is narrowed/named `PayloadTrafficManager`;
- probe, payload-traffic and publication domains remain separate even when they reuse the
  same lower network-rule Machinery.

---

## 2026-11-13 — NG2 component and runtime event model

VPN-GATE enters NG2 as a component-architecture redesign rather than a mechanical NG1
refactor.

The reusable architecture vocabulary is now defined independently in
`design/component-model.md`:

- `Manager` is a semantic boundary over a managed domain and publishes its current
  externally relevant state;
- `Agent` is the observe-only specialization of Manager;
- `Adapter` is a synchronous technical boundary and never participates in the event graph
  by itself;
- `Calculator` is an explicit pure data transformation;
- internal communication uses `InfoEvent` and `RequestEvent` over an abstract Event
  Delivery Environment;
- statefulness is an implementation property of Agent/Manager rather than a separate
  architectural `Engine` role;
- synchronous Adapter dependencies must form a DAG; feedback cycles are closed through
  asynchronous event boundaries.

A non-normative comparison with established pub/sub EDA, Kubernetes controllers/operators,
MAPE-K, Event-Carried State Transfer and Ports & Adapters is recorded in
`design/component-model-analogues.md`.

The first NG2 normative runtime contract is in `design/NG2/runtime-event-model.md`. It
covers steady-state runtime only, defines `RuntimeStateManager`, the top-level Agents and
Managers, the current-snapshot/calculator flow, event envelope and the initial event
catalog. Bootstrap, shutdown and internal Manager decomposition are intentionally deferred.

NG1 remains historical architecture/evidence and is not rewritten to match NG2.

---

## 2026-11-13 — NG1 Profile-facing interface balancing direction

The availability/control design now records `interface_balancing` as the provisional
Profile-facing configuration direction. Explicit forms such as
`icmp/172.21.201.19` or `tcp/172.21.201.19:443` express whether a concrete binding
actually provides what that Profile needs; the result remains Profile-local rather than
global Device/interface health.

Target-less forms such as `interface_balancing = "icmp"` are reserved conceptually for
future path-specific target derivation from already-known Device/interface/peer/Profile
information. That derivation algorithm, exact grammar, DNS semantics and timing/hysteresis
remain intentionally undecided.

## 2026-11-13 — NG1 Profile-binding availability model reset

Availability semantics were generalized before implementing the production detector:

- availability is now a current relation between one Profile and one concrete bound
  interface; the runtime result is ON/OFF rather than global
  UNKNOWN/AVAILABLE/UNAVAILABLE on a Device binding;
- DeviceEngine owns binding only. Availability/control conditions are external and may
  include link usability, active endpoint probes, manual inhibits, schedules or future
  Profile/interface-specific predicates;
- availability/control state is never persisted; retrospective state belongs in logs;
- deterministic metric projection remains independent of ON/OFF;
- the old UNAVAILABLE_METRIC and persistent shadow payload fallback were removed from the
  production code and tests;
- the former ECMP hash-policy production prerequisite was removed with that fallback;
  EXP-013 and EXP-016 remain historical Linux/FIB evidence;
- EXP-019/020 are retained as path-liveness evidence and EXP-021 passed on target Debian 13,
  proving a narrow unprivileged ICMP condition plus the exact-ifindex-reuse boundary;
- EXP-022 is prepared to prove an isolated RPDB/routing/nft probe plane before any
  user-facing availability configuration grammar is frozen.

The current production core is therefore again the deterministic baseline: Device
bindings, stable Profile-local metrics, normal routes and terminal blackholes. Generic
Profile-binding ON/OFF materialization remains future work after EXP-022.

---

## 2026-11-12 — NG1 autonomous dead-code and CI cleanup

Post-implementation audit cleanup completed without changing production routing/firewall
semantics:

- removed the unused legacy iptables filter/NAT modules and their dedicated unit/integration
  tests from the production ROU package;
- removed dead `observe_nft_generation_refs()` and
  `classify_device_to_host_profile()` helpers and collapsed the package-level export facade;
- `rou up` now leaves appliance preparation to systemd `ExecStartPre=rou prepare`
  instead of running the same preparation twice;
- public documentation now distinguishes administrator commands from the
  systemd-internal `prepare|contain|run` hooks;
- core NG1 CI no longer installs legacy/VPN experiment packages or runs EXP-020;
  EXP-020 remains archived experiment evidence;
- pushes to `code-cycle-*` branches now trigger NG1 CI automatically;
- ROU v0 and RC2/RC3 migration/inheritance history moved from the normative architecture
  to `design/NG1/ng1-history.md`.

---

## 2026-11-12 — EXP-019 PASS: WireGuard raw availability evidence

Future DeviceManager research established that WireGuard interface presence and
latest-handshake age are insufficient as prompt liveness indicators.

A disposable two-namespace WireGuard experiment proved:

- wg0 remains present with the same ifindex while its UDP underlay is broken;
- an active path probe fails during the outage and recovers after underlay restoration;
- the same wg0 generation survives the full loss/recovery cycle;
- latest-successful-handshake timestamp remained unchanged across the short outage and
  successful payload recovery.

Consequence: a future WireGuard positive UNAVAILABLE detector must not rely solely on
interface presence or handshake age. Active path probing is viable raw evidence, but probe
target/cadence/threshold semantics are intentionally left for a human-approved
DeviceManager design.

Attempts 1–3 are preserved as harness/environment false negatives; attempt 4 is PASS.

EXP-019 is archived evidence rather than a permanent dependency of the completed core NG1
CI. A DeviceManager implementation that relies on this behavior will add its own permanent
integration coverage.

---

## 2026-11-12 — EXP-016 PASS: production ECMP hash policy fixed to 1

EXP-016 closed the future availability prerequisite for ECMP fallback.

Privileged disposable-netns evidence proved:

- target kernel accepts fib_multipath_hash_policy values 0, 1, 2 and 3;
- policy 1 keeps one repeated TCP 5-tuple on a stable nexthop;
- policy 0 ignores L4-only variation for a fixed L3 pair;
- policy 1 uses L4 variation across both ECMP members;
- the sysctl is namespace-isolated.

NG1 now owns and exactly verifies:

```text
net.ipv4.fib_multipath_hash_policy=1
```

Fresh instance creation and restart/ensure use the same shared prerequisite compiler, so
bootstrap and runtime no longer duplicate sysctl policy.

The hash-policy gate is closed. Positive UNAVAILABLE classification and DeviceManager
availability semantics remain future work.

---

## 2026-11-12 — NG1 production nft baseline and full disposable cycle PASS

The current NG1 Python production baseline now uses nftables as its only production
filter/NAT backend.

Completed and verified:

- EXP-017 PASS: numeric nft iif/oif rules preserve concrete interface-generation identity
  across same-name/new-ifindex replacement;
- generation-safe nft verification uses complete policy semantics plus stable
  compiler-owned generation markers;
- legacy iptables remains regression/historical evidence only;
- Planner supports both ordinary binding lifecycle and proven ROUTE_ADDITIVE incremental
  transitions without unnecessary global ip_forward=0;
- post-prerequisite reassessment accepts the same proven incremental transition set as
  initial assessment;
- disposable privileged production cycle passes:
  initial reconcile, same-name/new-ifindex replacement, metric promotion, ordinary member
  disappearance, structural foreign-nft barrier repair and durable runtime-state verify;
- rootless NG1 and RC3 suites and privileged kernel integration are green on the reviewed
  baseline.

Future-gated work remains intentionally separate:

- EXP-014 multi-interface remote-initiated flow pinning — postponed until after the first
  working production release;
- EXP-015 real TCP MTU/MSS signoff;
- EXP-016 ECMP hash-policy prerequisite before enabling a real UNAVAILABLE trigger;
- DeviceManager availability/process lifecycle work after the core baseline is otherwise
  complete.

---

## 2026-11-12 — NG1 Draft 5 correction implementation and kernel proof

Implemented the accepted safety-correction review across the production Python ROU:

- remote-initiated Profiles are rejected unless active capacity is exactly 1 and every
  active Device has restrictive envelope `default=drop`;
- INPUT/FORWARD/OUTPUT are all default-DROP with explicit local/transit admissions;
- ordinary binding lifecycle is classified separately from structural drift;
- lifecycle route repair is a semantic diff and continuously preserves each Profile
  table's terminal blackhole;
- full owned RPDB priority window 1..32765 is verified, not merely current rule range;
- local publication address is carried through runtime -> Planner -> INPUT materialization;
- iptables save/restore verification now normalizes counters, chain serialization and
  canonical state/match ordering instead of comparing fragile raw text;
- bootstrap installs/verifies default-DROP filter before runtime/publications;
- boot-time `ensure_instance`, containment commands, persistent systemd instance lifecycle
  and hardened state path were added;
- runtime state rejects symlink ancestors;
- `rou show` now uses the production projectors/verifiers for full desired-vs-live status.

Additional whole-code review finding:

- legacy iptables interface admission is name-based and cannot by itself prove zero-window
  isolation across same-name/new-ifindex replacement. EXP-017 was prepared as the strict
  dynamic-generation firewall backend gate.

GitHub validation at commit `958aec8dff27d1042755883626ff74e0480de54c` passed both
rootless and privileged kernel-integration jobs.

---

## 2026-11-12 — NG1 Draft 5 correction: remote-init safety, local firewall, barrier scope

External whole-model review found three material safety gaps and one over-conservative
transition rule. The review and independent analysis are archived verbatim in
`design/reviews/`; the project response is separate.

Accepted corrections:

- INBOUND/BIDIRECTIONAL Profiles are production-valid only at active interface capacity 1;
- remote-initiated Profiles additionally require restrictive Device envelopes with
  terminal `default=drop`;
- multi-interface remote-initiated return steering is deferred behind EXP-014 connmark/
  fwmark evidence;
- ESTABLISHED/RELATED state acceptance is explicitly bound-interface <-> host0 only;
- ROU INPUT and OUTPUT are both default-DROP with narrow local/underlay admissions;
- persistent shadow fallback is retained, while its positive UNAVAILABLE trigger remains
  deliberately deferred to future DeviceManager/availability work;
- ordinary binding/availability lifecycle transitions no longer require global
  `ip_forward=0`; the global barrier is reserved for structural/unknown drift and
  unverified recovery;
- rou-up ordering now establishes and verifies fail-closed state before publications;
- `fib_multipath_hash_policy` is made an explicit future prerequisite (EXP-016);
- real TCP MTU/MSS behavior is gated by EXP-015 instead of guessed TCPMSS policy;
- PROJECT-CONVENTIONS now names NG1 as current normative architecture and permits the
  existing English NG1 baseline.

Prepared experiments:

- EXP-014 — remote-initiated flow pinning;
- EXP-015 — real TCP MTU/MSS;
- EXP-016 — ECMP hash-policy prerequisite.

The pre-correction implementation is preserved on branch
`ng1-production-draft5-pre-expert-review-20261112`.

## 2026-11-11 — NG1 Draft 4: explicit NEW verdicts; EXP-013 closed

Final Draft 3 + EXP-013 review found one materialization ambiguity in overlapping Profile
prefixes on a shared Device. Draft 4 resolves it by making NEW-flow direction policy
explicit rather than omission-based.

- every enabled (Profile, Device, remote-prefix) pair materializes an explicit ACCEPT or
  DROP verdict for each relevant direction;
- generated NEW-flow verdicts are longest-prefix-first, preventing a broader allowing
  Profile from bypassing a more-specific deny;
- Device-envelope restrictive rules still precede generated direction verdicts;
- rootless firewall-intent projection now covers both overlap counterexamples;
- EXP-013 is recorded as PASS and the unavailable-path persistent shadow fallback is no
  longer implementation-gated;
- multipath member disappearance is documented as a full Profile-route reprojection under
  the protective fail-closed barrier;
- a three-member persistent-shadow route example was added for operator clarity.

NG1 Draft 4 is the implementation baseline for broader production routing/firewall work.

## 2026-11-11 — NG1 Architecture Draft 3: direction/envelope/routing clarification

External concept/architecture review exposed missing production semantics around unmatched
host0 traffic, shared Devices, Profile direction, Device firewall ownership, lifecycle and
bootstrap prerequisites.

Draft 3 now defines:

- host0-scoped RPDB dispatch plus terminal host-ingress fail-closed action;
- Profile `destinations[]` as remote/VPN-side prefixes;
- stateful generated Profile-direction guard with NEW / ESTABLISHED,RELATED / INVALID
  semantics;
- Device -> host Profile classification by remote source prefix + Device membership;
- separate administrator-authored Device `traffic_envelope` firewall;
- shared-Device example demonstrating different Profile directions on one concrete tunnel;
- no mandatory conntrack-mark requirement for return routing;
- over-quota/unbound interface payload isolation;
- deterministic first-observed quota promotion without lexical interface reordering;
- Device-process startup sequence inside the already-created ROU namespace;
- publication supervision;
- bootstrap-owned stable link addressing and required namespace forwarding/rp_filter state;
- v0 -> production migration boundary, production test layers, representability/scale
  policy and host-VPN coexistence guidance.

The external review and clarification dialogue are preserved verbatim in
`design/reviews/NG1-2026-11-11-concept-architecture-review.md`; disposition is recorded
in the matching response document.

EXP-013 remains the implementation gate for unavailable common-metric projection.

## 2026-11-11 — NG1 production config/domain implementation begins

The first production NG1 implementation slice now exists under
`design/NG1/code/python/rou/`.

- immutable Device/Profile/ExpectedInterface domain objects;
- TOML -> ActiveConfig loader for the agreed configuration surface;
- disabled placeholder semantics;
- strict IPv4 destination and Device-reference validation;
- active ExpectedInterface overlap validation;
- pure Profile metric-layout compiler with device_order -> expected_interfaces priority;
- disabled Devices consume no current metric range;
- reserved metric tail: normal < UNAVAILABLE_METRIC < BLACKHOLE_METRIC;
- unresolved publication/traffic-envelope TOML fields are rejected rather than guessed;
- dedicated NG1 Python GitHub Actions validation was added.

Rootless validation before commit: Python compileall PASS; **27/27 unit tests PASS**.

## 2026-11-11 — NG1 production model and initial TOML configuration contract

The first production-capable NG1 domain/runtime model is frozen before implementation.

- Device/Profile are separate global policy entities;
- PlannerEngine, DeviceEngine and TrafficEngine define the primary processing boundaries;
- Engine-related runtime/diagnostic artifacts use planner-*, device-* and traffic-* subject prefixes;
- Device discovery now uses ordered `expected_interfaces[]` entries with typed EXACT/PREFIX matching and per-entry `interface_quota`;
- the aggregate Device quota is derived from ExpectedInterface quotas;
- Profile priority is `device_order[]` followed by Device `expected_interfaces[]` order;
- bound interface identity remains `(ifname, ifindex)`, with stable Profile-local metric assignment for the continuous bound lifetime;
- normalized AVAILABLE/UNAVAILABLE state is separated from binding lifetime;
- disabled Device/Profile declarations may be minimal placeholders;
- the initial human-facing format is TOML with named `[device.<id>]` and `[profile.<id>]` tables;
- enabled Profiles require explicit direction, non-empty destinations and non-empty device_order;
- enabled Devices require non-empty expected_interfaces;
- prefix selector syntax is `<prefix>*/<quota>`; exact selectors have implicit quota 1;
- detailed DEBUG decision logging is required for all Engines.

ROU v0/EXP-012 remains historical executable evidence; its BindingSpec/capacity terminology
is not normative for the production NG1 model.

## 2026-11-10 — RC3 binding-specific networks and heterogeneous failover

The post-EXP-009 profile model was corrected after live-test design exposed that one
profile-level transport network cannot describe independent failover interfaces such as
`wg0` and `wg1` on different VPN subnets.

Current model:

- profile-level `interface` and `network` are removed;
- enabled profile contains ordered `bindings[]`;
- each `BindingSpec` owns `interface = exact|prefix+` and its own IPv4 `network`;
- old LIST selector domain form is removed;
- exact BindingSpec rank defines stable fixed metrics and natural failback;
- all prefix BindingSpec of a profile share one cyclic dynamic allocator starting after
  the exact metric range;
- prefix survivors keep order/metrics; removed metrics stay reserved until verified commit;
- top-level/profile `enabled` use staged parsing; disabled profile bodies are ignored;
- top-level disabled mode is an intentional `DISABLED` lifecycle state with forwarding off;
- selector namespace safety now rejects prefix guards that would include forbidden exact
  interface names;
- verified process-local state uses prepare-then-commit semantics;
- structural route verification failure escalates to `INIT/PANIC`, while verified
  zero-path availability remains `DEGRADED`.

Normal ADD/REMOVE/INIT-PANIC runtime procedures remain unchanged; the primary implementation
change is config/domain/snapshot projection and metric derivation.

The permanent GitHub Actions workflow now validates Python 3.13 compileall and the complete
unit suite on every push/PR to `main`.

This entry supersedes earlier same-day descriptions of profile-level `network`, LIST
selectors and a prefix allocator starting unconditionally at metric 10; those entries are
retained below as historical development record.

## 2026-11-10 — RC3 stable prefix order and metric allocator implemented

Python implementation now matches the revised prefix ordering/metric architecture.

- prefix bindings preserve verified process-local relative order while continuously active;
- new bindings append instead of causing ASCII reordering of existing firewall/NAT blocks;
- simultaneous newly observed bindings use ASCII only as a local tie-breaker;
- prefix metric allocation is cyclic and process-local;
- existing bindings preserve allocated metrics;
- every daemon-owned UNICAST metric is strictly below `BLACKHOLE_METRIC`;
- explicit-list validation now uses `BLACKHOLE_METRIC`, not merely uint32 capacity;
- `FIRST_UNICAST_METRIC` is independent from `ROUTE_METRIC_STEP`;
- snapshot projection failure, including allocator exhaustion, isolates fail-closed;
- verified active order, allocator mapping and cursor share one commit boundary.

Validation: Python 3.13 `compileall` PASS; **130/130 unit tests PASS**. The temporary
validation workflow was removed after the successful run.

## 2026-11-10 — RC3 prefix bindings keep stable process-local order

The prefix metric allocator simplification is extended to firewall/NAT/status ordering.

For `prefix+`:

- continuous active bindings keep their relative process-local order;
- a newly accepted binding is appended after existing bindings;
- a removed binding disappears without reordering survivors;
- if several new bindings are first observed in one snapshot, only that new group uses
  bytewise ASCII as a deterministic tie-breaker;
- INPUT/FORWARD exact blocks, VPNG-INGRESS and NAT follow this stable process-local order;
- a lexically earlier new interface therefore does not change the relative desired order of existing exact rules; a protective full-policy restore may still rebuild the owned chain transactionally;
- status exposes the order as useful diagnostic evidence of first acceptance by the
  current daemon process;
- the order is not persisted across restart and is not a route-priority guarantee.

The verified prefix active order and metric allocator mapping/cursor share the same
commit boundary after successful verification.

## 2026-11-10 — RC3 prefix metrics become a cyclic technical allocator

The architecture no longer derives `prefix+` route priority from ASCII interface-name
ordering.

- exact selector keeps metric 10;
- explicit ordered list keeps administrator-defined stable priority slots;
- `prefix+` uses a process-local cyclic allocator for unique technical UNICAST metrics;
- continuous `ConcreteBinding(name, ifindex)` keeps its allocated metric;
- newly appearing prefix bindings do not renumber existing routes;
- all daemon-owned UNICAST metrics are strictly lower than `BLACKHOLE_METRIC`;
- allocator wraps to the first metric, skips occupied values and fails closed only if all
  valid slots are exhausted;
- allocator state is committed only after successful verification and is not persisted
  across restart;
- ASCII ordering remains only for canonical policy/status construction and reproducible
  traversal of simultaneously new bindings; it is not a route-priority contract.

## 2026-11-10 — RC3 post-simplification code cleanup

A focused code audit verified initialization, discovery, monitoring and fail-closed
protection after removing peers and `local_address`.

Removed migration/dead state:

- write-only committed candidate history;
- obsolete untyped `list_interface_ipv4()` kernel boundary and its three tests;
- abandoned route-overlap cache/helper;
- unused daemon ACL merge helper;
- unused selector/state convenience properties;
- redundant ConfigLoader selector-validation constants;
- duplicate ProfileResult completeness check.

The IPv6 prerequisite latch is now checked before interface inventory; while latched,
periodic passes still reassert forwarding-off/isolation policy but skip unnecessary
interface discovery.

Core monitoring semantics were intentionally retained:

- LINK events for interface create/delete/recreate and ifindex identity;
- IPv4 address events for `network` membership transitions;
- route events for low-latency drift detection;
- periodic full reconciliation as the source-of-truth fallback.

Validation: Python 3.13 `compileall` PASS; **121/121 unit tests PASS**. The test count
decreased by exactly three because the deleted legacy kernel API no longer requires tests.

## 2026-11-10 — RC3 removes redundant local_address

External optimization review identified that the post-EXP-009 `local_address` field had
only one remaining function: qualifying a selector-matching candidate as an active
interface. The already mandatory `network` field fully covers that requirement.

Accepted change:

- `local_address` removed from the normative closed schema, domain model and Python
  `VpnProfileConfig`;
- legacy `local_address` is now an unknown managed profile key;
- a candidate becomes active when at least one of its local IPv4 addresses belongs to
  `profile.network`;
- different concrete interfaces of one profile may use different host addresses inside the
  same transport network;
- an interface with no IPv4 or only addresses outside `profile.network` remains
  candidate-only and guard-blocked;
- applicability checks host-address membership only; actual interface prefix length is not
  required to equal the logical transport network prefix;
- exact host-address assignment remains transport configuration, not VPN-GATE state.

Validation after implementation:

```text
Python 3.13 compileall: PASS
Unit tests: 124/124 PASS
```

The first validation run caught one stale firewall-test helper still passing the old exact
IPv4 argument to the resolver; after correcting that fixture, the full suite passed.
The temporary validation workflow was removed.

## 2026-11-10 — RC3 interface-centric architecture and implementation after EXP-009

- EXP-009 completed: OpenConnect multi-interface lifecycle, direct `dev` routing and
  WireGuard peer-selection semantics validated live.
- Removed transport `peers` / `PeerBinding` from the normative VPN-GATE route model and
  Python runtime configuration.
- Selector grammar is exact, `prefix+`, or ordered explicit exact list; legacy `%` is
  rejected.
- Multiple simultaneous concrete interfaces are normal for prefix/list selectors.
- Candidate applicability remains gated by stable configured `local_address`.
- Daemon-owned UNICAST routes are direct `dev <exact-interface> proto 202` routes with
  no transport next-hop and no `onlink`.
- Prefix metrics derive from case-sensitive bytewise ASCII ordering of the current active
  set; explicit-list metrics use stable configured slots.
- Full firewall/NAT policy materializes every active exact interface; prefix matching is
  deny-only.
- Runtime IPv6 prerequisites are revalidated before allowing reconciliation and a violation
  latches the host-prerequisite isolation path until restart.
- Verification success is separated from functional availability: verified zero-path state
  is committed and yields `RUN/DEGRADED`, not a false route-verification failure.
- Four independent review/fix iterations were completed (networking, security/firewall,
  config/domain, implementation/operations), followed by a cross-domain
  **ACCEPT — NO FINDINGS** review.
- Python 3.13 validation after implementation: `compileall` PASS and **121/121 unit tests
  PASS**. The temporary validation workflow was removed after the run.

# VPN-GATE change log

## 2026-11-09 — RC3 принят к реализации после post-final review

Обработан внешний review архитектуры, выполненный по состоянию до EXP-006.

- startup IPv6-проверки разделены на глобальные условия -> snapshot -> per-interface
  условия -> разрешение селекторов;
- `disable_ipv6=1` проверяется для всех совпадающих интерфейсов, включая `AMBIGUOUS`;
- изменение обязательных IPv6 sysctl во время `RUN` явно отнесено к неподдерживаемому
  изменению доверенной host configuration; IPv4 `ISOLATED` не объявляется защитой от
  IPv6 drift;
- INPUT-only restore payload явно запрещено распространять на FORWARD-цепочки;
- EXP-006.2 явно фиксирует блокировку уже установленного `ESTABLISHED,RELATED` потока,
  что фактически подтверждено завершившимся `PASS`;
- очищена терминология §9.4;
- устаревший открытый EXP-006 gate удален из §25 и migration checklist обновлен;
- статус нормативной архитектуры RC3: **принят к реализации**.

Код не изменен.

## 2026-11-09 — Финальный документальный review RC3

Архивирован внешний финальный review RC3 и сохранен отдельный project response.

По результатам review:

- текущая русская техническая проза очищена от оставшихся ненормативных англицизмов;
- для авторского технического текста закреплено использование `е` вместо варианта с
  двумя точками; внешние verbatim-артефакты не переписываются;
- §11/§11.1 описывают текущую NAT-модель без исторических оборотов;
- §8.2 объясняет, почему начальный startup не требует isolation barrier;
- IPv4-only deployment дополнительно требует выключенного IPv6 на управляемых
  VPN-интерфейсах;
- follow-up review отказался от анализатора сторонних INPUT-цепочек: подтвержденный INPUT-only drift восстанавливается точечно без изменения `ip_forward` и транзитной политики; Fail2ban остается обычной host-policy после daemon-owned INPUT-префикса;
- `EXP-006` выполнен на Debian 13 / Linux 6.12.115 / iptables-nft 1.8.11: все четыре
  подэксперимента PASS; подтверждены замена существующих chains через `--noflush`,
  `full -> isolation -> full`, точечный INPUT-only repair при живом транзите и
  транзакционно чистая ошибка restore; implementation gate firewall orchestration снят.

Код не изменен.


## 2026-11-09 — Обработка review RC3 после терминологической правки

Архивирован новый внешний review RC3 после terminology pass и сохранён отдельный
project response.

Принятые правки:

- устранены оставшиеся голые употребления `runtime` в обычной прозе;
- «среда выполнения» заменена на «среда исполнения»;
- таблица пустых параметров использует `profile.peers`;
- уточнена формулировка про проекцию конфигурации для исполнения;
- контракт IPv6-пересылки привязан к baseline Debian 13 / Linux 6.12 и отдельно описывает
  возможные будущие независимые per-interface overrides;
- явно задокументировано, что isolation barrier блокирует также существующий входящий
  ESTABLISHED-трафик управляемых VPN-интерфейсов, включая административные сессии.

Policy D1/D4/D5 не меняется.


## 2026-11-09 — Восстановление внешних RC3 review verbatim

Повторная сверка с исходными Library-артефактами показала, что при первоначальном
архивировании архитектурного review RC3 и аудита §26 в исходные тексты попали небольшие
редакционные изменения. Оба source review восстановлены дословно.

Содержательный проектный ответ остаётся действующим; в него добавлена запись о проверке
целостности источников. Семантика архитектуры RC3 не меняется: все ранее принятые
замечания review уже отражены в нормативных документах.

## 2026-11-09 — RC3 pure firewall/NAT policy model

A pure policy layer now derives both RC3 policy forms from one model:

- `desired_full_policy(config, interface_state)` returns full firewall + NAT state;
- `desired_isolation_filter(config)` returns a filter-only deny-first barrier and cannot
  carry NAT by type;
- binding-specific ACCEPT/NAT rules use only exact resolved interface names;
- exact ingress blocks precede deny-only selector guards;
- VPN-side generic INPUT NEW acceptance is absent;
- absent/not-ready/ambiguous profiles retain structural deny policy and RETURN-only NAT.

The existing daemon firewall builder is not switched yet; integration follows in a
separate commit.

## 2026-11-09 — RC3 binding-aware route derivation

Route derivation is migrated from RC2 static `CONFIGURED RouteSpec` state to RC3
config + resolved binding semantics:

- BLACKHOLE routes depend only on configuration;
- UNICAST routes exist only for ready profiles and always use the exact bound ifname;
- prefix selector text can no longer enter a `RouteSpec`;
- `VpnProfile` now stores only process-local OWNED routes and committed binding/readiness;
- runtime route passes use typed interface inventory and return profile FAIL for AMBIGUOUS
  selector state after verified fail-closed routes.

ConfigLoader still accepts exact selectors only; prefix activation waits for firewall/NAT
policy migration.

## 2026-11-09 — RC3 typed interface kernel inventory

`SubprocessKernelInterface.list_interfaces()` now exposes immutable `InterfaceRecord`
snapshots with interface name, ifindex and local IPv4 addresses.

The new parser preserves addressless/IPv6-only interfaces, merges duplicate records only
when the ifindex agrees, and rejects conflicting same-name ifindex data. The legacy
`list_interface_ipv4()` boundary remains temporarily available until daemon integration.

## 2026-11-09 — RC3 interface resolution and readiness core

Pure interface-state logic now resolves one typed selector against one inventory snapshot:

- zero matches -> `ABSENT`;
- one match -> `BOUND(name, ifindex)`;
- multiple matches -> `AMBIGUOUS`;
- readiness requires a `BOUND` record containing the configured local IPv4 address.

Resolution output is deterministic and independent of Netlink event payloads; kernel
inventory integration remains a later step.

## 2026-11-09 — RC3 typed selector in runtime configuration

The managed runtime projection now carries `InterfaceSelector` instead of a raw interface
string. Existing RC2 execution paths explicitly render the selector back to an exact
interface name, while ConfigLoader remains exact-only at this migration stage.

Cross-profile interface validation already uses selector-set overlap semantics, preparing
the configuration layer for prefix families without enabling them before binding-aware
route/policy derivation is implemented.

## 2026-11-09 — RC3 implementation bootstrap and interface domain model

Implementation work starts without modifying the frozen RC2 baseline:

- `design/RC3/code/python/` is bootstrapped blob-for-blob from RC2.5.1 in a separate
  mechanical commit;
- RC3 adds immutable `InterfaceSelector`, `InterfaceRecord`, `InterfaceBinding` and
  `InterfaceResolution` domain values;
- exact and prefix-family selector matching/overlap semantics are covered by focused unit
  tests;
- prefix selectors are intentionally not wired into the running loader yet, preventing the
  legacy RC2 route path from receiving `vpns+` before binding-aware route/policy migration.


## 2026-11-09 — RC3 terminology refinements

Terminology is refined after manual Russian-language review:

- `flock` is described as an exclusive lock acquired without waiting, avoiding the
  misleading phrase “exclusive non-blocking lock”;
- `runtime` usage is split between compound technical entities such as
  `runtime-интерфейс` and temporal wording “во время исполнения” for daemon activity;
- “среда исполнения” is preferred over “среда выполнения”;
- `firewall` is restored as an accepted term for installed filtering policy/rules, while
  NAT remains a separate entity and combined state is written `firewall/NAT`;
- `daemon-owned` is restored as an accepted ownership term where it makes architecture
  prose shorter and more precise;
- the empty-list schema example again uses the real `profile.routes` configuration field.

No architecture semantics change.


## 2026-11-09 — RC3 Russian technical editing pass

A terminology-only editorial pass follows the final technical cleanup:

- mixed Russian/English prose is reduced where the English word is not an identifier;
- `handshake` is restored as the established protocol term;
- `ownership`, desired/actual state and daemon-owned wording are aligned with the RC3
  glossary;
- awkward or colloquial wording such as “пожизненная блокировка” and “TOML-экзотика” is
  replaced with normative technical Russian;
- pseudocode and invariant prose are normalized to Russian grammar without changing their
  technical contracts;
- `blackhole` is explicitly recorded as an accepted Linux routing term.

No architecture semantics are intentionally changed.


## 2026-11-09 — RC3 technical consistency cleanup

A final expert review resolves remaining semantic ambiguities before implementation:

- cleanup now treats confirmed `ip_forward=0` as a hard barrier before destructive teardown;
- IPv6 forwarding is an explicit startup prerequisite and must remain disabled outside the
  IPv4-only daemon policy;
- managed VPN INPUT no longer permits generic NEW connections to the gateway itself;
- INPUT/FORWARD/POSTROUTING built-in prefix placement is verified and pre-prefix foreign
  rules are `UNSAFE` drift;
- profile ordering is defined as locale-independent ASCII lexical order of normalized IDs;
- local gateway OUTPUT is explicitly outside source ACL/FORWARD policy;
- managed/unmanaged configuration validation scope is made consistent;
- route priority is bounded to the Linux u32 priority field;
- `ProfileResult` SUCCESS/FAIL semantics are made normative;
- diagnostic reason-code stability is defined without pretending the architecture already
  enumerates the implementation catalog;
- READY/watchdog and ENOBUFS wording is made internally consistent.


## 2026-11-09 — Terminology exception for handshake

`handshake` is added to the project-wide language exceptions and the RC3 normative glossary
as an established protocol-interaction term. It may remain untranslated when referring to a
protocol phase or result, including WireGuard/VPN handshake wording.

No architecture semantics change.

## 2026-11-09 — RC3 Russian terminology audit

A terminology-only pass applies the root `PROJECT-CONVENTIONS.md` language rule to the
entire RC3 architecture. Ordinary prose is rewritten in Russian while technical identifiers,
commands, named states and documented English exceptions remain unchanged.

The audit is archived as
`design/reviews/RC3-2026-11-09-russian-terminology-audit.md`. Using the same heuristic on
narrative prose, ordinary English-like tokens fall from 1864 to 164 (~91.2% reduction).
Section 26 is additionally reviewed manually because its normative prose is inside a fenced
block and therefore is not represented by that metric.

No architecture semantics are intentionally changed.

## 2026-11-09 — Project conventions

A root-level normative `PROJECT-CONVENTIONS.md` is added to preserve repository-wide rules
across review/refactor sessions: Russian-preferred documentation, verbatim review archival,
review filename ordering, separation of semantic and terminology-only commits, historical
experiment baseline handling, and archived-RC discipline.


## 2026-11-09 — RC3 review resolution

RC3 architecture is updated from the archived architecture review and §26 invariant audit.

Safety-relevant changes:

- `VPNG-INGRESS` gains deny-only selector guards after ready exact-interface blocks, closing
  the unbound prefix-family ingress path discovered by review;
- readiness changes are policy-changing transitions just like binding changes and use the
  same deny-first recovery sequence;
- the isolation filter is specified as a complete global filter barrier, including exact
  profile-chain contents and the intentional brief outage of all managed forwarding;
- isolation-filter application is explicitly filter-only; existing NAT may remain behind the
  verified deny barrier until desired NAT is applied and verified;
- verified FORWARD ownership is distinguished from the reaction window caused by a foreign
  rule inserted before the daemon prefix;
- a stable diagnostic-reason model is restored to the normative implementation model;
- OUTPUT remains host-admin policy and foreign POSTROUTING processing is explicitly
  preserved;
- runtime exact `proto kernel` protected-prefix collision is fail-closed DEGRADED;
- a concrete RC2.5.1 -> RC3 implementation migration checklist is added.

The experiment journal now states that historical section/invariant references belong to the
recorded architecture baseline and are not renumbered retroactively.


## 2026-11-09 — RC3 review archive

Two independent RC3 reviews and the project response are archived under `design/reviews/`.
Review filenames now follow `<subject>-YYYY-MM-DD-<description>.md`, so artifacts group by
subject/version and then sort chronologically. Existing RC2 review blobs are renamed without
content changes.


Краткий технический журнал развития реализации. Здесь фиксируются существенные
architecture/implementation milestones, состояние тестов и следующий незакрытый блок.


## 2026-11-09 — RC3 terminology normalization

RC3 terminology is normalized against `design/RC3/terms-and-definitions.md`.

The language pass deliberately avoids mechanical word substitution:

- natural Russian terms are used where they preserve precision;
- dense technical blocks use the documented `English term (Russian meaning)` convention and
  may retain the English short form until the end of the logical block;
- runtime, daemon, snapshot, desired/actual/owned state, ownership, daemon-owned, fallback,
  failover and CLI remain normative English exceptions;
- technical identifiers, commands and named states remain unchanged;
- historical English prose in the experiment log remains in its recorded language, while
  new Russian annotations follow the RC3 terminology document.

No Python implementation files are changed.



## 2026-11-09 — RC3 semantic baseline and project terminology

RC3 documentation is branched from RC2.6.3 without changing the Python implementation.

RC3 incorporates the independent RC2.6.3 consistency review:

- §4.4 no longer treats the deny-only `-i prefix+` guard as an unvalidated future
  experiment; EXP-005 is the validating evidence;
- the architecture claims only the tested ingress `iptables -i prefix+` contract, not an
  untested `-o prefix+` contract;
- `+` is reserved by selector grammar in all positions for exact-selector names; trailing
  `+` additionally has the direct iptables wildcard/prefix rationale;
- EXP-004 keeps its historical `%` decision verbatim in substance and receives a clearly
  marked subsequent RC3 note explaining that EXP-005 superseded the selector syntax.

A normative terminology document is added at
`design/RC3/terms-and-definitions.md`. The architecture references it explicitly.

The experiment log/evidence is now project-scoped at
`design/vpn-gateway-experiments.md` and `design/experiments/`, not tied to RC2.

Python implementation remains RC2.5.1 and is intentionally unchanged. Package split is the
next implementation step after RC3 documentation is finalized.



## 2026-11-08 — EXP-005 PASS; architecture RC2.6.3 adopts iptables-native prefix selector

EXP-005 validated the remaining deny-only interface-family firewall contract on target
Debian 13 / iptables-nft 1.8.11.

Confirmed:

- `iptables-restore` accepts `-i vpns+`;
- `iptables-save` preserves the same canonical operand;
- `vpns+` matches the entire textual prefix namespace, including bare `vpns`, numeric
  suffixes and nonnumeric suffixes;
- an earlier exact `-i vpns0` ACCEPT takes precedence, while another prefix member reaches
  the later deny-only guard.

Architecture advanced to RC2.6.3:

- old vpn-gateway-only percent-sentinel numeric-family syntax is removed;
- `prefix+` is the single prefix-family selector and deliberately mirrors iptables
  semantics;
- the whole textual prefix namespace is reserved by a managed prefix selector;
- trailing `+` exact interface names are unsupported because iptables interprets that
  operand as wildcard/prefix matching;
- wildcard/prefix remains forbidden for ACCEPT/NAT/routes; those always use the resolved
  concrete exact interface.

Python implementation remains RC2.5.1 and is intentionally unchanged.

Next: implementation can proceed without a remaining selector-family firewall experiment.



## 2026-11-08 — RC2.6.2 architecture vivisection APPROVED

Two independent adversarial review passes were archived against RC2.6.2.

Safety/state-machine verdict: **APPROVE**.

- isolation barrier replacement semantics are sufficient;
- isolation verification cannot be confused with full-policy SAFE;
- failure to disable forwarding remains fail-closed under deny-first ordering;
- bootstrap full-filter-before-NAT remains safe because cleanup has already confirmed
  `ip_forward=0`;
- no new ordinary-default-route leak path was found;
- same-name/ifindex replacement remains an explicitly accepted trusted-host reaction-window
  limitation.

Implementation/data-model verdict: **APPROVE**.

- selector -> concrete binding -> kernel resource boundaries are implementable;
- one immutable desired reconciliation snapshot is coherent with fresh ACTUAL verify reads;
- multi-file Python package split is recommended;
- no architecture-level implementation blocker remains.

The only pre-code external contract still requiring target validation is the deny-only
selector-family iptables interface match/canonicalization.

Reviews:

- `design/reviews/RC2.6.2-2026-11-08-architecture-safety-vivisection.md`
- `design/reviews/RC2.6.2-2026-11-08-architecture-implementation-vivisection.md`

Next: target experiment for the deny-only family guard, then staged RC2.6.x implementation.



## 2026-11-08 — Architecture RC2.6.2 final isolation-barrier clarification

RC2.6.2 incorporates the two remaining RC2.6.1 safety re-review clarifications:

- isolation-filter materialization is a complete replacement/canonicalization of the
  daemon-owned filter desired state for that stage, so stale binding-specific daemon ACCEPT
  rules cannot survive underneath the barrier;
- successful isolation-filter verification is explicitly **not** equivalent to full desired
  firewall/NAT SAFE;
- full-policy SAFE requires verified desired NAT plus verified full desired filter for the
  same immutable reconciliation snapshot.

Python implementation remains RC2.5.1 and is intentionally unchanged.

Next: independent RC2.6.2 architecture vivisection before implementation.



## 2026-11-08 — RC2.6.1 architecture re-review

Two independent re-review passes were archived against RC2.6.1.

Result:

- all previous HIGH findings are resolved;
- no new architecture blocker was found;
- safety review requests two narrow clarifications before implementation:
  isolation-filter verification is not equivalent to full-policy SAFE, and isolation
  materialization must replace stale daemon binding-specific ACCEPT state rather than merely
  append denies;
- implementation review considers RC2.6.1 implementable and leaves selector overlap corner
  cases/package migration discipline to unit tests and implementation sequencing.

Reviews:

- `design/reviews/RC2.6.1-2026-11-08-architecture-safety-rereview.md`
- `design/reviews/RC2.6.1-2026-11-08-architecture-implementation-rereview.md`

No architecture change is made by this re-review commit.



## 2026-11-08 — Architecture RC2.6.1 review corrections

Both RC2.6 architecture reviews were accepted and incorporated before implementation.

RC2.6.1 adds:

- deny-first binding-sensitive repair:
  isolation filter -> NAT -> full filter -> routes, with verify between stages;
- the deny-first barrier remains mandatory when `ip_forward=0` cannot be confirmed;
- interface inventory/read/parse/resolution failure is an ISOLATED-class failure because
  full binding-specific policy cannot be derived safely;
- a config-only isolation filter is explicit and contains no binding-specific ACCEPT;
- one immutable pass-level reconciliation snapshot holds interface resolution/readiness,
  desired routes and full desired policy;
- numeric-family selectors reserve their runtime interface-name namespace;
- same-name/ifindex replacement and the kernel-event reaction window are explicit trusted-host
  threat-model boundaries;
- filtered proto-201/202 cleanup remains strict inside the reserved marker namespace;
- status must expose selector/binding/readiness separately from ACTIVE lifecycle state.

The old `filter -> nat` repair contract is removed. Python implementation remains RC2.5.1
and is intentionally unchanged.

Next: short independent re-review of RC2.6.1, then target experiment for deny-only
interface-family iptables matching before implementation.



## 2026-11-08 — RC2.6 independent architecture reviews

Two independent review passes were archived before implementation:

- safety/state-machine review:
  `design/reviews/RC2.6-2026-11-08-architecture-safety-review.md`;
- implementation/data-model review:
  `design/reviews/RC2.6-2026-11-08-architecture-implementation-review.md`.

The safety review found one high-severity ordering issue: after RC2.6 makes NAT and ACCEPT
rules binding-specific, the old `filter -> nat` repair sequence is unsafe if
`ip_forward=0` cannot be confirmed. It recommends a deny-only filter baseline before NAT
and before restoring full ACCEPT rules.

It also requires interface-inventory failure to isolate the daemon because expected policy
can no longer be derived without a trustworthy binding snapshot.

No RC2.6 architecture changes are made by the review commit itself; maintainer disposition
and architecture correction are the next step.



## 2026-11-08 — Architecture RC2.6 after EXP-004

Architecture revised from RC2.4.1 to RC2.6 before further Python implementation.

Key changes:

- complete IPv4 FORWARD ownership: terminal `VPNG-FORWARD-DENY` before foreign rules;
- `interface` is now an exact or numeric-family selector (`vpns%`);
- selectors resolve only to concrete runtime interfaces; wildcard selector text never enters
  RouteSpec/allow/NAT kernel operations;
- selector overlap inside the managed set is a fatal config error;
- runtime binding tracks exact name + ifindex; ambiguity is fail-closed;
- firewall/NAT policy now has structural plus binding-specific parts;
- MASQUERADE and profile allow rules follow a verified ready concrete binding;
- binding transitions isolate forwarding before policy/route rematerialization;
- fixed deny-only selector INPUT guard is required; exact iptables prefix syntax remains a
  target experiment before implementation;
- cleanup route inventory uses selective proto 201/202 queries, while normal reconciliation
  retains strict full-table inventory;
- daemon safely creates/validates its private runtime directory before lock;
- Python implementation may be split into a package/directory with one daemon entry point,
  keeping domain boundaries suitable for a future single-binary Rust implementation.

The bounded kernel-event -> daemon-reaction window for dynamic interface families is explicit
in the architecture rather than hidden behind static-interface assumptions.

Post-EXP expert review:
`design/reviews/EXP-004-2026-11-08-post-review.md`.

Next: independent architecture review before any RC2.6 implementation work.


## 2026-11-08 — EXP-004 gateway boundary validation PASS

EXP-004 completed five live boundary checks after the RC2.5.1 happy-path run.

Validated/observed:

- unmanaged forwarded traffic currently falls through daemon chains into base
  `FORWARD ACCEPT`; because vpn-gatewayd owns global `ip_forward`, complete IPv4
  forwarding-policy ownership is now required;
- on OpenConnect interface loss, the dependent `proto 202` route disappears while the
  `proto 201` blackhole survives and prevents default-route fallback;
- when the VPN reconnects, RC2.5.1 does not restore `proto 202` without daemon
  reconciliation/restart, confirming the known runtime-reconciliation gap;
- ocserv `device` is a prefix, not an exact interface name: occupying `vpns0` produced
  `vpns1`, and `device = vpns0` produced `vpns00`;
- configuration direction is one `interface` key with trailing `%` for a numeric family
  (for example `vpns%` -> `^vpns[0-9]+$`); more than one match is ambiguous and
  fail-closed;
- filter and nat cleanup payloads using duplicate `-D`, then `-F/-X`, succeeded in one
  `iptables-restore --noflush` transaction while preserving foreign rules;
- a synthetic undeleted external reference made `CHAIN_DEL` fail with rc=4 and left the
  table unchanged, confirming per-table transactional behavior on the tested backend;
- `ip -j -N -4 route show table main proto 201/202` cleanly isolates daemon marker routes
  from unrelated foreign multipath state and is suitable for cleanup-specific inventory.

Setup also exposed that standalone foreground startup currently assumes
`/run/vpn-gateway` already exists. Post-EXP review should make the daemon safely
create/validate this private `0700` runtime directory and its expected owner while retaining systemd
`RuntimeDirectory=` as the deployment default.

Full procedure/results: `design/vpn-gateway-experiments.md`.

This EXP supersedes the previous sequencing note that called graceful shutdown
"EXP-004". The next step is a post-EXP architecture/implementation review; lifecycle
shutdown/up-down-up validation moves to EXP-005 unless that review identifies a prerequisite.


## 2026-11-08 — EXP-003 first live end-to-end gateway PASS

RC2.5.1 completed the first real end-to-end happy-path test on the Debian 13 lab topology.

Validated live:

- `net.ipv4.ip_forward=1` after successful startup;
- owned `proto 201` blackhole for `10.0.0.0/8`;
- preferred `proto 202` route via `172.20.130.5 dev vpns0 metric 10 onlink`;
- expected `VPNG-*` INPUT/FORWARD/NAT chains and prefix jumps;
- server-side MASQUERADE on `vpns0`;
- OpenConnect-client forwarding plus egress MASQUERADE;
- real Windows LAN traffic to `<protected-target-ip>` traversing
  `<gateway-lan-ip> -> 172.20.130.5 -> <lan-router-ip> -> <protected-target-ip>`.

The same target previously went directly through `<lan-router-ip>`; after installing the
test route through `<gateway-lan-ip>`, reachability remained intact and the trace visibly
followed the intended VPN gateway path.

External CLI boundary forms are now to be manually validated on the target Debian before
being encoded in the subprocess adapter; this rule was applied before the RC2.5.1 retry.

EXP-003 is recorded in `design/vpn-gateway-experiments.md`.

Independent technical review: [`RC2.5.1-2026-11-08-review.md`](design/reviews/RC2.5.1-2026-11-08-review.md).
The review now includes maintainer disposition: read-before-write forwarding fixes are
accepted for RC2.5.2; moving OWNED commit after forwarding and a pseudo-atomic combined
snapshot API are rejected; route metric-collision handling requires a target experiment
before any validation rule is added.

Next order: RC2.5.2 forwarding read-before-write correction, then EXP-004 graceful
shutdown/cleanup + up/down/up idempotency. Fault injection, systemd safety-net behavior and
runtime self-healing remain intentionally deferred.

## 2026-11-07 — RC2.5.1 Debian iptables-save compatibility fix

The first real foreground bootstrap on Debian 13.7 / iptables-nft 1.8.11 failed during
config-independent startup cleanup before any gateway resources were materialized:

```text
iptables-save: invalid option -- 'w'
```

The RC2.5 subprocess adapter incorrectly assumed that `iptables-save` accepted the same
`-w/--wait` option as `iptables-restore`.

Correction:

- `iptables-save -t filter` and `iptables-save -t nat` are now invoked without `-w`;
- `iptables-restore -w N --noflush` retains bounded xtables lock waiting;
- the kernel-adapter regression test now asserts the Debian 13-compatible argv exactly.

Architecture remains RC2.4.1; implementation version is RC2.5.1.

## 2026-11-07 — RC2.5 happy-path bootstrap

Implementation RC2.5 completes the first executable happy-path gateway while retaining
architecture RC2.4.1.

Implemented:

- config-independent marker cleanup before config load and on graceful stop;
- real `net.ipv4.ip_forward` procfs adapter;
- memory-only `iptables-save` / `iptables-restore --noflush` adapter with bounded lock wait;
- fixed INPUT/FORWARD/NAT policy materialization and verification;
- daemon jumps inserted as a deterministic prefix ahead of foreign/UFW rules;
- static MASQUERADE for every managed VPN egress;
- initial route plan apply with missing BLACKHOLE guards first;
- fresh exact route verification and OWNED commit only after successful verify;
- `ip_forward=1` only after firewall and route verification;
- signal-only happy-path RUN loop until SIGTERM/SIGINT, followed by cleanup.

Runtime firewall repair, periodic reconciliation and Netlink self-healing remain intentionally
deferred. External drift during RC2.5 testing requires a service restart.

Regression:

```text
Config/security: 22/22 PASS
Value/profile:    7/7 PASS
Route planning:  14/14 PASS
Kernel adapter:  17/17 PASS
Bootstrap:         7/7 PASS
Total:            67/67 PASS

py_compile: PASS
--version:  PASS (RC2.5)
--help:     PASS
--check-config: PASS
```

The RC2.5 firewall comparator was also checked against the real Debian 13 canonical
`iptables-save` snapshot retained from EXP-001 and classified it as `SAFE`.

Next milestone: run RC2.5 in the foreground on the sterile Debian 13 gateway and validate
real forwarding through the already-established VPN interface before adding runtime
self-healing.

## 2026-11-07 — EXP-002A confirmed

EXP-002A passed against the corrected RC2.4.1 adapter:

```text
empty0 = frozenset()
p2p0   = frozenset({IPv4Address('172.20.140.1')})
EXP-002A OVERALL=PASS
```

This confirms the live Debian 13 / iproute2 address-inventory contract after the EXP-002
correction. The route/address kernel boundary is now considered validated; the next
implementation block is `_apply_plan()` / `_verify_plan()`.

## 2026-11-07 — RC2.4.1 EXP-002 correction

EXP-002 live smoke found one real mismatch in the RC2.4 address-inventory contract.

- `ip -j -4 addr show` omitted an existing interface with no IPv4 address;
- adapter changed to `ip -j addr show` and filters only `family == "inet"` in Python;
- numeric route types emitted by `ip -j -N` (`6/7/8/9`) were confirmed and were already
  accepted by the parser;
- P2P local address handling through `addr_info[].local` was confirmed;
- EXP-002 is recorded as FAIL with one actionable finding; EXP-002A is pending to validate
  the corrected adapter directly.

Regression after the correction:

```text
Config/security: 22/22 PASS
Value/profile:    7/7 PASS
Route planning:  14/14 PASS
Kernel adapter:  13/13 PASS
Total:           56/56 PASS

py_compile: PASS
--version:  PASS (RC2.4.1)
```

## 2026-11-07 — RC2.4 kernel route adapter

Реализован реальный iproute2 boundary для route/address части `SubprocessKernelInterface`.

### Route inventory

- используется `ip -j -N -4 route show table main`;
- `default` нормализуется в `0.0.0.0/0`;
- bare host destination нормализуется в `/32`;
- protocol IDs читаются численно благодаря `-N`;
- отсутствующий RTPROT_BOOT нормализуется в `proto=3`;
- поддерживаются UNICAST/BLACKHOLE/UNREACHABLE/PROHIBIT/THROW;
- `onlink` переносится из JSON flags;
- multipath/nexthop-group/structured-via routes не пропускаются молча и дают `KernelError`.

### Route mutations

Реализованы:

```text
add_route()
delete_route()
replace_route()
```

Команды явно задают IPv4 `table main`, route type, numeric protocol и остальные поля
`RouteSpec`. `proto=None` считается нематериализуемым состоянием и не подменяется
iproute2 default.

### Interface IPv4 inventory

Реализован `list_interface_ipv4()` через `ip -j -4 addr show`:

- используется `addr_info[].local`;
- peer/broadcast fields не влияют на readiness;
- interface без IPv4 возвращается с пустым `frozenset`.

### Tests

Добавлено 12 kernel-adapter unit tests.

Ожидаемый regression set:

```text
Config/security: 22/22 PASS
Value/profile:    7/7 PASS
Route planning:  14/14 PASS
Kernel adapter:  12/12 PASS
Total:           55/55 PASS

py_compile: PASS
--version:  PASS (RC2.4)
--help:     PASS
```

Следующий шаг — live smoke на Debian 13 с реальным `iproute2`, после чего можно
реализовывать `_apply_plan()` и `_verify_plan()`.

## 2026-11-07 — repository state synchronization

Repository metadata synchronized with the actual RC2.3 development state:

- changelog switched to newest-first order;
- daemon top-level description synchronized from RC2.2 to RC2.3;
- accidentally committed Python bytecode removed;
- `.gitignore` now excludes `__pycache__/` and `*.py[cod]`.

No functional daemon behavior changed in this commit.

## 2026-11-07 — RC2.3 route reconciliation planning

Реализован pure route-planning layer поверх одного immutable ACTUAL/DESIRED snapshot.

### `_derive_desired_routes()`

- ready profile -> BLACKHOLE + UNICAST;
- not-ready profile -> только BLACKHOLE;
- DESIRED вычисляется один раз на reconciliation pass;
- полученный snapshot используется далее без повторного вычисления readiness.

### `_build_plan()`

План строится по ACTUAL + DESIRED + process-local OWNED:

- missing desired -> add;
- desired + actual + owned -> keep;
- desired + actual + not owned -> authoritative canonicalization;
- competing exact foreign route -> delete;
- owned non-desired exact route -> delete;
- more-/less-specific routes не изменяются.

### Explicit replace operation

Обнаружен архитектурный пробел в прежней модели:

```text
ReconciliationPlan(adds, deletes)
```

не мог корректно представить состояние:

```text
actual ∩ desired
но RouteSpec не OWNED текущим процессом
```

Одновременный add+delete одного и того же `RouteSpec` противоречил invariants самого plan.

Поэтому `ReconciliationPlan` расширен до:

```text
route_adds
route_deletes
route_replaces
```

`route_replaces` является явной authoritative canonicalization operation, а не silent adoption.

В `KernelInterface` добавлен соответствующий contract:

```text
replace_route(RouteSpec)
```

Ownership после replace всё равно появляется только после успешного verify/commit.

### `_validate_plan()`

Реализованы safety checks:

- add/delete/replace sets попарно disjoint;
- add разрешён только для current DESIRED route, отсутствующего в ACTUAL;
- replace разрешён только для current DESIRED route, присутствующего в ACTUAL и отсутствующего в OWNED;
- foreign delete допустим только внутри authoritative exact protected-prefix scope;
- owned non-desired delete должен иметь ownership justification;
- `proto kernel` нельзя delete или replace;
- exact protected prefix, совпадающий с connected `proto kernel` route, является fatal plan conflict;
- incomplete DESIRED snapshot запрещён;
- duplicate exact resource claims между managed profiles запрещены defensively.

### `_routes_for_profile()`

Related route set включает:

- exact protected-prefix routes;
- competing exact routes;
- more-specific overlaps;
- less-specific overlaps.

Default route `0.0.0.0/0` из overlap diagnostics исключается.

### Tests

После этого этапа ожидаемый regression set:

```text
Config/security: 22/22 PASS
Value/profile:    7/7 PASS
Route planning:  14/14 PASS
Total:           43/43 PASS

py_compile: PASS
--version:  PASS
--help:     PASS
```

### Следующий блок

Следующий implementation milestone — реальный route kernel adapter:

```text
ip -j route
ip -j addr
ip route add
ip route del
ip route replace
```

После него должны быть реализованы:

```text
_apply_plan()
_verify_plan()
```

После этого route reconciliation впервые сможет работать с реальным kernel state,
а не только с pure-model snapshots.

---

## 2026-11-07 — стартовая точка журнала

На момент начала ведения журнала в реализации уже присутствовали следующие блоки.

### Configuration

Реализован `ConfigLoader` для `/etc/vpn-gateway/vpn-gateway.toml`.

Основные свойства:

- secure open конфигурации с `O_NOFOLLOW`;
- проверка final path component через `lstat`;
- повторная проверка реально открытого объекта через `fstat`;
- config file и parent directory должны принадлежать root и не быть writable для group/other;
- runtime загружает и валидирует только profiles из `managed_vpns`;
- malformed unmanaged profile не блокирует normal startup;
- `--check-config` выполняет полный offline lint всего catalog:
  - managed errors -> ERROR;
  - unmanaged invalid definitions/conflicts -> WARNING;
  - допустимые особые состояния, например `peers=[]`, -> NOTE;
- case-insensitive разрешение profile IDs;
- нормализация duplicate set-like values;
- проверка конфликтов managed interfaces, protected routes и VPN transport networks;
- runtime config преобразуется в typed immutable representation.

### Typed route/profile model

Реализованы базовые typed value objects:

- `RouteSpec`;
- `RouteType`;
- lifecycle/state/reason enums;
- immutable reconciliation-related value objects.

`VpnProfile` уже умеет строить `CONFIGURED` route set:

- BLACKHOLE guard для каждого protected prefix;
- peer UNICAST routes;
- peer metrics `10, 20, ...` в порядке `peers`;
- при `peers=[]` остаются только BLACKHOLE guards.

Также реализован process-local `OWNED` state:

- ACTUAL kernel state сам по себе не означает ownership;
- OWNED заменяется только после успешного verify;
- replacement выполняется atomically;
- входной route set копируется defensively.

### Daemon skeleton

Уже присутствуют:

- lifecycle/state machinery;
- managed profile registry;
- readiness helper по наличию interface и ожидаемого local IPv4 address;
- `effective_sources()`;
- guards, требующие полный result mapping ровно по всем managed profiles;
- `_commit_owned()` с проверкой полного mapping до первой mutation;
- fixed firewall/NAT, cleanup, runtime reconciliation и Netlink contracts/skeletons.

Большая часть firewall/NAT, cleanup, event loop и route apply/verify на этой точке ещё
оставалась implementation TODO.

### Kernel abstraction

Определён `KernelInterface` и subprocess-based implementation skeleton.

В abstraction предусмотрены операции для:

- route inventory;
- route mutation;
- interface IPv4 inventory;
- `net.ipv4.ip_forward`;
- `iptables-save`;
- `iptables-restore`.

Конкретная route materialization на этой точке ещё не реализована.
