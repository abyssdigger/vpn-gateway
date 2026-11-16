# Production implementation review 20 — Draft 5 safety correction whole-code review

Role: external expert review with Linux networking-stack depth, security/fail-closed
focus, and Python-to-Rust migration experience.

## Scope

Reviewed the complete current NG1 production Python path after the 2026-11-12 external
architecture review:

- schema/domain validation;
- DeviceEngine / TrafficEngine projections;
- routing/RPDB allocation, mutation and verification;
- firewall/NAT projection and live serialization verification;
- Planner transition classification and commit lifecycle;
- namespace prerequisites;
- instance lifecycle and durable state;
- publications and runtime supervision;
- read-only status;
- CLI/systemd/deployment surfaces;
- privileged disposable-netns evidence;
- current Draft 5 invariants and experiment gates.

## Findings and dispositions

### F1 — remote-initiated return steering was unsafe for capacity > 1

A host reply to a Device-initiated flow is destination-dispatched and may choose a
different lower-metric Device/interface.

Severity: high.

Disposition: fixed for schema version 1. INBOUND/BIDIRECTIONAL now require active
capacity exactly 1. Capacity > 1 is blocked behind EXP-014 flow-pinning evidence.

### F2 — remote-initiated host-side trust boundary was incomplete

Profile remote prefixes constrain the source side, not the reachable host destination.

Severity: high.

Disposition: fixed. INBOUND/BIDIRECTIONAL additionally require every active referenced
Device to have a traffic envelope with terminal default=drop. The administrator must
explicitly allow host destinations/protocols/ports.

### F3 — ROU-local INPUT/OUTPUT were fail-open by default

The production filter initially kept INPUT/OUTPUT ACCEPT while only FORWARD was owned
fail-closed.

Severity: high.

Disposition: fixed. INPUT/FORWARD/OUTPUT are all default-DROP. INPUT admits loopback,
host0 return traffic and host0 NEW only to concrete internal publication endpoints.
OUTPUT admits loopback and locally generated traffic only through host0. No Device
interface receives implicit local INPUT/OUTPUT admission. Bootstrap installs this filter
before runtime/publications.

### F4 — broad global barrier on ordinary binding lifecycle was unnecessary

Any desired/current mismatch originally forced global ip_forward=0.

Severity: medium/high availability and architectural consistency.

Disposition: fixed with a proof-oriented transition classifier. Proven ordinary binding
lifecycle repairs while forwarding remains open; structural/unknown drift and unverified
recovery retain the global barrier.

### F5 — first incremental design used full Profile-table flush and was unsafe with overlaps

A more-specific Profile table temporarily emptied by flush could cause RPDB lookup to
continue to a later broader Profile, crossing a policy boundary.

Severity: high.

Disposition: fixed. Lifecycle route mutation is an exact semantic diff. Every Profile
table's terminal blackhole must already exist and is never removed during lifecycle
repair. The live overlapping-Profile integration test proves no fall-through to the
broader Profile.

### F6 — owned RPDB verification covered only current terminal priority

The mutator owns priorities 1..32765, but verifier/classifier initially ignored foreign
rules above the current terminal host0 priority.

Severity: high drift-detection gap.

Disposition: fixed. Verification and transition classification cover the full owned RPDB
window.

### F7 — same-name/new-ifindex cannot be strictly isolated by legacy iptables name matches

NG1 identity is (ifname,ifindex), but iptables-legacy -i/-o matches the reusable name.
A replacement that reuses the name before observation may temporarily inherit old rules.

Severity: high for strict dynamic-generation isolation.

Disposition: not guessed around. Same-name/new-ifindex observed transitions are structural
and use the barrier, but that does not eliminate the pre-observation window. EXP-017 is a
formal production gate for an ifindex-aware backend (preferred nftables numeric
meta iif/oif or equivalent) or an equally strong DeviceManager serialization proof.

This is an explicit external blocker, not an unimplemented ordinary function.

### F8 — persistent shadow fallback trigger status was ambiguous

The route mechanism exists while normal production code has no positive UNAVAILABLE
detector.

Severity: documentation/ownership.

Disposition: clarified. The mechanism intentionally ships now. The positive trigger is
deliberately deferred to future DeviceManager/Device-specific health detection. EXP-016
must fix fib_multipath_hash_policy before such a trigger makes ECMP fallback effective.

