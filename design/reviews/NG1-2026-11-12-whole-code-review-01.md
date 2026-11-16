# NG1 whole-code review after Draft 5 safety correction

Date: 2026-11-12

Reviewer role: external expert analyst with Linux/network-stack depth, Python-to-Rust
migration experience, aggressive edge-case review and whole-project consistency scope.

## Scope

Reviewed the current production Python package as one control plane rather than isolated
modules:

- normalized config/domain;
- DeviceEngine/TrafficState/metrics;
- routing/RPDB desired state and mutation;
- transition classification;
- firewall/NAT desired state;
- nftables candidate backend;
- Planner/runtime/state persistence;
- lifecycle/publications/status/CLI;
- current privileged integration/experiment evidence.

## Findings

### F1 — production Planner still executes legacy iptables while nftables is the approved backend direction

Severity: **HIGH / architectural consistency**

The repository already contains an ifindex-aware nftables materializer and EXP-017 proves
that numeric iif/oif rules do not transfer admission to a same-name/new-ifindex generation.
However PlannerEngine still compiles, observes, applies and verifies
`FirewallDesiredState` / `NatDesiredState` through iptables-legacy.

Consequences:

- production behavior does not yet satisfy the intended generation-aware firewall contract;
- `transition.py` still contains a backend-specific same-name/new-ifindex structural
  barrier solely because the active backend matches names;
- two complete firewall/NAT semantics coexist and can drift.

Recommendation:

1. make nftables the only production Planner policy backend;
2. retain legacy iptables modules only as regression/historical evidence until removal;
3. make transition classification backend-neutral over canonical policy generations;
4. remove the name-backend same-name/new-ifindex structural special case once nft
   verification is generation-safe.

### F2 — nft textual verification can collapse interface generations if live ifindex is rendered as a name

Severity: **HIGH / verification integrity**

`normalize_nft_list()` currently rewrites rendered interface names back to ifindex using
the desired state's `(ifindex, ifname)` set. When an old generation disappears and a new
interface reuses the same name, nft may render the new numeric ifindex as that name.
Normalizing the output using the *old* desired mapping can therefore falsely turn a new
generation into the old ifindex.

The kernel matching primitive itself is correct; the ambiguity is only in observation.

Recommendation:

- do not promote nft to production verification until observation preserves numeric
  generation identity independently of interface-name resolution;
- use nft JSON/netlink representation if it exposes numeric iface_index, or another
  experimentally proven observation form;
- EXP-017 is extended to capture the JSON representation after same-name/new-ifindex
  replacement.

Until resolved, the nft materializer remains implementation-ready but its verifier is
gated.

### F3 — Draft 5 remote-initiated safety corrections are present in code and should remain one invariant boundary

Severity: **resolved / verify coverage**

Current config validation already enforces:

- INBOUND/BIDIRECTIONAL active interface capacity == 1;
- every active Device referenced by such a Profile has a traffic envelope with terminal
  default DROP.

Current firewall generation already scopes ESTABLISHED/RELATED to concrete bound
Device-interface <-> host0 pairs and has INPUT/FORWARD/OUTPUT default DROP.

Recommendation: retain these as schema-v1 production constraints and ensure all direct
ActiveConfig construction paths call `validate_active_config()` before mutation/status
projection. Do not weaken the constraint while EXP-014 is pending.

### F4 — ordinary binding lifecycle classification is conceptually correct, but policy backend must be generation-aware before same-name replacement is incremental

Severity: **MEDIUM / transition correctness**

`compile_lifecycle_route_rebuild_plan()` correctly preserves terminal blackholes and
does not require a global forwarding barrier for proven normal add/remove lifecycle.
Structural/unknown drift still uses the barrier.

The current same-name/new-ifindex structural reason is not an architectural requirement;
it compensates for legacy name-based firewall materialization. Once production nft
observation is generation-safe, same-name/new-ifindex can be treated as ordinary
old-generation removal + fresh-generation addition, subject to normal fresh-state
verification.

### F5 — fib_multipath_hash_policy is observed but no production value is owned yet

Severity: **accepted gated behavior**

This is intentionally blocked on EXP-016. Current verifier only requires an observable
integer. That is acceptable while no real availability detector emits UNAVAILABLE.

Recommendation: do not make a DeviceManager availability detector operational before
EXP-016 selects and documents the production value; then add it to prerequisite writes and
exact verification.

### F6 — MTU/MSS policy remains correctly unresolved

Severity: **accepted gated behavior**

No clamp should be guessed. EXP-015 remains the production TCP signoff gate.

### F7 — deployment/runtime code is substantially implemented but should not be called complete until nft production migration and end-to-end disposable lifecycle pass

Severity: **MEDIUM / release completeness**

CLI, lifecycle, runtime locking, publication supervision, status projection and systemd
deployment artifacts exist. Their final production acceptance depends on:

- production Planner using nft;
- generation-safe nft verification;
- full disposable `rou up -> runtime -> binding churn -> repair -> rou down` integration;
- final whole-code review with no findings.

## Rust-alignment assessment

Strong overall:

- immutable normalized domain values;
- pure projection separated from command execution;
- typed transition/result/error objects;
- explicit provider/trait-shaped boundaries;
- durable state is versioned and validated;
- events are wakeups, not policy data.

The main Rust-migration risk is currently duplicated firewall backends rather than Python
language structure. Removing production duality is preferable before adding more product
surface.

## Verdict

The implementation is coherent enough to continue, but **F1 and F2 are blocking for
production backend acceptance**.

Proceed in this order:

1. finish EXP-017 observation proof;
2. implement generation-safe nft observation/verification;
3. migrate Planner/transition/status to nft production policy;
4. run rootless + privileged CI;
5. review/fix the migrated backend;
6. continue deployment/end-to-end integration.
