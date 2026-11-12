# NG1 audit — dead artifacts, unnecessary complexity, experiment consistency and unresolved ambiguity

Date: 2026-11-12

Role: internal whole-project expert audit under CONTINUOUS-DEVELOPMENT.md.

## Scope

Reviewed the current first-production NG1 Python baseline plus the proposed future
DeviceManager availability slice, specifically looking for:

- unused concepts, variables, functions, modules and tests;
- unjustified complexity or duplicated ownership;
- contradictions with completed experiments;
- unresolved ambiguities that would make the next implementation step unsafe or
  misleading.

The completed first-production source baseline remains functionally clean. Most findings
below concern cleanup of historical scaffolding or prerequisites for future availability
work.

---

## A. Unused or legacy artifacts

### A1 — legacy iptables implementation still ships inside the production package

Severity: **MEDIUM / architecture hygiene**

The production runtime is nft-only, but the installed `rou/` package still contains:

- `firewall_state.py`;
- `firewall_kernel.py`;
- `nat_state.py`;
- `nat_kernel.py`.

These modules are no longer imported by Planner/runtime. They exist solely for regression
tests.

`nat_state.py` additionally contains historical/test-only abstractions:

- `NatPolicyBlocked`;
- `NatProvider`;
- `UnresolvedNatProvider`;
- `ExplicitNoNatProvider`;
- `ExperimentalMasqueradeAllBoundProvider`.

This contradicts the intended statement "legacy iptables remains regression/historical
evidence only": the code is still physically installed as production-package surface.

It also duplicates policy materialization. Future firewall changes would have to update an
obsolete iptables semantic implementation merely to keep historical tests green.

**Recommendation**

Move any evidence worth retaining under a test-only/archive namespace, for example
`tests/legacy_iptables/`.

Do not install it with `rou/`.

Reduce legacy tests to the specific historical properties still worth regression-testing;
do not maintain a second full semantic firewall/NAT compiler.

### A2 — broad package-level `rou.__init__` facade has no repository consumer

Severity: **LOW / API surface**

All project code and tests import concrete modules such as `rou.planner`,
`rou.domain`, etc. No current repository consumer imports the re-export facade.

The facade creates a pseudo-public API that must be kept synchronized and makes future Rust
module boundaries less explicit.

**Recommendation**

Reduce `rou/__init__.py` to package metadata/docstring unless an external Python-library
API is intentionally declared.

### A3 — `classify_device_to_host_profile()` is test-only despite claiming diagnostic use

Severity: **LOW**

The function is exported and documented as useful for diagnostics/status, but production
status does not call it. Runtime firewall materialization implements the same semantics
through ordered nft rules.

Its only current consumers are unit tests and the unused package facade.

**Recommendation**

Remove it and test Device->host classification through the actual firewall intent/nft
projection, unless a concrete diagnostic feature is added that uses it.

### A4 — `observe_nft_generation_refs()` is unused

Severity: **LOW**

The production verifier performs JSON generation-marker observation through
`observe_nft_state()`. The standalone helper has no production or test consumer.

**Recommendation:** remove it.

### A5 — legacy semantic tests duplicate the production nft test matrix

Severity: **LOW/MEDIUM maintenance**

`test_firewall_state.py`, `test_firewall_kernel.py`, `test_nat_state.py` and
`integration_firewall_roundtrip.py` validate a backend that no longer defines production
semantics. Several tests duplicate INPUT/FORWARD/OUTPUT/NAT policy already covered by
nft tests.

**Recommendation**

Keep only narrow historical backend/canonicalization evidence if desired. Do not maintain
parallel semantic-policy test suites.

---

## B. Unnecessary complexity / ownership duplication

### B1 — `rou up` prepares the instance twice

Severity: **MEDIUM lifecycle simplification**

Current `cmd_up()` calls `ensure_instance()` directly and then starts
`rouvpn@.service`.

The unit itself has:

    ExecStartPre=/usr/local/sbin/rou prepare %i

and `rou prepare` calls the same `ensure_instance()`.

The systemd pre-start hook is required anyway so an enabled unit can recreate its appliance
after reboot. Therefore direct CLI preparation duplicates lifecycle ownership.

**Recommendation**

Make systemd/ExecStartPre the single creation/preparation owner for `rou up`:

    rou up -> enable/start unit -> ExecStartPre prepare -> runtime -> verified status