### F9 — iptables verifier compared fragile text serialization

Live iptables-save reordered chain serialization/match options/state lists and emitted
rule counters, causing false drift.

Severity: medium/high verifier correctness.

Disposition: fixed with semantic normalization: table/chain structure, per-chain rule
order, counters and canonical conntrack-state ordering are normalized while preserving
semantically significant intra-chain order.

### F10 — local publication address was dropped between runtime and Planner

Runtime accepted the ROU-local publication address but initially failed to pass it into
reconcile_once, causing publication INPUT projection to fail.

Severity: high functional wiring bug.

Disposition: fixed and regression-tested through runtime-layer argument propagation.

### F11 — runtime-state filesystem trust was incomplete

Direct parent/file checks did not reject symlink ancestors above the direct parent, and
instance path validation permitted lexical parent traversal.

Severity: medium/high integrity.

Disposition: fixed. Every existing ancestor is lstat-checked against symlinks; configured
absolute paths reject '..'; state_file is constrained below /var/lib/vpn-gateway.

### F12 — boot/deployment lifecycle needed persistent service semantics

The initial CLI shape did not fully define reboot recovery, safe prepare, or persistent
enable/disable behavior.

Severity: medium production-operability.

Disposition: fixed. systemd ExecStartPre uses strict fail-closed prepare; ExecStopPost
contains forwarding; rou up enables+starts, rou down disables+stops then proves inactive
before teardown. Safe bootstrap drift is repaired only after closing forwarding; partial
appliance ownership is never adopted.

### F13 — read-only operational status was too shallow

Earlier show output reported appliance shape/counts but did not prove current kernel state
matches policy.

Severity: medium observability.

Disposition: fixed. RuntimeStatus reuses production projectors and kernel/filter/NAT/
prerequisite verifiers to report desired-vs-live policy status and bound/over-quota state.

### F14 — MTU/MSS and ECMP hash behavior must not be guessed

Severity: production-readiness evidence.

Disposition: EXP-015 (real TCP MTU/MSS) and EXP-016 (fib_multipath_hash_policy) are
prepared gates. They do not block control-plane implementation but block the corresponding
production claims.

### F15 — normalized configuration invariants initially depended too much on TOML parser

Programmatic ActiveConfig could bypass cross-object constraints.

Severity: medium API/domain integrity.

Disposition: fixed with public validate_active_config invoked by Planner and status.

### F16 — required Engine DEBUG decision trail is still incomplete

Draft 5 §16 requires DEBUG logging for PlannerEngine, DeviceEngine and TrafficEngine:
inputs, projected configuration, previous committed state, decision path, desired result,
apply/verification result and commit outcome, excluding secrets.

Current logging is strongest in runtime/publication failure paths but does not yet provide
the required structured decision trail for all three Engines.

Severity: medium maintainability/operations; not a kernel-safety blocker.

Recommendation: add compact structured DEBUG records with stable
planner-/device-/traffic- subject prefixes at the pure projection and Planner transition
boundaries. Log identifiers/counts/state transitions rather than raw configuration blobs,
credentials or subprocess argv.

## Evidence

At commit 958aec8dff27d1042755883626ff74e0480de54c:

- rootless NG1 Python validation: PASS;
- privileged disposable-netns kernel-integration: PASS;
- RC3 regression workflow: PASS.

Later deployment/status hardening is covered by additional rootless and kernel-integration
tests and must return to green before final baseline acceptance.

## Rust-alignment assessment

The implementation is increasingly Rust-compatible:

- typed immutable normalized values;
- explicit Result-like error boundaries;
- pure projection separated from mutation;
- backend/provider traits represented by Python Protocols;
- durable state has explicit versioned primitive schema;
- transition classifier is a pure decision function;
- command execution is argv-based, never shell-based;
- ownership and lifecycle are RAII-shaped.

The largest future backend change is EXP-017 ifindex-aware firewall materialization; the
policy/domain interfaces need not change for an nftables/Rust backend.

## Verdict

Architecture and corrected implementation are sound in the implemented/unblocked scope.

One unblocked recommendation remains: **F16 Engine DEBUG decision logging**.

External gates EXP-014/015/016/017 remain explicit and must not be silently bypassed.
After F16 and a fresh green CI run, perform one final whole-scope review; no additional
ordinary implementation change is recommended by this review.