Rollback remains stop-proof before teardown.

### B2 — internal service hooks are exposed as ordinary administrative CLI commands

Severity: **LOW/MEDIUM product surface**

Architecture defines the administrative surface around `up/down/show` (plus useful
`check`), while implementation exposes:

- `prepare`;
- `contain`;
- `run`.

These are systemd implementation hooks and are easy to misuse manually.

**Recommendation**

Mark them internal/hidden or move them behind an internal command namespace. Keep the
stable operator surface small.

Because this changes visible CLI behavior, exact presentation can be agreed with the
maintainer before cleanup.

### B3 — the normative architecture document carries too much historical implementation detail

Severity: **LOW documentation complexity**

Sections 19–21 mix current architecture with publication evidence, ROU-v0 implementation
details and RC2/RC3 migration history. Section numbering also contains a hierarchy glitch
(`## 19.1` adjacent to `## 19`).

The material is valuable evidence, but keeping it inside the normative architecture makes
it harder to distinguish current contract from provenance.

**Recommendation**

Move historical/prototype/evidence narrative to a companion history/evidence document.
Keep the normative architecture focused on current model, invariants and explicit future
boundaries.

### B4 — README duplicates the DeviceManager/UNAVAILABLE deferral

Severity: **LOW**

The deferred list states the positive UNAVAILABLE trigger/DeviceManager deferral twice in
slightly different wording.

**Recommendation:** collapse to one entry.

---

## C. Experiment/process inconsistencies

### C1 — EXP-020 remains in permanent core CI although EXP-019 was correctly removed

Severity: **MEDIUM maintenance / CI stability**

The EXP-019 review explicitly concluded that a future-only availability experiment should
not permanently gate the completed ROU core CI.

EXP-020 has the same status, but the core workflow still:

- installs `ocserv openconnect openssl`;
- executes EXP-020 on every kernel-integration run.

This is inconsistent and adds unrelated external packages/process behavior to every core
validation.

**Recommendation**

Preserve EXP-020 harness/results as evidence, remove it from permanent core CI, and remove
those packages from the core job unless another test needs them.

When DeviceManager availability relies on this behavior, add a focused permanent
DeviceManager integration test.

### C2 — code-cycle branches do not currently trigger the NG1 workflow

Severity: **MEDIUM process/tooling**

`.github/workflows/ng1-python.yml` runs on:

- push to `main`;
- pull requests targeting `main`.

A standalone `code-cycle-*` branch is externally observable as required by
CONTINUOUS-DEVELOPMENT.md, but does not automatically run CI.

This does not violate the per-commit visibility rule, but it leaves no direct mechanism to
close a code review unit with branch-local CI evidence.

**Recommendation**

Add an explicit review-unit CI mechanism for code-cycle branches. Prefer a deliberate
trigger rather than necessarily running the expensive privileged suite on every commit.
For example:

- rootless validation on every `code-cycle-*` push;
- full privileged validation on an explicit review-unit checkpoint trigger/PR.

The exact GitHub workflow mechanism is implementation/process policy, not network
architecture.

---

## D. Availability architecture gaps exposed by EXP-019/020

### D1 — normalized availability is not part of committed/durable Planner history

Severity: **HIGH / future transition correctness**

Architecture invariant 62 states normalized availability changes are incremental.

Current implementation explicitly cannot prove this yet:

- `DeviceBindingState` persists candidate order only;
- `JsonRuntimeStateStore` persists binding candidates and metrics, not availability;
- `binding_snapshot_from_state()` reconstructs historical availability as UNKNOWN unless
  a caller injects a separate mapping;
- `_project_committed_generation()` supplies no historical mapping;
- `assess_binding_lifecycle()` explicitly says future DeviceManager must persist enough
  availability history.

Therefore the first real AVAILABLE/UNAVAILABLE transition cannot simply be plugged into the
current provider API and still satisfy the promised incremental-generation proof.

**Recommendation**

Before activating a detector, make last **verified normalized availability** part of
committed Device state and durable state (state-version bump as required).

Persist only normalized availability needed for verified-generation reconstruction;
high-frequency probe counters/diagnostics need not be durable safety state.

On restart, seed detector normalization from the last committed state. A retired
`(ifname,ifindex)` generation never transfers state to a different identity.

### D2 — current `AvailabilityProvider(snapshot)` API is unsuitable for active probes

Severity: **HIGH / deterministic planning**

`compile_planner_projection()` invokes the provider as if it were a pure function.

Planner can build more than one projection during a single reconcile (for example initial
and closed-barrier projections). If the provider performs a live probe, desired state can
change because time/probe execution changed, not because the observed kernel generation
changed.

This violates the intended deterministic observe -> project -> apply model.

**Recommendation**

Active probing must run asynchronously outside Planner.

Planner receives one immutable normalized availability snapshot per reconcile. A provider
read is side-effect-free; it does not launch probes.

Availability state changes create a wakeup, after which Planner still collects fresh kernel
state and reads a fresh immutable availability snapshot.

### D3 — `rou show` cannot represent real availability with the current state model

Severity: **HIGH / observability correctness**

`inspect_runtime_status()` calls `compile_planner_projection(..., availability_provider=None)`.

Once production availability exists, this reconstructs bound paths as UNKNOWN. If the
runtime has correctly demoted an interface to UNAVAILABLE, a separate `rou show` process
would project the wrong desired routes and may report false policy drift.

This is the same underlying problem as D1 and must be fixed by making committed normalized
availability observable to status.

Detailed probe counters/health are a separate issue: current CLI has no RPC to the daemon.

**Recommendation**

- durable committed state carries normalized availability;
- `rou show` projects from that committed state;
- optional high-frequency detector diagnostics use a separate runtime status snapshot
  (`/run/vpn-gateway/...json`) or a later IPC mechanism rather than forcing every probe
  result into durable state.

### D4 — availability change needs a wakeup path

Severity: **MEDIUM/HIGH liveness**

Runtime currently waits on `IpMonitorWakeupSource` plus periodic audit.

An availability transition can occur with no link/address/route/rule event — exactly what
EXP-019 and EXP-020 proved.

Waiting only for the audit interval would make failover latency unrelated to the configured
probe policy.

**Recommendation**

Add an availability wakeup source/event and combine it with netlink wakeups. Event payloads
remain hints only; Planner still reads fresh immutable state.

### D5 — DeviceEngine / DeviceManager ownership is currently blurred

Severity: **MEDIUM architecture clarity**

Current architecture says:

- DeviceEngine normalizes Device-specific evidence into bound-interface availability;
- future DeviceManager changes actual Device state and is independent of DeviceEngine.

The availability proposal places process and availability providers "under DeviceManager".

That silently changes the ownership contract.

**Recommendation**

Introduce a neutral runtime component/boundary such as
`AvailabilitySupervisor/DeviceHealthProvider`:

- it owns probing/scheduling/raw evidence;
- DeviceEngine consumes its normalized immutable snapshot;
- DeviceManager may later compose/use the same provider but process lifecycle does not own
  availability semantics.

This preserves the existing Engine boundaries and keeps process management optional.

---

## E. Active-probe design ambiguities

### E1 — OUTPUT-only probe admission is insufficient

Severity: **HIGH / proposal correctness**

The availability proposal currently identifies only a narrow generated OUTPUT exception.

For ICMP:

- echo-request leaves through the Device interface;
- echo-reply returns as **ROU-local INPUT on the Device interface**.

Current invariant 72 deliberately gives Device interfaces no implicit ROU-local INPUT
access, so the reply will be dropped.

**Recommendation**

If ICMP is approved, generate a narrow generation-scoped pair:

- OUTPUT: concrete Device generation -> target/32, ICMP echo-request;
- INPUT: target/32 -> concrete Device generation, ICMP echo-reply with appropriate
  conntrack state.

Both rules carry the same numeric-ifindex generation verification markers as production
transit rules.

No broad Device-local INPUT or OUTPUT admission is introduced.

### E2 — probe evidence must not begin before its firewall path is verified

Severity: **HIGH / false-negative prevention**

A new binding initially has no probe-specific Device INPUT/OUTPUT admission.

If the detector begins counting failures before Planner has installed and verified those
rules, firewall policy itself generates false failure evidence and can drive the path to
UNAVAILABLE.

**Recommendation**

Use an explicit arming boundary:

1. binding appears as UNKNOWN;
2. Planner materializes and verifies generation-scoped probe admission;
3. only then is that generation eligible for failure/success counting;
4. detector event may subsequently change normalized availability.

Detector setup/permission failures are diagnostics, not path-failure samples.

### E3 — ICMP privilege requirements are not proven under the hardened unit

Severity: **HIGH / security boundary**

`rouvpn@.service` does not grant `CAP_NET_RAW`.

Whether the selected Linux/Python probe primitive can use ICMP under the current
capability/ping-socket environment is unresolved.

Silently adding `CAP_NET_RAW` would widen the service security boundary.

**Recommendation**

EXP-021 must test candidate generation-bound ICMP mechanisms under equivalent capability
constraints.

Prefer a mechanism that works without expanding the capability set. If CAP_NET_RAW is
actually required, treat that as a separate maintainer security decision.

### E4 — schema-version-1 availability extension conflicts with the frozen strict schema

Severity: **HIGH / user-visible contract**

Router schema v1 is strict, unknown-key rejecting and documented as normative. DeviceManager
configuration is explicitly listed outside schema v1.

Adding `[device.<id>.availability]` while retaining `schema_version=1` mutates the
meaning of an already frozen version.

**Recommendation**

Do not silently extend v1. Choose either:

- router schema v2 with availability fields; or
- a separate versioned Device-health/DeviceManager configuration surface.

This requires maintainer agreement.

### E5 — concrete probe routing/binding still needs kernel evidence

Severity: **HIGH / experiment gate**

EXP-019/020 prove the usefulness of an active probe but not the generic implementation
primitive.

EXP-021 must prove:

- egress is tied to the intended concrete generation;
- the probe cannot escape through an alternate Device/route;
- same-name/new-ifindex replacement does not transfer ownership;
- target route semantics work for both WG and OpenConnect shapes;
- bounded timeout behavior;
- narrow INPUT/OUTPUT rules work as intended.

### E6 — exact ifindex reuse is not covered by EXP-017

Severity: **HIGH / current generation-identity assumption**

EXP-017 proved that same-name/**new-ifindex** does not inherit numeric nft admission.

It did not prove what happens if Linux permits a deleted interface's exact ifindex to be
reused (naturally or via explicit index request).

The project currently treats `(ifname,ifindex)` as concrete generation identity and nft
rules intentionally match numeric ifindex. Exact reuse could invalidate that assumption.

**Recommendation**

Add an explicit phase to a kernel experiment (EXP-021 or a dedicated follow-up):

1. determine whether same ifindex can be deliberately/naturally reused in the target
   namespace/kernel;
2. if it can, test stale nft-rule matching and DeviceEngine identity behavior;
3. define the threat/model boundary or add an additional generation mechanism if required.

Do not assume EXP-017 already proved this case.

### E7 — proposal's AvailabilityKey is more complex than the current runtime API requires

Severity: **LOW/MEDIUM**

The proposal introduced:

    (device_name, ifname, ifindex)

while the current provider contract is keyed by globally unique `InterfaceIdentity`
(`ifname,ifindex`) and active Device selectors are disjoint.

Device ownership is already present in `BoundInterface`.

**Recommendation**

Keep the runtime snapshot keyed by `InterfaceIdentity` unless a concrete ambiguity
requires duplicating Device identity. Use typed BoundInterface context when target/config
lookup needs the Device.

---

## F. Smaller cleanup/documentation findings

### F1 — test module naming is misleading

`test_runtime.py` tests DeviceEngine/TrafficRuntimeState projection, while
`test_runtime_loop.py` actually tests the runtime loop.

**Recommendation:** rename the former to describe Device/traffic-state semantics.

### F2 — availability evidence text is asymmetric

Architecture §7.3 explicitly summarizes EXP-019 WireGuard evidence but does not yet mention
the matching EXP-020 OpenConnect result.

**Recommendation:** summarize both or reference one consolidated evidence statement.

### F3 — invariant 62 is ahead of implemented proof machinery

Invariant 62 normatively states availability changes are incremental. The desired end-state
is still correct, but current implementation cannot prove those transitions until D1 is
implemented.

**Recommendation**

Clarify that incremental availability is normative **once committed availability-generation
history exists**; do not imply the currently shipped no-detector runtime already exercises
that path.

---

# Overall assessment

The completed first-production routing/firewall/runtime core remains coherent and its
existing PASS evidence is not invalidated by this audit.

The largest avoidable complexity is historical iptables code/tests remaining inside the
production package and core CI.

The largest future-design issue is that availability is not merely a detector function:
making EXP-019/020 evidence operational requires a small supervised subsystem with:

- asynchronous raw probing;
- immutable normalized snapshots;
- committed normalized availability history;
- a Planner wakeup channel;
- generation-scoped verified probe firewall admission;
- read-only status integration.

Trying to implement this directly inside the current synchronous
`AvailabilityProvider(snapshot)` callback would be architecturally wrong.

---

# Cleanup that does not require maintainer policy decisions

Recommended autonomous cleanup queue:

1. remove/move legacy iptables implementation from installed `rou/` package;
2. reduce legacy semantic tests to narrow archived/regression evidence;
3. remove unused `observe_nft_generation_refs()`;
4. remove unused `classify_device_to_host_profile()` or only retain it if a real
   diagnostic consumer is introduced;
5. collapse unused package-level re-export facade;
6. remove EXP-020 from permanent core CI and its unique package dependencies;
7. add a deliberate code-cycle review-unit CI trigger;
8. remove duplicate README deferral and minor test/document naming drift;
9. simplify `rou up` to use systemd ExecStartPre as the single preparation owner;
10. split historical ROU-v0/RC2-3 material out of the normative architecture.

Items 9–10 should be performed as separate review units because they touch lifecycle/docs
broadly even though they do not require product-policy decisions.

---

# Updated maintainer decisions before availability implementation

The previous four-item list was incomplete. The required decisions are now:

## H1 — configuration surface/version

Choose:

- **H1-A (recommended):** router `schema_version=2` adds optional per-Device availability
  policy while v1 remains accepted/frozen;
- H1-B: separate versioned Device-health/DeviceManager configuration.

Do not mutate strict schema v1 silently.

## H2 — availability domain and target ownership

Recommended:

- one Device = one availability domain;
- explicit IPv4 probe target configured per Device;
- each bound interface generation of that Device is probed independently against that same
  target;
- if different binding groups need different targets, model them as different Devices.

## H3 — timing/hysteresis policy

Choose either:

- **H3-A (recommended):** explicit `interval`, `timeout`, `failures`, `successes`
  with no hidden production defaults;
- H3-B: named/default timing presets.

EXP-019/020 do not establish the numeric values.

## H4 — first probe protocol

Recommended: ICMP echo, subject to EXP-021 proving a safe implementation under current
service capabilities.

## H5 — local firewall exception

Approve or reject a narrow generated probe-only exception:

- generation-scoped OUTPUT echo-request to target/32;
- generation-scoped INPUT echo-reply from target/32;
- no general local Device INPUT/OUTPUT access.

This is a deliberate change to invariants 72/73 and therefore requires explicit agreement.

## H6 — capability policy

Recommended decision now:

- **do not grant CAP_NET_RAW by design**;
- let EXP-021 first prove whether a capability-free/ping-socket implementation works under
  the hardened unit;
- if it does not, return for explicit approval before widening the service capability set.

## H7 — availability component ownership

Recommended:

- availability probing/scheduling lives in an independent
  `AvailabilitySupervisor/DeviceHealthProvider`;
- DeviceEngine consumes normalized snapshots;
- DeviceManager process lifecycle remains separately composable.

This keeps the current Engine contract intact rather than making health a side effect of
process management.

## H8 — restart semantics for normalized availability

Recommended:

- persist last **verified normalized availability** with Planner durable state;
- on daemon restart seed the same interface generation from that committed state;
- reset probe counters/health timers, but do not automatically turn committed UNAVAILABLE
  into UNKNOWN/normal routing;
- valid new evidence drives the next transition.

This is primarily internal safety semantics but should be confirmed because it affects
post-restart failover behavior.

---

# Experiment update

If H1–H8 are accepted sufficiently to proceed, EXP-021 should be expanded before detector
implementation to cover:

1. ICMP capability behavior under service-equivalent restrictions;
2. concrete-interface/generation binding;
3. no alternate-route escape;
4. verified INPUT+OUTPUT probe admission;
5. detector arming only after policy verification;
6. same-name/new-ifindex replacement;
7. explicit same-ifindex reuse attempt and stale nft-rule behavior;
8. WG-shaped and OpenConnect-shaped target routing.

Only after EXP-021 PASS should production availability code be implemented.
