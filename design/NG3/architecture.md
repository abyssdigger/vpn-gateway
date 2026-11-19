# VPN-GATE NG3 — Architecture Report

**Status:** NG3 architecture, current Release 1 closure with executable reference slices  
**Cycle:** `ng3-design-cycle-20261116-primary-requirements-basis-40m`  
**Requirements:** `design/NG3/requirements.md`  
**Component model:** `design/component-model.md`

This document is an implementation report for accepted NG3 requirements.

It is not a source of new product semantics.

No NG2 component is inherited merely because it existed. Historical NG2 design may be used
as evidence that a mechanism is technically plausible or as a source of failure modes, but
every NG3 architectural element below must be justified again by NG3 requirement IDs.

## Current executable reference evidence

The architecture now has bounded executable reference slices under
`design/NG3/code/python/rou/`.

These slices are implementation/evidence for accepted contracts. They are **not** a claim
that the Release 1 daemon, Linux actuation layer or deployment lifecycle is complete.

Current trace:

| Architecture responsibility / contract | Executable reference | Review evidence |
| --- | --- | --- |
| ConfigurationAdapter structural + canonical Release-1 normalization | `domain.py`, `config.py`, `release1_config.py`, `port_bundle.py` | `NG3-2026-11-16-structural-config-code-review.md`, `NG3-2026-11-17-release1-config-grammar-rust-boundary-review.md`, `NG3-2026-11-17-port-bundle-correction-review.md`, `NG3-2026-11-18-sticky-reserve-reference-code-review.md` |
| authoritative VPNPathAdapter interface-identity observation boundary | `interface_identity.py`, `interface_inventory.py` | `NG3-2026-11-16-interface-inventory-code-review.md` |
| Linux VPNPathAdapter fresh managed-netns runtime collection | `linux_vpn_path_adapter.py` | `NG3-2026-11-18-linux-vpn-path-adapter-runtime-review.md` |
| shared current Device binding projection / stable logical slots | `binding.py` | `NG3-2026-11-16-device-binding-projection-code-review.md` |
| PayloadProfileRequest structural projection | `payload_profile.py` | `NG3-2026-11-16-payload-profile-request-code-review.md` |
| PayloadPolicyCalculator NEW-flow Profile classification | `profile_classification.py` | `NG3-2026-11-16-profile-classification-code-review.md` |
| PayloadTrafficManager bounded availability confirmation + Profile active-route state | `availability_confirmation.py`, `availability_routing_state.py`, `availability_manager.py` | `NG3-2026-11-16-availability-confirmation-code-review.md`, `NG3-2026-11-18-availability-routing-state-review.md` |
| AvailabilityPriorityCalculator effective-order transformation | `availability_priority.py` | `NG3-2026-11-16-availability-priority-code-review.md`, `NG3-2026-11-18-sticky-reserve-reference-code-review.md` |
| NetworkPolicyExecutor pure priority-transition planning primitive | `route_priority.py` | `NG3-2026-11-16-route-priority-planner-code-review.md` |
| NetworkPolicyExecutor re-observed partial-state priority convergence | `route_priority_convergence.py` | `NG3-2026-11-16-route-priority-convergence-code-review.md` |
| NetworkPolicyExecutor single-attempt observe/apply/re-observe contract | `route_priority_executor.py` | `NG3-2026-11-16-route-priority-executor-attempt-code-review.md` |
| NetworkPolicyAdapter/Executor owned route-key inventory projection | `route_priority_inventory.py` | `NG3-2026-11-16-route-priority-inventory-code-review.md` |
| NetworkPolicyExecutor bounded physical iproute2 priority backend | `iproute_priority_backend.py` | `NG3-2026-11-16-iproute-priority-backend-code-review.md` |
| Profile-level multi-domain priority coordinator | `route_priority_profile.py` | `NG3-2026-11-16-route-priority-profile-coordinator-review.md` |
| lower Adapter route-priority realization contract | `route_priority_realization.py` | `NG3-2026-11-16-route-priority-realization-contract-review.md` |
| shared lower network-policy deterministic allocation | `network_policy_layout.py` | `NG3-2026-11-16-network-policy-layout-allocator-review.md` |
| pure normalized availability-subject -> probe route/RPDB/local-policy projection | `probe_policy.py` | `NG3-2026-11-19-probe-policy-projection-review.md` |
| pure probe route/RPDB actual-vs-desired comparison | `probe_routing_compare.py` | `NG3-2026-11-19-probe-routing-comparison-review.md` |
| bounded fail-closed probe route/RPDB convergence | `probe_routing_plan.py`, `probe_routing_convergence.py`, `linux_probe_routing.py` | `NG3-2026-11-19-probe-routing-convergence-review.md` |
| probe route/RPDB mutation Driver with exact `oif` path discriminator | `linux_probe_routing.py` | `NG3-2026-11-19-probe-path-discriminator-broken-review.md`, `NG3-2026-11-19-probe-route-rpdb-mutation-review.md`, `EXP-065-result-20261119.md` |
| EXP-066-backed probe-local nft owner comparison/full-diff/Linux Driver | `probe_local_observation.py`, `probe_local_mutation.py`, `linux_probe_local.py`, composite nft owner | `NG3-2026-11-19-probe-local-nft-owner-review.md`, `EXP-066-result-20261119.md` |
| bounded current probe observation context / late-result rejection / technical-result mapping | `probe_runtime.py` | `NG3-2026-11-19-probe-observation-context-agent-review.md` |
| EXP-067-backed one-shot ICMP exit semantics with bound `-I <ifname>` path execution | `icmp_probe_driver.py` | `NG3-2026-11-19-probe-path-discriminator-broken-review.md`, `NG3-2026-11-19-icmp-probe-driver-review.md`, `EXP-067-result-20261119.md` |
| bounded availability observation tick + confirmation/effective-order composition | `availability_observation_tick.py`, `availability_manager.py` | `NG3-2026-11-19-availability-observation-tick-review.md`, `NG3-2026-11-19-availability-manager-effective-order-review.md` |
| availability effective-order -> existing make-before-break route-priority bridge | `availability_route_priority.py` | `NG3-2026-11-19-availability-route-priority-bridge-review.md` |
| bounded Linux probe-routing/readiness/observation/priority cycle | `linux_availability_cycle.py` | current continuous-availability cycle review |
| accepted NG3 Linux platform resource space | `linux_policy_platform.py` | `EXP-028-result-20261116.md` |
| semantic Profile/allocation -> route-key priority realization | `route_priority_domain_builder.py` | `NG3-2026-11-16-route-priority-domain-builder-review.md` |
| explicit direct-device VPN integration route realization | `direct_device_route.py` | `NG3-2026-11-16-direct-device-route-realizer-review.md` |
| complete payload route/RPDB desired-state projection | `payload_routing_desired.py` | `NG3-2026-11-16-payload-routing-desired-state-review.md` |
| strict whole-reserved route/RPDB structural observation | `structural_routing_inventory.py` | `NG3-2026-11-16-structural-routing-inventory-review.md`, `NG3-2026-11-19-probe-policy-projection-review.md` |
| pure payload actual-vs-desired structural comparison | `payload_routing_compare.py` | `NG3-2026-11-16-payload-routing-comparison-review.md` |
| EXP-048-backed structural route/RPDB mutation Driver | `linux_structural_routing.py` | `NG3-2026-11-16-cross-domain-structural-convergence-review.md`, `EXP-048-result-20261116.md` |
| exact-before-release cross-domain phase planner | `structural_policy_plan.py` | `NG3-2026-11-16-cross-domain-structural-convergence-review.md` |
| semantic Profile forward compiler | `payload_forward_compiler.py` | `NG3-2026-11-17-profile-forward-compiler-review.md` |
| multi-path Device firewall semantic compiler | `device_firewall_policy_compiler.py`, `device_firewall_compiler.py`, `linux_device_firewall.py` lower port-bundle rendering | `NG3-2026-11-17-device-firewall-policy-compiler-review.md`, `NG3-2026-11-17-port-bundle-correction-review.md`, `EXP-042-result-20261117-port-bundle-pass.md` |
| complete payload lower desired-state assembly | `payload_network_policy_desired.py` | `NG3-2026-11-17-payload-network-policy-desired-review.md` |
| guarded cross-domain structural Executor + Linux snapshot backend | `structural_policy_mutation.py`, `linux_structural_policy.py` | `NG3-2026-11-16-cross-domain-structural-convergence-review.md` |
| bounded complete structural transaction coordinator | `structural_policy_transaction.py` | `NG3-2026-11-16-structural-transaction-coordinator-review.md` |
| network-policy activation subassembly | `network_policy_activation.py` | `NG3-2026-11-17-network-policy-activation-review.md` |
| managed network-domain infrastructure lifecycle | `managed_network_domain.py` | `NG3-2026-11-17-managed-network-domain-lifecycle-review.md` |
| controller lifetime instance exclusion | `instance_lock.py` | `NG3-2026-11-17-controller-instance-lock-review.md` |
| bounded controller startup assembly | `controller_startup.py`, `managed_network_domain.py` preflight | `NG3-2026-11-17-controller-startup-review.md` |
| bounded controller stop / owned-domain cleanup | `controller_stop.py`, `managed_network_domain.py` teardown | `NG3-2026-11-17-controller-stop-cleanup-review.md` |
| bounded controller restart composition | `controller_restart.py` | `NG3-2026-11-17-controller-restart-review.md` |
| phase-bounded STARTING termination checkpoints | `controller_startup.py`, shared owned-domain cleanup in `controller_stop.py` | `NG3-2026-11-17-starting-termination-review.md` |
| managed-netns structural forwarding gate | `forwarding_gate.py`, `linux_forwarding_gate.py` | `NG3-2026-11-16-forwarding-gate-code-review.md`, `EXP-030-result-20261116.md` |
| nft table-level ownership observation | `nft_namespace_inventory.py` | `NG3-2026-11-16-nft-namespace-inventory-code-review.md`, `EXP-031-result-20261116.md` |
| invariant payload nft scaffold comparison | `nft_payload_scaffold.py` | `NG3-2026-11-16-payload-nft-scaffold-code-review.md`, `EXP-032-result-20261116.md` |
| guarded physical payload nft scaffold preparation | `nft_scaffold_executor.py`, `linux_nft_scaffold.py` | `NG3-2026-11-16-nft-scaffold-prepare-code-review.md` |
| normalized Device NAT intent -> payload masquerade desired projection | `device_policy.py`, `payload_nat_desired.py` | `NG3-2026-11-16-payload-nat-desired-code-review.md`, `EXP-033-result-20261116.md` |
| host-side Device server publication | `host_publication_policy.py`, `linux_host_publication.py`, alpha runtime composition | `NG3-2026-11-17-host-server-publication-dnat-review.md`, EXP-052, EXP-051 extension |
| host-boundary bootstrap/return policy projection | `host_boundary_policy.py`, `linux_host_boundary_policy.py` | EXP-053, current host-return-steering cycle review |
| managed-stack established-flow return affinity | `stack_return_affinity.py`, `linux_stack_return_affinity.py` | EXP-061, current stack-return-affinity cycle review |
| cross-contract pure structural integration | `tests/test_pure_structural_pipeline.py` | `NG3-2026-11-16-pure-structural-pipeline-integration-review.md` |

The executable reference implementation still stops before separately-gated runtime
boundaries:

- Profile ordinary-side `+snat` physical materialization;
- stable production packaging/version lifecycle and a stable external status API.

Live current-state presentation is no longer one of these gaps: the executable alpha publishes
the accepted `RuntimeStatusAgent` projection through its documented current-only JSON surface.
That alpha surface remains replaceable interface machinery rather than the final stable
Release-1 operator API.

The ordinary Release-1 Device/Profile grammar itself is no longer unresolved.

This mapping implements the traceability intent of `VPNG0007-R7.R6.R1` without promoting
reference code into new product semantics.

# 1. Architecture scope of this pass

**Implements:**
- `VPNG0001`
- `VPNG0002`
- `VPNG0003`
- `VPNG0004`
- `VPNG0005`
- `VPNG0006`
- `VPNG0007`
- `VPNG0001-R1`
- `VPNG0002-R2`
- `VPNG0003-R3`
- `VPNG0004-R4`
- `VPNG0005-R5`
- `VPNG0006-R6`
- `VPNG0007-R7`

The primary project requirements above are closed through the accepted derived requirement trees and the architecture traced below.

This pass attempts architecture only for the requirements that are already sufficiently
defined to justify concrete responsibilities:

- payload policy materialization;
- deterministic path preference;
- availability-driven priority adaptation;
- active availability observation;
- fail-closed network-policy application;
- local drift/retry behavior around owned network policy;
- current component-level state publication.

This architecture intentionally does **not** yet define implementation details that no
accepted requirement makes architectural semantics:

- automatic VPN-session provisioning/configuration, because `VPNG0001-R1.R3.C1` leaves that
  responsibility to the administrator in the first release;
- concrete per-integration administrator command sequences/documents;
- concrete CLI/API/status presentation formatting;
- concrete event-delivery transport;
- final process/package assembly topology where existing contracts do not require one;
- complete Linux route/table/nft/sysctl representation beyond the accepted safety and
  priority-transition mechanisms;
- WireGuard/OpenConnect-specific provisioning machinery;
- TCP/UDP/HTTP availability checks beyond the accepted first-release ICMP constraint;
- a universal event persistence/replay layer.

These omissions are deliberate implementation freedom, not unresolved requirement semantics.

## 1.1. Managed network isolation boundary ("стакан")

**Implements:**
- `VPNG0004-R4.R6`
- `VPNG0004-R4.R6.R1`
- `VPNG0004-R4.R6.R1.R1`
- `VPNG0004-R4.R6.R1.R2`
- `VPNG0004-R4.R6.R1.R3`
- `VPNG0004-R4.R6.R1.R4`
- `VPNG0004-R4.R2`
- `VPNG0004-R4.R4`
- `VPNG0005-R5.R1`
- `VPNG0005-R5.R4`
- `VPNG0007-R7.R3`
- `VPNG0007-R7.R3.R2`

NG3 selects an isolated managed network domain as the architectural boundary for the router
data plane.

For the Linux implementation direction, the minimal current realization is a dedicated
network namespace containing the VPN-GATE-owned virtual network environment.

The explicit host/domain boundary is realized by dedicated boundary links rather than by
using arbitrary host routes/interfaces as implicit product plumbing. For the current Linux
architecture, a dedicated veth-style link is the minimal default for each required
host/domain attachment because it gives one endpoint inside the managed namespace and one
explicit peer outside it without merging the two routing domains.

Inside this domain belong the network objects whose semantics are owned by VPN-GATE,
including:

- payload routing state;
- filtering/NAT state required by accepted policy;
- managed ingress/egress links;
- VPN data-plane adapters/endpoints used as VPN paths;
- probe data-plane state when probing a path requires it.

The managed-domain contract is:

- **ownership:** mutable routing/policy state used only by VPN-GATE lives inside the managed
  domain unless a boundary object is explicitly declared;
- **host boundary:** host connectivity enters through named/dedicated boundary endpoints,
  not through ambient host networking;
- **VPN path placement:** a VPN path's data-plane endpoint used by managed forwarding is
  present inside the managed domain;
- **observation before use:** runtime code verifies the endpoint is present in the expected
  domain before accepting it for managed forwarding;
- **identity:** logical path identity is bound to one verified current concrete endpoint
  through the accepted VPNPathAdapter/configuration contracts.

This closes the architectural shape of the managed domain while keeping concrete external
field names and protocol-specific endpoint discovery as implementation choices.

The host network namespace is outside this managed domain. Interaction with the host must
occur only through explicit boundary links/contracts.

The purpose of this boundary is not "use netns because NG1 used netns". It is to realize
`VPNG0004-R4.R6`: unrelated host network state must not become implicit product state or be
mutated as a side effect of internal routing changes.

The namespace is therefore an architecture choice. If another mechanism can later satisfy
the same isolation/ownership requirements more simply, the requirement does not protect the
namespace itself.

### 1.1.1. Managed network-domain bootstrap — executable Linux lower contract

**Implements:**
- `VPNG0004-R4.R6`;
- `VPNG0004-R4.R6.R1`;
- `VPNG0004-R4.R6.R1.R1`;
- `VPNG0004-R4.R6.R1.R2`;
- `VPNG0004-R4.R6.R1.R4`;
- `VPNG0005-R5.R1`;
- `VPNG0005-R5.R4`;
- `VPNG0007-R7.R1`;
- `VPNG0007-R7.R3.R1`.

The Linux bootstrap consumes an **already-normalized internal** infrastructure specification:

```text
ManagedNetworkDomainSpec:
    namespace
    host_interface
    inner_interface
    host_address: IPv4Interface
    inner_address: IPv4Interface
```

These fields are not accepted external TOML syntax. Final instance/config grammar remains
separate implementation work.

The host/inner addresses must be distinct usable addresses in the same IPv4 subnet. Namespace
and interface names must satisfy Linux-safe bounded identifier syntax. The two interface names
must differ.

The lifecycle owns only:

- the named network namespace;
- the host-side boundary veth;
- the namespace-side boundary veth;
- the two explicit IPv4 addresses;
- namespace loopback UP state;
- namespace main-table default route via the host-side address.

It does **not** own:

- payload routes/RPDB;
- nft policy;
- VPN path interfaces;
- publication sockets/relays;
- host firewall/NAT.

Only two initial presence shapes are accepted:

```text
namespace absent + host boundary absent
    -> fresh create

namespace present + host boundary present
    -> first confirm ForwardingGate=DISABLED
    -> exact read-only infrastructure verification

namespace present XOR host boundary present
    -> structural failure
    -> if namespace exists, forwarding remains protectively closed
```

Existing divergent infrastructure is not repaired or adopted in place. Wrong link type,
wrong/missing address, wrong default route, missing loopback/UP state or non-reciprocal veth
peer identity is a conflict/failure. A later explicit teardown/recreate operation may replace
it; `ensure` never guesses ownership.

Fresh creation is:

```text
require namespace + host boundary absent
    -> create namespace
    -> immediately converge/reread ForwardingGate=DISABLED
    -> create veth pair
    -> move inner endpoint into namespace
    -> assign exact IPv4 addresses
    -> host veth UP
    -> namespace lo + inner veth UP
    -> install namespace default via host address / inner veth
    -> fresh exact verification
```

Failure after namespace creation performs best-effort deletion of the just-created namespace
and any surviving host-side boundary, then propagates failure. No nft table or payload route
is created by this lifecycle.

Exact verification requires current kernel evidence that:

- namespace and host boundary exist;
- both boundary endpoints are veth and UP;
- both configured IPv4 addresses are present;
- namespace loopback is UP;
- namespace default route points through the configured host address and inner interface;
- host and inner veth endpoints expose reciprocal `ifindex/link_index`, proving they are the
  same current veth pair.

The verified inner endpoint is returned as the current host-boundary `InterfaceIdentity`
for downstream binding/payload desired-state assembly. No stored ifindex registry is needed.

Destroy is infrastructure cleanup, not semantic policy cleanup:

```text
if namespace exists:
    best-effort ForwardingGate=DISABLED
delete namespace best effort
delete surviving host boundary best effort
fresh verify namespace + host boundary absent
```

Normal product shutdown should release higher network-policy owners first when possible;
crash/failure containment may still close forwarding and remove the owned infrastructure.

This contract deliberately reuses the already live-proven NG2 namespace/veth lifecycle facts
(peer verification, partial-state refusal and no policy ownership) while adapting them to the
current NG3 ForwardingGate and leaving external configuration syntax unfixed.

### 1.1.1-A. Host-boundary bootstrap and return routing

**Implements:**
- `VPNG0002-R2.R3.R1.R1`;
- `VPNG0002-R2.R3.R1.R1.R1`;
- `VPNG0002-R2.R3.R1.R1.R2`;
- `VPNG0002-R2.R3.R3.R1`;
- `VPNG0002-R2.R3.R3.R1.R1`;
- `VPNG0004-R4.R6.R1.R1`;
- `VPNG0004-R4.R6.R1.R2`.

The isolated managed domain does not remove the ordinary VPN bootstrap problem: a packet
initiated on the ordinary/host side must first be delivered into the explicit VPN-GATE
boundary before Profile routing can act on it. NG3 therefore defines a separate
**host-boundary policy owner**. It owns only explicit VPN-GATE tables/rules/nft state and does
not own the ordinary host `main` table.

Bootstrap is required for:

```text
outbound
bidirectional
inbound+route-return
bidirectional+route-return
```

The selected Release-1 Linux realization is backed by EXP-056 and EXP-059 and deliberately
does **not** install Profile routes or endpoint pins into host `main`.

#### Dedicated bootstrap table and paired RPDB rules

One VPN-GATE-owned host bootstrap table contains one route toward the managed inner peer for
each distinct bootstrap destination. `0.0.0.0/0` is represented as an ordinary default route
inside this dedicated table; no split-default or default replacement is needed in `main`.

Packets already emitted by the managed stack must bypass bootstrap before destination rules:

```text
iif <managed-host-boundary>
    -> lookup main
```

This rule is the ordinary underlay/server-reply escape. It applies equally to:

- client VPN transport packets leaving the managed namespace;
- replies from a published VPN server to dynamic external clients;
- any other packet that has already crossed from the managed domain into the host.

Therefore no exact underlay endpoint pin is required, and a managed exact `/32` destination
may equal a VPN transport endpoint: ordinary/local initiation and stack-origin transport are
distinguished by ingress direction.

For each bootstrap destination prefix `P`, rule pairs are ordered by descending prefix
length and then deterministic network/owner order:

```text
to P lookup main suppress_prefixlength prefixlen(P)
to P lookup <VPNG-bootstrap-table>
```

The first rule asks the current ordinary `main` table for a route but suppresses any decision
whose prefix is equal to or broader than `P`. Consequently:

- an ordinary route **strictly more specific** than the matching managed destination wins;
- an equal or less-specific ordinary route does not override explicit Profile policy;
- connected LAN/uplink routes naturally survive a full-tunnel Profile;
- an administrator route added after VPN-GATE activation is honored immediately when it is
  strictly more specific; VPN-GATE does not copy or reconcile that route;
- a nested more-specific managed destination is processed by its own earlier rule pair and can
  still override a broader ordinary route.

The dispatch rule then looks up the VPN-GATE bootstrap table. This is equivalent to the useful
longest-prefix behavior of conventional VPN route injection without mutating host `main`.

Reserved VPN-GATE RPDB priorities execute after the kernel local rule but before ambient main
lookup. A foreign rule/object occupying an exact VPN-GATE-owned priority/table key is a
diagnosable conflict; VPN-GATE does not renumber around arbitrary administrator policy or
adopt foreign state. Administrator rules at higher precedence remain administrator
responsibility, consistent with the conventional VPN operating boundary.

#### Stateful remote-initiated return is a separate owner

Bootstrap routing and stateful return intentionally remain separate. EXP-057 proved that one
undifferentiated mark/table cannot satisfy both semantics: bootstrap must preserve a
strictly-more-specific ordinary route, while return traffic for an already-associated
remote-initiated flow must be forced back to the managed stack.

EXP-053 remains the selected stateful-return mechanism:

```text
remote NEW enters host from managed boundary
    -> save connection association in ct mark

forwarded reply
    -> restore packet mark in PREROUTING

host-local reply
    -> restore packet mark in nft type-route OUTPUT

return fwmark
    -> dedicated return RPDB rule/table
    -> managed boundary
```

The return fwmark rule executes before bootstrap bypass/prefix pairs. Thus an associated reply
cannot accidentally fall through to a more-specific ordinary route.

The canonical `+route-return` Profile modifier disables this stateful return steering for
that Profile. Its unmarked reply is then handled by the ordinary bootstrap pair for the
Profile destination and therefore follows route-based VPN semantics, including preservation
of strictly-more-specific `main` routes.

The modifier does **not** mean Linux `NOTRACK`, does not disable conntrack globally and does
not alter Profile firewall state semantics.

The production-shaped controller/alpha composition now treats bootstrap and stateful return
as one bounded **selected host-boundary contribution** while retaining their separate lower
owners. Runtime audit first observes the complete contribution. Exact state is a no-op; any
repair closes the managed ForwardingGate before host-boundary mutation, and conflicting
reserved host state is fail-closed rather than adopted. The stateful return route/RPDB owner
predates protocol-tagged host bootstrap ownership, so its reserved table/priority accepts only
ABSENT or exact desired state; a different occupant is a conflict, not automatically deletable
stale state. Cleanup disables selected bootstrap capture first, then removes return nft and
return routing dependencies.

The executable alpha now accepts canonical `+route-return` and exercises this composition
through its ordinary startup/reconcile/stop lifecycle. This changes no grammar or semantics;
it closes the previous alpha materialization gap.

#### Evidence and rejected alternatives

- EXP-053: stateful host return steering — PASS;
- EXP-054/055: exact endpoint pin + host-route fallback/composite — PASS, retained as
  comparative fallback evidence;
- EXP-056: managed-ingress ordinary-main bypass — PASS;
- EXP-057: one shared bootstrap/return mark-table — FAIL and rejected;
- EXP-058: dedicated table with copied `throw` routes — PASS but not selected because it
  requires replication/reconciliation of ordinary route prefixes;
- EXP-059: paired RPDB bootstrap with `suppress_prefixlength` — PASS and **selected**.

This architecture does not require VPN-GATE to protect its owned host-boundary rules/tables
from a privileged administrator any more strongly than conventional VPN software protects its
own installed routes. It does require exact owner observation and fail-fast conflict handling
for the reserved VPN-GATE keys.

### Architectural consequence for external VPN channels

**Constrained by:**
- `VPNG0001-R1.R3.C1`
- `VPNG0001-R1.R3.C2`

**Implements:**
- `VPNG0001-R1.R3.C1.R1`
- `VPNG0001-R1.R3.C2.R1`

An administrator-provisioned VPN channel is useful to NG3 only when its data-plane endpoint
is available inside the isolated managed network domain.

The architecture therefore rejects the host-only shape:

```text
host namespace:
    vpn0  <-- VPN endpoint used directly by VPN-GATE routing
```

as the normal managed-path model.

The intended shape is:

```text
host / external provisioning environment
        |
        | explicit onboarding boundary
        v
+----------------------------------+
| NG3 isolated managed network     |
|                                  |
|   vpn data-plane endpoint        |
|          |                       |
|   payload routing/filtering      |
|          |                       |
|   explicit host-side boundary    |
+----------------------------------+
```

This section intentionally does **not** specify whether the VPN endpoint arrives by interface
creation inside the namespace, interface movement, process placement, protocol-specific
setup or another mechanism.

For the current scope, onboarding is architecturally closed with respect to both:

- **where** the data-plane endpoint must exist — inside the managed domain behind an explicit
  host/domain boundary;
- **which logical path it represents** — through the verified logical-path binding contract.

Concrete per-integration commands and external field names remain documentation/interface
implementation work.

### 1.1.2. Supported VPN onboarding applicability evidence gate

**Implements:**
- `VPNG0001-R1.R3.C1.R1.R1`

A supported external VPN onboarding integration is not accepted merely because an interface
placement mechanism appears plausible on paper. Before an integration may be called supported,
the project must retain reproducible target-Linux evidence for the complete administrator-facing
boundary:

```text
published administrator procedure
    ->
administrator-only external VPN setup/onboarding actions
    ->
VPN data-plane endpoint present inside the managed network domain
    ->
fresh VPNPathAdapter observation
    ->
exactly one expected logical-path binding
    ->
path admitted to the existing forwarding contract
```

The evidence must not depend on modifying VPN-GATE internals during the procedure. It must
record the exact external VPN implementation/version and the commands/configuration used, and
must include cleanup/repetition sufficient to show that the result is reproducible rather than
a one-off pre-existing host state.

EXP-049 initially exposed a real closure defect: OpenVPN 2.6.14 could run inside the managed
namespace and bind exactly, but the empty terminal `stack_input` / `stack_output` DROP
boundary killed its UDP underlay after activation.

The repaired integration now passes the complete gate on Debian 13 twice using the actual
first-release administrator shape:

```text
administrator-visible systemd VPN service
    + BindsTo / After managed-domain lifecycle anchor
    + NetworkNamespacePath = managed netns
    + policy-neutral OpenVPN configuration (route-noexec)
    + explicit integration transport facts
        ->
OpenVPN MainPID inside managed netns
        ->
real vpn0 created there
        ->
fresh exact NG3 binding
        ->
bounded integration-local INPUT/OUTPUT allow
        ->
production policy activation
        ->
controlled payload through vpn0
        ->
systemctl stop removes VPN runtime/endpoint
```

The lower integration-local owner marker is
`vpn-gate:ng3:local-integration-v1`. Arbitrary ICMP to the underlay remains blocked while
the exact OpenVPN transport and controlled payload succeed.

This closes the applicability mechanism for the tested OpenVPN/systemd integration only.
It does not silently generalize to all VPN technologies. Each additional supported onboarding
mechanism requires equivalent evidence or an explicitly reviewed proof of material
equivalence.

### 1.1.2.1. Release-1 systemd onboarding boundary

**Constrained by:**
- `VPNG0001-R1.R3.C1.C1`
- `VPNG0001-R1.R3.C1.C1.R1`
- `VPNG0001-R1.R3.C1.C1.R2`
- `VPNG0001-R1.R3.C1.C1.R3`
- `VPNG0005-R5.C1`
- `VPNG0005-R5.C1.R1`

Release 1 uses systemd as the VPN process supervisor rather than introducing a VPN-GATE
process manager.

For a supported service:

```text
distinct stack-specific VPN unit/instance
    BindsTo = managed-domain/controller unit
    After = managed-domain/controller unit
    NetworkNamespacePath = managed netns
```

The administrator retains normal `systemctl start/stop/restart` semantics for the VPN unit.
A supported reload remains implementation-specific.

Prefer a distinct instance of a vendor template when available. A systemd alias is not a
second independently configurable service and is therefore not a cloning mechanism.

First-release automation deliberately does not discover, clone, patch, enable or adopt
arbitrary administrator VPN units. The administrator prepares the stack-specific unit/drop-in
using `vpn-onboarding-release1.md`.

Integration-specific VPN configuration must be policy-neutral with respect to VPN-GATE-owned
managed-domain routes/RPDB/NAT/firewall. Examples include OpenVPN `route-noexec` and
WireGuard/wg-quick `Table = off`; conflicting legacy hooks belong outside the supported
managed-domain contract.

Direct root/admin modification of VPN-GATE-owned namespace/lifecycle artifacts is external
intervention. Observable invariant loss is fail-closed and diagnosable; Release 1 does not
promise forensic adoption or cleanup of arbitrary processes/namespace references left by
manual damage.

### 1.1.3. Release-1 bounded VPN lifecycle through systemd

**Implements:**
- `VPNG0007-R7.R7.R1`;
- `VPNG0007-R7.R7.R1.R1`;
- `VPNG0005-R5.R4`;
- `VPNG0005-R5.R5`;
- `VPNG0005-R5.R6.R2`;
- `VPNG0005-R5.R6.R3`.

**Constrained by:**
- `VPNG0001-R1.R3.C1.C1`;
- `VPNG0005-R5.C1`.

EXP-050 passed twice with the same OpenVPN 2.6.14 / systemd onboarding mechanism that passed
EXP-049. The accepted first-release lifecycle boundary is therefore:

```text
administrator
    -> owns VPN-specific configuration
    -> prepares the distinct stack-specific VPN unit/instance/drop-in

systemd
    -> supervises the explicitly bound VPN process/cgroup
    -> performs VPN service start/stop/restart
    -> enforces BindsTo/After dependency ordering

VPN-GATE
    -> owns managed network domain and fail-closed policy
    -> owns bounded integration-local transport admission
    -> freshly observes/binds/reconciles each VPN endpoint generation
```

VPN-GATE does **not** introduce a generic VPN PID registry, process-tree scanner or process
supervisor.

A normal administrator `systemctl stop/start/restart <stack-vpn-unit>` operates on that VPN
without leaving the managed namespace. EXP-050 proved same-config restart and changed-config
restart with fresh OpenVPN processes and fresh `vpn0` generations:

```text
same-config:
    vpn0 ifindex 2 -> ifindex 3

changed VPN-specific config:
    vpn0 ifindex 3 -> ifindex 4
    tun-mtu 1500 -> 1400
```

After each generation change, NG3 used fresh authoritative observation, rebound the current
endpoint, reconciled current route/RPDB/nft state and carried controlled payload without
requiring the old process or interface generation.

The supported deployment stop order is:

```text
ForwardingGate = DISABLED
    ->
stop managed-domain/controller systemd lifecycle anchor
    ->
BindsTo + reverse After ordering stops explicitly bound stack VPN unit(s)
    ->
confirm VPN unit inactive + old PID absent + cgroup empty + endpoint absent
    ->
run VPN-GATE owned-domain cleanup
    ->
confirm managed namespace + host boundary absent
    ->
release controller ownership
```

The current in-process `stop_controller_once(...)` remains intentionally smaller: it cleans
VPN-GATE-owned managed-domain resources and does not enumerate or kill arbitrary VPN
processes. The deployment/systemd layer is responsible for stopping the **explicitly bound**
stack-specific VPN units before invoking/finalizing domain cleanup. This is now an accepted
layering boundary rather than an unresolved ownership question.

Aggressive OpenVPN evidence also closes the first-release configuration boundary. The
supported OpenVPN shape uses `route-noexec` and does not elevate arbitrary user scripts with
`script-security 2`. A test hook attempting route/RPDB/nft/sysctl mutation was not executed;
OpenVPN failed visibly and systemd reported the failed service. Equivalent privileged hooks
that deliberately bypass these restrictions are outside the supported integration contract
and are treated as administrator/root intervention, not state VPN-GATE must silently adopt.

EXP-050 evidence is retained in
`EXP-050-result-20261117-systemd-openvpn-pass.md`. The lifecycle mechanism is accepted for
Release 1; VPN-specific policy-neutral restrictions still require per-integration
documentation/evidence.

## 1.2. Architecture-wide implementation requirements

The structure and maintenance rules of this report itself implement cross-cutting NG3
requirements that do not belong to one runtime component.

**Implements:**
- `VPNG0007-R7.R2`
- `VPNG0007-R7.R3.R3`
- `VPNG0007-R7.R4`
- `VPNG0007-R7.R6.R1`
- `VPNG0007-R7.R6.R2`
- `VPNG0007-R7.R7`

Consequences for this architecture:

- responsibilities and contracts are described locally enough for human/AI review;
- stable internal contracts are intended to contain unrelated change;
- independent component scopes are intended to support parallel review/development units;
- every material architectural block links back to the requirement tree;
- any requirement/constraint change requires revalidation of the affected architecture
  before implementation continues;
- every substantial implementation/experiment unit must identify the exact accepted R/C whose
  implementation, verification or closure requires that work; evidence does not create
  product semantics by itself.

# 2. Real scenarios used by this design

These scenarios are not additional requirements. They are concrete situations used to test
whether the decomposition is necessary and sufficient.

## S1 — Explicitly managed payload

A configured traffic class is allowed to use a configured set of VPN paths. Unrelated host
traffic must not acquire VPN forwarding merely because those paths exist.

Relevant requirements:
- `VPNG0001-R1.R1`
- `VPNG0002-R2.R1`
- `VPNG0002-R2.R2`
- `VPNG0002-R2.R3`
- `VPNG0002-R2.R4`
- `VPNG0004-R4.R1`

## S2 — Preferred path degrades

Two or more paths are allowed. The preferred path becomes practically unusable while at
least one allowed alternative remains usable. New traffic should prefer the usable
alternative, without changing path membership.

Relevant requirements:
- `VPNG0003-R3.R1`
- `VPNG0003-R3.R2`
- `VPNG0003-R3.R2.R1`
- `VPNG0003-R3.R3`
- `VPNG0003-R3.R4`
- `VPNG0003-R3.R5`
- `VPNG0003-R3.R7`

## S3 — Local presence is not sufficient evidence

A VPN interface/process can remain locally present while the remote path property relevant
to the product scenario is no longer usable. Payload may also be idle, so waiting for a
payload failure is not always useful.

The architecture therefore selects active observation as the first NG3 mechanism for
obtaining evidence required by `VPNG0003-R3.R6`. Active probing is an architectural choice,
not a product promise.

Relevant requirements:
- `VPNG0003-R3.R6`
- `VPNG0003-R3.R6.R3`

## S4 — Old observation finishes late

The observed concrete path context changes while an earlier asynchronous check is still
in-flight. Its later result must not modify current preference.

Relevant requirements:
- `VPNG0003-R3.R6.R1`
- `VPNG0003-R3.R6.R2`

## S5 — Network mutation partially fails

The system begins changing owned network policy and one lower operation fails. The next
decision must be based on freshly observed authoritative state and must not silently expose
unallowed forwarding.

Relevant requirements:
- `VPNG0004-R4.R2`
- `VPNG0004-R4.R3`
- `VPNG0004-R4.R4`
- `VPNG0004-R4.R5`
- `VPNG0005-R5.R2`
- `VPNG0005-R5.R3`

## S6 — One cleanup area fails

Shutdown owns several independent resources. Failure to clean one must not prevent attempts
to clean the others, and the failures must remain visible.

Relevant requirements:
- `VPNG0005-R5.R4`
- `VPNG0005-R5.R5`
- `VPNG0006-R6.R3`

# 3. Architecture summary

```text
normalized payload intent
        |
        | RequestEvent / assembly input
        v
+-----------------------+
| PayloadTrafficManager |<---------------------------+
|        Manager        |                            |
+-----------------------+                            |
        |                                            |
        | uses                                       | availability InfoEvent
        v                                            |
+-----------------------+                            |
| PayloadPolicy         |                            |
| Calculator            |                            |
+-----------------------+                            |
        |                                            |
        +--> AvailabilityPriorityCalculator          |
        |                                            |
        v                                            |
+-----------------------+                            |
| NetworkPolicyAdapter  |                            |
|       Adapter         |                            |
+-----------------------+                            |
        |                                            |
        v                                            |
+-----------------------+                            |
| NetworkPolicyExecutor |                            |
|       Executor        |                            |
+-----------------------+                            |
        |                                            |
        v                                            |
managed network domain                               |
                                                     |
                                           +----------------------+
                                           | AvailabilityProbe    |
                                           | Agent                |
                                           +----------------------+
                                                     |
                                                     | uses
                                                     v
                                           +----------------------+
                                           | ActiveProbeDriver    |
                                           | Driver               |
                                           +----------------------+
                                                     |
                                                     v
                                               external network
```

The event-delivery mechanism is intentionally left abstract. NG3 requires the semantic edge,
not a persistent bus, journal or replay system.

The externally provisioned VPN-channel integration adds one narrow Machinery boundary:

```text
logical VPN path intent
        |
        v
+-----------------------+
| VPNPathAdapter        |
|       Adapter         |
+-----------------------+
        |
        v
observed concrete endpoint
inside managed network domain
```

The Adapter resolves and verifies a binding; it does not provision or configure the VPN
session.

## 3.1. External VPN-channel boundary

**Implements:**
- `VPNG0001-R1.R3`
- `VPNG0001-R1.R3.C1.R1`

**Constrained by:**
- `VPNG0001-R1.R3.C1`

For the first release, VPN-GATE consumes VPN channels that have already been deployed and
basically configured by the administrator.

The architecture therefore does **not** introduce a VPN-session/tunnel provisioning Manager
merely because older generations contained VPN process-management machinery.

The product-side boundary defines enough administrator-facing contract to make an externally
provisioned channel:

- place its data-plane endpoint inside the isolated managed network domain;
- identifiable as a concrete VPN-GATE path;
- observable to the extent required by routing, safety and status requirements;
- usable by payload policy;
- documentable as a repeatable administrator procedure.

The exact representation of that contract remains integration-specific. A Linux interface
move, process placement, interface name, protocol-specific handle or another mechanism may be
selected by a supported integration without changing the accepted product semantics.

## 3.2. Logical VPN path binding

**Implements:**
- `VPNG0001-R1.R3.R1`
- `VPNG0001-R1.R3.R2`
- `VPNG0001-R1.R3.R3`
- `VPNG0004-R4.R6.R1.R4`
- `VPNG0007-R7.R3.R1`
- `VPNG0007-R7.R3.R2`

The architecture separates:

```text
logical path identity
!=
concrete current data-plane endpoint
```

The product-facing path identity is stable for the configuration lifecycle. Runtime endpoint
identity may change when the administrator recreates/replaces the externally provisioned VPN
channel.

The human configuration names Devices, not every logical path.

Logical path identity is derived during Device binding normalization from:

```text
Device ID
+ expected-interface selector position
+ stable slot within selector quota
```

The concrete runtime endpoint is the current binding of that logical identity.

A replacement endpoint may become the current endpoint for the same logical path only after
the new binding has been observed and verified.

### VPNPathAdapter

**Component type:** Adapter

**Implements:**
- `VPNG0001-R1.R3.R1`
- `VPNG0001-R1.R3.R2`
- `VPNG0001-R1.R3.R3`
- `VPNG0001-R1.R3.R4`
- `VPNG0001-R1.R3.R4.R1`
- `VPNG0001-R1.R3.R4.R2`
- `VPNG0001-R1.R3.R4.R3`
- `VPNG0001-R1.R3.R4.R3.R1`
- `VPNG0001-R1.R3.R4.R4`
- `VPNG0004-R4.R6.R1.R4`
- `VPNG0007-R7.R3`
- `VPNG0007-R7.R5`

The Adapter is the boundary between logical VPN-path semantics and the externally
provisioned concrete VPN endpoint.

Conceptual boundary:

```text
observe_device_endpoints(active DeviceBindingIntent set)
    -> observed candidate endpoints in managed domain

verify_path_binding(logical_path_id, concrete endpoint)
    -> matched current endpoint
     | absent
     | ambiguous
     | wrong managed domain
     | structurally unusable
```

The Adapter observes lower-domain facts. It does not decide Profile policy or Device
preference.

The executable Linux reference realizes this boundary with a stateless
`LinuxVpnPathAdapter`. Every observation obtains one complete fresh managed-netns link
inventory, parses exact `(ifname, ifindex)` identities and may require the already verified
host-boundary generation to be present before the snapshot is consumed. The Adapter keeps no
current inventory cache or generation registry.

The alpha's periodic timer is only a wakeup cadence. Startup and every periodic reconcile call
the same fresh Adapter observation path; a failed command/parse is an observation failure and
is never converted to an empty endpoint set. Netlink events may later replace or supplement
the wakeup mechanism without changing this authoritative snapshot contract.

A successful result must prove at least:

- the endpoint is inside the managed network domain;
- the endpoint matches the normalized binding intent for the logical path;
- exactly one current endpoint is selected;
- a previously superseded endpoint is not returned as current.

The Adapter does **not**:

- create the VPN session;
- configure protocol credentials;
- choose payload eligibility;
- decide path preference;
- decide availability health;
- invent the user configuration syntax.

The semantic content of `normalized_binding_intent` is defined: it must identify one
current concrete endpoint for one logical path. The exact external selector spelling and
protocol-specific discovery mechanics remain replaceable interface/integration details.

### 3.2.1. Transport endpoint provenance

**Implements:**
- `VPNG0001-R1.R3.R5`
- `VPNG0001-R1.R3.R5.C1.R1`

**Constrained by:**
- `VPNG0001-R1.R3.R5.C1`

Transport endpoint provenance is a bounded optional fact attached to the **current verified
path binding**, not part of stable `LogicalPathId` identity:

```text
current PathBinding
    = LogicalPathId + current InterfaceIdentity(ifname, ifindex)

optional current transport provenance
    = transport endpoint/peer identity
      proven by the accepted integration discovery/onboarding contract
      for exactly that current PathBinding
```

The fact answers a different question from the tunnel's inner/network-layer peer address and
from an availability probe target. A public OpenConnect server address, a WireGuard peer
endpoint, an inner point-to-point address and a Profile-specific ICMP target are not assumed
to be interchangeable.

`VPNPathAdapter` is the technical observation boundary for this provenance because it already
owns observation and verification of the concrete external endpoint. A supported integration
may enrich the current binding observation with transport provenance when its accepted lower
contract provides sufficient evidence. The Adapter must return provenance as absent/unresolved
rather than infer it from an interface prefix, slot number, reused ifname, ambient route or an
unrelated inner peer address.

Provenance validity is scoped to the exact current concrete binding. Replacement of the
concrete endpoint invalidates the old provenance together with the old binding; no separate
global generation counter or provenance history is introduced.

Potential consumers remain separate semantic owners:

- `AvailabilityDescriptionResolver` may use confirmed transport provenance when an accepted
  integration-specific target derivation formula requires it;
- a future endpoint-scoped Device firewall policy may resolve a logical/named endpoint through
  confirmed provenance and then materialize the rule against the current concrete path;
- status/diagnostics may display confirmed provenance without becoming its source of truth.

The first release does **not** require this fact for ordinary path binding, routing, explicit
availability targets or other functions whose accepted semantics do not depend on it. A
consumer that requires provenance must fail/diagnose that dependent function when provenance
is unavailable; it must not broaden scope to all paths or guess a peer.

The exact human-facing named-endpoint syntax is deliberately postponed to the later
configuration-format review. No named-endpoint grammar is selected here.

**EXP-039 result:** PASS on privileged Linux CI. A real userspace-held
`IFF_POINTOPOINT` TUN exposed its inner point-to-point address peer, but changing the
userspace transport socket peer left generic `ip -j -d link` and `ip -j addr` observation
unchanged and neither transport address appeared there. Therefore transport endpoint
identity is not an organic generic property of a point-to-point TUN interface.
Integration-specific provenance is required; generic interface discovery must not claim to
recover a transport peer merely from point-to-point interface state.

### 3.2.2. Bound endpoint versus route realization

A verified `PathBinding(logical_path_id, InterfaceIdentity)` proves **which current
endpoint** represents the path. It does not, by itself, prove the complete Linux route
next-hop shape for every possible supported VPN integration.

The lower VPN integration contract therefore additionally produces:

```text
PathBinding
    + integration-specific verified topology/contract
        ->
RoutePriorityPathRoute:
    logical_path_id
    current InterfaceIdentity
    gateway = IPv4 | none
    onlink = true | false
```

The route realization must be consistent with the same current concrete endpoint identity
used by the binding.

The generic NetworkPolicyAdapter must not guess `gateway` or `onlink` from:

- interface name;
- Device ID;
- historical transport type;
- the mere presence of an IPv4 peer address;
- ambient host routes.

A supported integration may expose a simpler realization when evidence/onboarding proves it.

#### Direct-device integration capability

For an integration whose accepted lower contract states that protected destinations are
routed directly through the bound interface, the realization is:

```text
gateway = none
onlink  = false
dev     = current bound InterfaceIdentity.ifname
```

Historical EXP-009 H5 is concrete evidence that this shape works for the tested OpenConnect
point-to-point endpoint. WireGuard remains governed by its own cryptokey-routing
(`AllowedIPs`) contract; a WireGuard onboarding profile may use direct-device realization
only when its external configuration makes the Profile destinations valid for that
interface.

Direct-device is therefore an explicit **integration capability**, not a universal property
of every interface matched by `expected_interfaces`.

If the selected integration cannot produce one unambiguous current route realization for a
bound logical path, that path is not structurally ready for payload route materialization.
The lower policy remains unconfirmed/fail-closed; the Adapter does not invent a gateway.

No new user-facing route field is introduced by this boundary. Route realization belongs to
the supported integration/onboarding contract beneath the Device/Profile policy model.

## 3.3. Declarative configuration boundary

**Implements:**
- `VPNG0001-R1.R2.R1`
- `VPNG0001-R1.R2.R2`
- `VPNG0001-R1.R2.R3`
- `VPNG0001-R1.R2.R4`
- `VPNG0001-R1.R2.R4.R1`
- `VPNG0001-R1.R2.R4.R1.C1`
- `VPNG0001-R1.R2.R4.R2`
- `VPNG0001-R1.R2.R4.R2.R1`
- `VPNG0001-R1.R2.R4.R3`
- `VPNG0001-R1.R2.R4.R4`
- `VPNG0001-R1.R2.R4.R4.R1`
- `VPNG0001-R1.R2.R4.R4.R2`
- `VPNG0001-R1.R2.R4.R4.R3`
- `VPNG0001-R1.R2.R4.R5`
- `VPNG0001-R1.R2.R4.R6`
- `VPNG0001-R1.R2.R4.R6.R1`
- `VPNG0001-R1.R2.R4.R6.R2`
- `VPNG0001-R1.R2.R4.R6.R3`
- `VPNG0001-R1.R2.R4.R6.C1`
- `VPNG0001-R1.R2.R5`
- `VPNG0001-R1.R2.R5.R1`
- `VPNG0001-R1.R2.R5.R2`
- `VPNG0001-R1.R2.R5.R3`
- `VPNG0001-R1.R2.R5.R4`
- `VPNG0001-R1.R3.C1.R1`
- `VPNG0002-R2.R1`
- `VPNG0002-R2.R1.R1`
- `VPNG0002-R2.R1.R2`
- `VPNG0002-R2.R2`
- `VPNG0002-R2.R2.R1`
- `VPNG0002-R2.R2.R2`
- `VPNG0002-R2.R3`
- `VPNG0002-R2.R3.R1`
- `VPNG0002-R2.R3.R2`
- `VPNG0002-R2.R3.R3`
- `VPNG0002-R2.R3.C1`
- `VPNG0002-R2.R3.C1.R1`
- `VPNG0002-R2.R4`
- `VPNG0002-R2.R5`
- `VPNG0002-R2.R5.R1`
- `VPNG0004-R4.R1`
- `VPNG0007-R7.R3.R1`
- `VPNG0007-R7.R3.R2`
- `VPNG0007-R7.R5`

NG3 uses the recovered human-facing Device/Profile configuration model recorded in
`design/NG3/config-model.md`.

Users/admins describe product intent; they do not provide an ordered recipe of Linux
networking operations.

The human model is intentionally two-layered:

```text
Device
    = expected external VPN/network resource

Profile
    = desired network behavior using ordered Devices
```

A Device may be shared by multiple Profiles. Profile configuration contains no runtime route
metrics, kernel rules or concrete lower-network command sequence.

### ConfigurationAdapter

**Component type:** Adapter

The Adapter translates an external configuration representation into validated, normalized
domain intents.

It is Direct Machinery: a successful return means the supplied configuration has been
accepted and normalized; a failed return means no dependent network mutation may begin from
that candidate configuration.

The architecture intentionally avoids a global mutable "runtime configuration object".
Instead, the adapter produces explicit domain contracts needed by accepted requirements.

The human-facing parse result is normalized into explicit domain contracts:

```text
DeviceConfigIntent:
    device_id
    enabled
    expected_interfaces[] = ordered(selector, quota)
    nat_intent
    device_firewall?
    publications?

ProfileConfigIntent:
    profile_id
    enabled
    direction
    destinations[]
    device_order[] = plain Device IDs in baseline order
    reserve_device_ids[] = Profile-local subset of device_order
    availability_check?
    ordinary_gateway_nat_intent?

DeviceBindingIntent:
    device_id
    expected_interfaces[]

DevicePolicyIntent:
    device_id
    nat_intent
    device_firewall?
    publications?

PayloadProfileRequest:
    profile_id
    direction
    destinations[]
    ordered_paths[]

AvailabilityCheckConfig:
    profile_id
    mechanism
    target = explicit IPv4 | omitted

AvailabilityProbeIntent:
    availability_subject_id = (profile_id, logical_path_id)
    logical_path_id
    mechanism
    target = concrete IPv4
```

Key normalization rules:

- Device/Profile IDs remain stable opaque user identifiers;
- disabled Device/Profile placeholders do not require active-object semantic completeness;
- active Devices are derived as enabled Devices referenced by at least one enabled Profile;
- `DeviceBindingIntent` retains ordered expected-interface selectors and quotas;
- `ProfileConfigIntent` retains remote destinations and ordered Device references; canonical
  `device_order` membership suffixes are normalized into plain Device IDs plus a separate
  Profile-local reserve Device subset, so lower consumers never parse `:reserve`;
  canonical `direction` is normalized into base direction plus a separate Profile-scoped
  ordinary-side gateway NAT intent when the accepted `+snat` suffix is present;
- `PayloadProfileRequest` contains the concrete ordered logical paths obtained after binding
  while preserving Profile identity/direction/destinations;
- current concrete logical paths are derived from accepted Device bindings, not written
  directly into Profile config;
- supported user-facing values are parsed strictly and canonically; invalid/ambiguous input is
  rejected rather than silently repaired;
- field order is semantic only where the contract explicitly declares policy order;
- derived implementation values such as aggregate Device quota, ifindex, route metrics and
  table/rule priorities are not required from the user;
- an enabled Device eligible for ordinary-to-VPN traffic has explicit
  `use_outbound_nat = true|false`, normalized to `MASQUERADE|NONE`;
- `allow_vpn_client` is normalized as exact Device-owned VPN client transport/control facts;
  there is no public top-level `integration.*` object;
- Device `firewall` is normalized as an ordered first-match policy that can only narrow
  Profile permission; source/destination transport selectors use normalized ordered
  non-overlapping `PortBundle` values, omitted policy is permissive at the Device layer and
  explicit policy has terminal no-match DROP;
- `publish_vpn_server` is normalized separately from Profile payload routing; host/internal
  port bundles preserve declared item order and explicit translation requires equal expanded
  cardinality for positional 1:1 mapping;
- historical Device policy spellings are rejected rather than accepted as aliases;
- availability subject identity is exactly `(profile_id, logical_path_id)`;
- the same bound interface/path may therefore have independent availability state in
  different Profiles;
- first-release availability mechanism is ICMP;
- Device may provide a reusable default availability description;
- Profile independently selects no check, the Device default, or its own description of the
  same normalized shape;
- selecting Device default does not create Device-global health state: the resolved check and
  its evidence remain scoped to each `(Profile, logical path)`;
- probe runtime always receives one concrete normalized ICMP description with one IPv4 target.

The complete canonical Release-1 external TOML grammar is normative in
`design/NG3/config-model.md` and is normalized by the ConfigurationAdapter before any
dependent network mutation.

Payload policy, Device binding and availability remain separate normalized contracts even
though they originate from one human configuration.

### Device policy normalization

**Implements:**
- `VPNG0001-R1.R2.R4.R6`
- `VPNG0001-R1.R2.R4.R6.R1`
- `VPNG0001-R1.R2.R4.R6.R2`
- `VPNG0001-R1.R2.R4.R6.R3`
- `VPNG0001-R1.R2.R4.R6.C1`
- `VPNG0002-R2.R1`
- `VPNG0002-R2.R2`
- `VPNG0002-R2.R3`
- `VPNG0004-R4.R1`

The configuration boundary keeps Device transport policy separate from Profile need.

```text
DeviceConfigIntent
    -> DeviceBindingIntent
    -> DevicePolicyIntent
```

Canonical external-to-semantic normalization is:

```text
use_outbound_nat = false -> NatIntent.NONE
use_outbound_nat = true  -> NatIntent.MASQUERADE

allow_vpn_client
    -> exact Device-owned integration local/system transport intents

firewall[]
    -> ordered DeviceFirewallRuleIntent sequence
    -> each TCP/UDP source/destination port selector is PortBundle
       of ordered non-overlapping exact/range items
    -> omitted means permissive Device layer
    -> explicit no-match means DROP

publish_vpn_server
    -> ordered host PortBundle
       + identity mapping when internal bundle is omitted
       + equal-cardinality positional 1:1 host/internal mapping when explicit
    -> Device-owned host publication intent
       + managed-domain publication-local admission intent
```

The Device firewall can remove permission but cannot create destinations, directions or path
eligibility absent from Profile policy. One-line user rules are parsed exactly once at the
ConfigurationAdapter boundary; lower policy compilers never parse user strings.

Client transport/control permission and server publication are both Device transport
properties but remain different normalized owner classes. `allow_vpn_client` does not become
payload forwarding permission; `publish_vpn_server` does not become Profile routing.

Historical `nat`, `traffic_envelope`, `publications` and top-level `integration.*`
spellings are not compatibility aliases. Endpoint-scoped firewall syntax remains separately
deferred under `VPNG0001-R1.R2.R4.R6.R2.R5.C1`.

### AvailabilityDescriptionResolver

**Component type:** Calculator

**Implements:**
- `VPNG0001-R1.R2.R4.R4.R1`
- `VPNG0003-R3.R6.R1`
- `VPNG0003-R3.R6.R3.R1`
- `VPNG0003-R3.R6.R3.R1.C1.R1`
- `VPNG0003-R3.R6.R3.R1.C1.R1.R1`
- `VPNG0003-R3.R6.R3.R1.C1.R1.R2`
- `VPNG0003-R3.R6.R3.R1.C1.R1.R3`
- `VPNG0003-R3.R6.R3.R1.C1.R1.R4`
- `VPNG0003-R3.R6.R3.R2`
- `VPNG0007-R7.R1`
- `VPNG0007-R7.R3.R1`
- `VPNG0007-R7.R5`

**Constrained by:**
- `VPNG0003-R3.R6.R3.R1.C1.R1.C1`

This pure semantic projection resolves Profile availability selection above probe runtime.

Conceptual contract:

```text
resolve_description(
    availability_subject = (Profile, logical path),
    profile_selection = disabled | device_default | profile_description,
    corresponding Device default description?
)
    -> concrete AvailabilityProbeDescription
     | disabled
     | invalid
```

Release-1 `AvailabilityProbeDescription` is exactly:

```text
mechanism = ICMP
target = exact IPv4
```

Rules:

- absent Profile selection -> no probe demand for that Profile;
- Profile-owned description -> preserve that description exactly for each subject of the
  Profile;
- `default` -> copy the corresponding Device default description into the concrete
  subject-specific probe intent;
- if `default` is selected and the corresponding enabled Device has no valid default
  description, reject the configuration before runtime materialization;
- copying a Device description does not share availability evidence or state across Profiles;
- the Calculator does not inspect runtime peer/interface topology to invent a target.

The Calculator does not probe the network and does not own runtime observation state.

Validation must reject at least:

- invalid/duplicate Device or Profile IDs;
- enabled Device without non-empty valid expected-interface selectors;
- ambiguous active expected-interface selectors;
- enabled Profile without direction, destinations or device_order;
- first-release `inbound`/`bidirectional` Profile whose maximum eligible logical-path
  capacity from currently enabled referenced Devices exceeds 1;
- unknown Device references;
- duplicate Device references inside one Profile;
- duplicate exact destination ownership among enabled Profiles;
- invalid/non-strict IPv4 destination CIDRs;
- missing/invalid explicit Device NAT intent where the supported Device capability requires it;
- Device firewall declarations that would expand rather than restrict Profile permission;
- unsupported/ambiguous Device-firewall or publication grammar;
- malformed or unsupported availability-check mechanism/target;
- Profile `default` availability selection whose corresponding enabled Device has no valid
  default availability description;
- contradictory declarations that cannot produce one deterministic semantic result.

Known disabled Device references are valid and are skipped operationally.

Disabled Device/Profile placeholders bypass active-object deep semantic validation.

A rejected configuration is not partially materialized.

### Administrator onboarding contract

For each supported externally provisioned VPN-channel integration, administrator
documentation must explain:

1. how to provision the external VPN channel according to its own mechanism;
2. what result must exist inside the managed network domain;
3. how to declare the logical `path_id` and binding intent through the product
   configuration boundary;
4. how to determine that VPN-GATE accepted or rejected the binding.

This closes the architecture of `VPNG0001-R1.R3.C1.R1` without choosing a specific VPN
protocol. The Release-1 configuration spelling itself is now fixed by
`design/NG3/config-model.md`.

No ConfigManager, live-reload Engine, configuration database or generic plugin registry is
introduced. Those require separate accepted requirements if they become necessary.

## 3.4. Profile as independent payload-policy domain

**Implements:**
- `VPNG0001-R1.R2.R4.R4.R2`
- `VPNG0001-R1.R2.R4.R4.R3`
- `VPNG0002-R2.R2.R2`
- `VPNG0003-R3.R2.R1`
- `VPNG0004-R4.R1.R1`

A Profile is preserved as a semantic domain even when its current concrete path set is empty.

Normalization is therefore two-stage:

```text
ProfileConfigIntent
    + current valid Device bindings
        ->
PayloadProfileRequest:
    profile_id
    direction
    destinations[]
    ordered_paths[]
```

`ordered_paths` may be empty.

An empty path set does **not** remove the Profile from structural policy. Its destinations
remain classified to that Profile and materialize a fail-closed terminal result rather than
falling through to ambient/main routing.

Availability is applied after this structural request exists. It may reorder
`ordered_paths` through negative priority modification, but it cannot rewrite:

- Profile identity;
- destinations;
- direction;
- Device membership;
- binding eligibility;
- structural existence of the Profile domain.

Profile is not a VPN session/interface/peer, route metric, probe target or Linux-rule
container. Those remain separate lower or adjacent contracts.

# 4. PayloadTrafficManager

**Component type:** Manager

**Implements:**
- `VPNG0001-R1.R1`
- `VPNG0002-R2.R1`
- `VPNG0002-R2.R2`
- `VPNG0002-R2.R3`
- `VPNG0002-R2.R4`
- `VPNG0002-R2.R5`
- `VPNG0003-R3.R1`
- `VPNG0003-R3.R2`
- `VPNG0003-R3.R3`
- `VPNG0003-R3.R4`
- `VPNG0003-R3.R5`
- `VPNG0003-R3.R7`
- `VPNG0004-R4.R1`
- `VPNG0004-R4.R1.R1`
- `VPNG0004-R4.R2`
- `VPNG0005-R5.R2`
- `VPNG0005-R5.R3`
- `VPNG0006-R6.R2`
- `VPNG0006-R6.R4`
- `VPNG0007-R7.R1`
- `VPNG0007-R7.R3`
- `VPNG0007-R7.R5`
- `VPNG0007-R7.R6`

## 4.1. Responsibility

The Manager owns the current semantic payload-policy projection for normalized Profiles.

Its structural input is a set of `PayloadProfileRequest` objects. A request remains present
even when `ordered_paths` is empty, so fail-closed Profile membership is not lost when
bindings disappear.

It owns:

- current accepted structural payload intent;
- current allowed path membership for that intent;
- configured baseline path preference;
- Profile-local reserve roles normalized from Device memberships;
- current bounded availability-adaptation state;
- current active logical path for each Profile while that path remains usable;
- current effective path order;
- orchestration of desired payload network policy through the Adapter;
- current verified payload-policy projection published for observers.

It does **not** own:

- parsing the user configuration;
- VPN process creation;
- active probe transport;
- active probe target/mechanism/cadence;
- Linux route/table/nft representation;
- global user-facing status aggregation.

## 4.2. Why one Manager

The payload policy requirements form one transactional semantic responsibility:

```text
allowed traffic
+ allowed path membership
+ configured preference
+ availability priority modifier
+ fail-closed materialization
= one effective payload policy
```

Splitting membership and priority into independent Managers would create two writers to the
same effective routing domain and would require an additional transactional coordination
protocol not demanded by any accepted requirement.

Keeping them together therefore follows both the product semantics and
`VPNG0007-R7.R1`.

## 4.3. Availability state inside the Manager

For each availability subject (one Profile + logical VPN path), the Manager
may keep only the bounded semantic state necessary to implement `VPNG0003-R3.R3`,
`VPNG0003-R3.R4`, `VPNG0003-R3.R5.R1` and `VPNG0003-R3.R5.R2`:

- whether an availability problem is currently established;
- bounded progress toward establishing a problem;
- bounded progress toward confirming recovery.

No unbounded attempt history, evidence journal or replay log is justified.

**Implements:**
- `VPNG0003-R3.R3`
- `VPNG0003-R3.R4`
- `VPNG0003-R3.R5`
- `VPNG0003-R3.R5.R1`
- `VPNG0003-R3.R5.R2`
- `VPNG0007-R7.R1.R1`

The Manager consumes semantic availability evidence, not raw probe execution results.

The executable bounded composition is `availability_manager.py::AvailabilityManager`: it synchronizes current probe contexts, resets confirmation on context replacement, applies only matching fresh `ProbeEvidence`, and projects the resulting problem set into effective `PayloadProfileRequest` order using the existing sticky/reserve routing state.


Normalized evidence:

```text
AvailabilityEvidence:
    availability_subject_id
    logical_path_id
    observation_context
    outcome = positive | negative | no_evidence
```

where:

- `positive` is accepted evidence that the observed path property is currently usable;
- `negative` is accepted evidence that the observed path property is currently unusable;
- `no_evidence` means the observation attempt does not justify changing path state
  (for example, a local execution failure that does not itself prove path failure).

Only fresh evidence for the current availability subject/path/context enters hysteresis.

For each availability subject the Manager keeps bounded confirmation state:

```text
availability_problem: bool
degradation_progress: 0..degradation_threshold
recovery_progress:    0..recovery_threshold
```

For each Profile with at least one currently usable path, the Manager may additionally retain
one `current_active_path`. This is Profile-level routing state, not per-flow state. It exists
only to prevent recovery of another path from causing an unnecessary failback. If the active
path disappears or becomes availability-problematic, the active identity is replaced by the
next effective usable path. No connection tuple, conntrack entry, transport session, packet
history or path-equivalence record is required for this policy.

The thresholds are finite local availability-policy parameters. They are not assumed to be
user-configurable unless a later requirement says so.

Transition semantics:

- while `availability_problem == false`:
  - negative evidence advances bounded degradation progress;
  - positive evidence clears degradation progress;
  - `no_evidence` does not fabricate path evidence;
  - reaching the degradation threshold establishes the problem;
- while `availability_problem == true`:
  - positive evidence advances bounded recovery progress;
  - negative evidence clears recovery progress;
  - `no_evidence` does not fabricate recovery;
  - reaching the recovery threshold clears the problem.

On either state transition, obsolete progress is reset.

No observation history, time window, replay log or unbounded attempt count is retained.

Adaptation consumes evidence from the user-selected availability criterion. For the first release, that criterion is a concrete ICMP + IPv4 description resolved from either the corresponding Device default or the Profile override defined below.

## 4.4. Availability affects priority only

The Manager applies availability only after structural policy has established the allowed
path set.

```text
structural allowed paths
        |
        v
baseline preference + Profile-local reserve roles
        |
        v
availability problem state + current active path
        |
        v
effective order
```

Availability is not allowed to:

- create path membership;
- remove policy permission;
- change traffic membership;
- change direction policy.

**Implements:**
- `VPNG0002-R2.R4`
- `VPNG0003-R3.R2`
- `VPNG0003-R3.R4`
- `VPNG0003-R3.R4.R1`
- `VPNG0003-R3.R4.R1.R1`
- `VPNG0003-R3.R7`
- `VPNG0003-R3.R8`
- `VPNG0003-R3.R8.R1`
- `VPNG0003-R3.R8.C1`

The Release-1 selection rule is route-level and deliberately bounded:

```text
usable path
    = current allowed path without an established availability problem

no usable current_active_path
    -> choose the first usable path in baseline order

usable current_active_path and active membership is ordinary
    -> keep current_active_path first
    -> order all other usable paths by baseline preference

usable current_active_path and active membership is reserve
    -> allow the first higher-baseline usable path to preempt
    -> otherwise keep the reserve active path first

problem/unusable paths
    -> remain structurally present
    -> follow usable paths in baseline relative order
```

Thus a recovered path returns to its natural baseline position among standby paths but cannot
jump above a healthy ordinary active path. A reserve active path is the explicit exception:
its Profile-local role says that fast failback to a recovered higher-baseline usable path is
preferred over stickiness.

This policy changes the route used by traffic only at an actual failover boundary or an
explicit reserve failback boundary. It does not promise that transport sessions survive such a
boundary. In particular, Release 1 does not require preservation of external source
IP/port/NAT identity, buffering/replay, transport migration or per-flow concrete-path state
after the active path itself becomes unusable.

### Simplification review

The previous outbound design required per-flow concrete-path affinity so that route-priority
recovery could not migrate established flows. That mechanism is no longer necessary for the
accepted Release-1 policy: ordinary recovery does not change the active route at all.

The selected state is therefore bounded by Profile/path availability state plus one active
path identity per Profile. VPN-GATE does not add a conntrack-like flow table, per-flow timeout
lifecycle, path-equivalence proof machinery or flow-specific fail-closed routing merely to
implement availability failover.

EXP-062 remains valid evidence that concrete-path affinity is technically possible if a later
product requirement needs finer-grained flow semantics; it is not a Release-1 availability
prerequisite.

## 4.5. Device binding projection

**Implements:**
- `VPNG0001-R1.R3.R4`
- `VPNG0001-R1.R3.R4.R1`
- `VPNG0001-R1.R3.R4.R2`
- `VPNG0001-R1.R3.R4.R3`
- `VPNG0001-R1.R3.R4.R3.R1`
- `VPNG0001-R1.R3.R4.R4`
- `VPNG0003-R3.R1.R1`

`PayloadTrafficManager` owns the current shared Device-binding projection used by all
Profiles.

For each active Device it combines:

```text
ordered expected-interface selectors/quotas
+
freshly observed candidate endpoints
+
previous current binding projection
```

into bounded current logical paths.

The projection preserves surviving slot assignments when new endpoints appear, so ordinary
environment change does not arbitrarily reorder existing paths.

Each accepted bound path has a stable logical identity:

```text
logical_path_id :=
    Device ID
    + expected-interface selector position
    + stable slot within selector quota
```

The current concrete endpoint binding is separate mutable state and is not part of the
logical identity itself.

The exact serialized/internal logical-path ID format is implementation detail.

No inactive/unreferenced Device participates in discovery/binding work.

Endpoints that match no active selector or match ambiguously do not become managed logical
paths.

For one selector, at most its configured quota is bound.

Linux concrete endpoint identity is `(ifname, ifindex)`; the same ifname with a new ifindex
is a fresh endpoint instance.

Quota admission preserves survivors:

- a newly observed candidate never evicts an already bound survivor merely because its name
  sorts earlier or it appeared in a later snapshot;
- over-quota candidates remain observable but unbound;
- once a bound disappearance is verified/committed, a waiting candidate may occupy the
  freed slot on a later reconciliation;
- waiting-candidate promotion preserves committed first-observed order;
- simultaneously first-observed candidates retain fresh kernel-snapshot order, with
  `ifindex` as the final tie-break;
- lexical ifname sorting is not used as policy.

This is bounded current binding state, not an event history: only the information needed to
preserve current survivor/admission order is retained.

This responsibility remains inside the existing PayloadTrafficManager for now because the
binding projection has no independent actuation or product policy outside the current payload
path set. A separate Device-binding Engine would require evidence of an independent ongoing
responsibility that cannot be represented here.

# 5. PayloadPolicyCalculator

**Component type:** Calculator

**Implements:**
- `VPNG0002-R2.R1`
- `VPNG0002-R2.R1.R1`
- `VPNG0002-R2.R1.R2`
- `VPNG0002-R2.R2`
- `VPNG0002-R2.R2.R1`
- `VPNG0002-R2.R3`
- `VPNG0002-R2.R3.R1`
- `VPNG0002-R2.R3.R2`
- `VPNG0002-R2.R3.R3`
- `VPNG0002-R2.R4`
- `VPNG0002-R2.R5`
- `VPNG0002-R2.R5.R1`
- `VPNG0007-R7.R3.R1`
- `VPNG0007-R7.R5`

The Calculator maps normalized structural intent and already-resolved external facts into a
deterministic semantic payload-policy projection.

It is pure: the same inputs produce the same projection.

This component is justified because policy interpretation is independently testable and must
not depend on hidden network history.

Its semantic inputs are:

```text
enabled ProfileConfigIntent set
+
current Device binding projection
+
normalized DevicePolicyIntent set
```

It first produces one `PayloadProfileRequest` per enabled Profile, then the structural
network-policy projection for those requests.

The Calculator must preserve these invariants:

- Profile remote membership comes only from its strict IPv4 destinations;
- ordinary->VPN NEW classification uses remote destination;
- VPN->ordinary NEW classification first restricts Profiles by actual ingress Device/path,
  then uses remote source prefix;
- exact duplicate destination ownership across enabled Profiles is invalid;
- different-length overlaps resolve deterministically by most-specific applicable Profile;
- path eligibility comes only from Profile.device_order plus current valid bindings of those
  Devices;
- zero eligible paths still preserve the Profile/destination domain with fail-closed terminal
  behavior;
- direction is explicit and independent;
- configured preference follows Profile.device_order -> expected-interface order -> stable
  slot;
- ordered Device firewall verdict is composed with Profile permission before lower Adapter
  materialization and can never widen Profile permission;
- per-path NAT intent comes from the owning Device policy and is independent from availability;
- transport publication intent is not interpreted as Profile payload permission;
- availability state is not an input to structural membership or permission;
- availability can later reorder only already-eligible logical paths.

## 5.1. First-release inbound/bidirectional path-capacity constraint

**Implements:**
- `VPNG0002-R2`
- `VPNG0002-R2.R3`
- `VPNG0002-R2.R3.R3`
- `VPNG0002-R2.R3.C1`
- `VPNG0002-R2.R3.C1.R1`

First release deliberately does not promise remote-initiated multi-path return-path behavior.

During configuration normalization, for every enabled Profile with:

```text
direction = inbound | bidirectional
```

the product computes the maximum eligible logical-path capacity implied by the currently
enabled Devices referenced by that Profile:

```text
Profile max path capacity
    =
sum(
    selector quota
    for every expected-interface selector
    of every currently enabled referenced Device
)
```

Exact selectors contribute quota 1. Prefix selectors contribute their explicit positive
quota.

If the resulting capacity is greater than 1, configuration normalization fails before
dependent network actuation with a diagnostic explaining that first-release
inbound/bidirectional multi-path is unsupported.

Consequences:

- current runtime presence of only one interface does **not** make a capacity>1 Profile
  acceptable;
- a disabled referenced Device contributes no current capacity; enabling it later is itself a
  configuration change and triggers validation again;
- outbound-only Profiles are not constrained by this rule and may remain multi-path;
- runtime disappearance/reappearance inside an already accepted capacity<=1 Profile does not
  change the product contract;
- no runtime fallback guesses return-path semantics if an unsupported topology is presented.

EXP-062 supersedes historical EXP-014 as the current technical evidence for a possible future
multi-path inbound/bidirectional extension. EXP-062 is PASS but its registry disposition is
deferred: Release 1 remains constrained to capacity<=1 until an explicit product decision
revises the requirements and selects the extension.

## 5.2. Established-flow path affinity inside the managed stack

**Implements:**
- `VPNG0002-R2.R6`;
- `VPNG0003-R3.R8`;
- `VPNG0003-R3.R8.R1`;
- `VPNG0003-R3.R8.C1`;
- `VPNG0007-R7.R3.R4`;
- `VPNG0007-R7.R3.R4.R1`.

**Constrained by:**
- `VPNG0002-R2.R3.C1`.

The host-side return mechanism from EXP-053 solves only the host/managed-domain boundary.
It returns a reply to the stack but does not by itself preserve which VPN routing domain
accepted the original remote-initiated flow.

This distinction is material when managed destinations overlap:

```text
channel A / Profile A: 10.0.0.0/16
channel B / Profile B: 10.0.0.0/24

remote 10.0.0.2 enters through A
reply re-enters stack from host boundary
ordinary NEW-flow classification -> B (/24)
required established-flow return -> A
```

Therefore payload permission and established-flow routing affinity remain separate lower
responsibilities. `payload_forward` may permit an established reply, but its address
predicate is not allowed to substitute for preservation of the routing domain selected by
the original inbound flow.

EXP-061 proves the Release-1 Linux mechanism end to end across:

```text
VPN ingress
    -> managed stack
    -> ordinary host/LAN
    -> ordinary host
    -> managed stack
    -> original VPN routing domain
```

The selected Release-1 projection is:

```text
VPN-originated NEW flow on an accepted ingress path
    -> save Profile routing-domain association in stack conntrack mark

reply re-enters from verified host boundary
    -> restore reserved ct mark to packet fwmark

higher-precedence affinity RPDB rule
    -> original Profile routing table
    -> current single eligible inbound path
```

The mark identifies the original **Profile routing domain**, not an arbitrary concrete path.
That is sufficient only because `VPNG0002-R2.R3.C1` limits Release-1 inbound/bidirectional
Profiles to at most one eligible logical path. EXP-062 separately proves that concrete-path
pinning is technically feasible for a future multi-path extension, but that evidence is
deferred and does not change the Release-1 product envelope.

The lower owner is intentionally separate from the invariant `ip vpn_gate` nft permission
table:

- `stack_return_affinity.py` derives deterministic mark/RPDB allocation and exact ingress
  classifier fragments from current Profile/path/layout facts;
- `linux_stack_return_affinity.py` renders a dedicated
  `ip vpn_gate_return_affinity` PREROUTING owner and exact fwmark RPDB rules;
- reserved affinity RPDB priorities execute before ordinary Profile destination dispatch;
- no physical rule is derived by reclassifying the reply only from its remote address.

The owner is now part of guarded production activation:

- authoritative nft/RPDB observation classifies the reserved owner as absent, exact, stale or
  conflicting;
- only absent/stale state already proven inside the reserved owner namespace may be
  materialized/replaced;
- conflicting/foreign state is never blind-adopted or overwritten;
- mutation is allowed only after a fresh ForwardingGate=DISABLED observation;
- exact postcondition and still-disabled barrier are re-observed after mutation;
- structural policy activation, including forwarding enablement, runs only after affinity
  convergence is confirmed;
- alpha reconciliation includes affinity ownership in its no-op exact-state audit, so affinity
  drift cannot be skipped merely because structural routing/nft state is exact;
- normal stop/restart removes the entire owned managed namespace; failed teardown retains the
  existing fail-closed/lock ownership semantics.

**Evidence:** `EXP-061-result-20261118.md` plus privileged production-owner integration in
`integration_stack_return_affinity_owner.py`.

### Outbound availability stability without per-flow affinity

The earlier outbound gap was created by combining two assumptions: recovery immediately
restored baseline route priority, while established flows were required never to move between
non-equivalent paths. That combination forced a per-flow concrete-path association.

The accepted Release-1 semantics remove the first assumption. When path A fails and B becomes
active, recovery of A produces:

```text
baseline: A > B > C
A fails:  B > C > A(problem)
A recovers, B ordinary and healthy:
          B > A > C
```

No outbound flow lookup needs special affinity to keep using B because ordinary route lookup
still selects B. If B later fails, switching away from B is an actual availability failover;
Release 1 accepts that existing transport/session state may or may not survive that switch.

For an explicit reserve membership the administrator chooses the opposite trade-off:

```text
baseline: A > B:reserve > C
A fails:  B > C > A(problem)
A recovers:
          A > B > C
```

The reserve suffix is Profile-local and changes only failback behavior. It does not alter
Device identity, structural membership or baseline ordering.

Consequently the outbound Release-1 availability path no longer has a per-flow-affinity
readiness gate. Managed-stack return affinity for remote-initiated traffic remains a separate
requirement under `VPNG0002-R2.R6` and is unchanged by this simplification.

# 6. AvailabilityPriorityCalculator

**Component type:** Calculator

**Implements:**
- `VPNG0003-R3.R1`
- `VPNG0003-R3.R2`
- `VPNG0003-R3.R3`
- `VPNG0003-R3.R4`
- `VPNG0003-R3.R4.R1`
- `VPNG0003-R3.R4.R1.R1`
- `VPNG0003-R3.R7`
- `VPNG0003-R3.R8`
- `VPNG0003-R3.R8.R1`
- `VPNG0003-R3.R8.C1`
- `VPNG0007-R7.R1`
- `VPNG0007-R7.R5`

Inputs:

- allowed paths in configured baseline order;
- current established availability-problem paths;
- current active path, if one remains current;
- Profile-local reserve Device IDs; every current path whose `device_id` belongs to that
  subset inherits the reserve role.

Output:

- effective ordered allowed path set.

The Calculator is pure and owns no history. The Manager owns availability confirmation and
the single current-active identity and supplies both explicitly.

Validation is strict for path state: problem and active path identities must belong to
current structural membership. Reserve Device IDs come from the already validated
Profile-local Device membership and may legitimately have no currently bound path. The output
always contains exactly the same structurally allowed path membership. It reorders that membership using the rule in section 4.4; it does not create or
delete policy permission.

# 7. AvailabilityProbeAgent

**Component type:** Agent

**Implements:**
- `VPNG0003-R3.R6`
- `VPNG0003-R3.R6.R1`
- `VPNG0003-R3.R6.R2`
- `VPNG0003-R3.R6.R3`
- `VPNG0003-R3.R6.R3.R1`
- `VPNG0006-R6.R3`
- `VPNG0007-R7.R1`
- `VPNG0007-R7.R3`
- `VPNG0007-R7.R5`

## 7.1. Responsibility

The Agent owns ongoing execution of configured active availability observations.

It owns:

- currently requested normalized observation channels;
- cadence for the selected active-observation mechanism;
- bounded in-flight checks;
- association of each result with the current requested availability-subject identity and
  concrete path observation identity;
- rejection of results that no longer belong to the current observation context;
- local diagnostics about inability to resolve or execute the observation mechanism.

It does not own:

- payload path membership;
- configured route preference;
- availability hysteresis policy outcome;
- effective route order.

## 7.2. Why Agent

Active checking is ongoing observation of an external network condition. The component
does not manage that network condition; it observes it.

Therefore it is an Agent under `design/component-model.md`, rather than a Manager.

## 7.3. Generation token

To implement `VPNG0003-R3.R6.R2`, an in-flight result must carry enough identity to determine
whether it still belongs to the current physical observation context.

The implemented mechanism is a monotonically replaced local observation-generation token
inside one bounded current observation context.

The current context is exactly:

```text
normalized AvailabilityProbeIntent
    -> availability subject = (Profile, logical path)
    -> concrete target
    -> mechanism
current concrete endpoint identity = (ifname, ifindex)
local generation token
```

Reconfiguring the exact same immutable context preserves the token. Subject, target,
mechanism or concrete endpoint replacement creates a fresh generation. Disabling the
observation removes the current context; re-enabling it creates a fresh generation even if
the semantic tuple happens to be identical to the previously disabled one.

The token has no routing-policy meaning. It exists only to reject stale physical results.
No logical evidence epoch, attempt journal, result history or replay ordering is introduced.

`availability_observation_tick.py::run_availability_observation_tick` is the bounded external-wakeup composition for ongoing observation: it synchronizes current subjects, runs at most one exact-readiness-gated attempt per subject, applies only returned fresh evidence, and returns the resulting effective Profile order. It does not schedule itself or retry within the tick; cadence remains a local outer-runtime parameter.

The executable bounded reference uses
`probe_runtime.py::AvailabilityProbeAgent` for one subject context and
`probe_runtime.py::AvailabilityProbeRuntime` as the bounded multi-channel implementation of
the same Agent role. The runtime retains one child context owner per subject seen under the
accepted static configuration so path disappearance disables the context without resetting its
generation counter; reappearance therefore cannot make an old in-flight result equal a fresh
context. This retained set is bounded by the configured Profile/path identity space and is not
an observation history.

**Implements:**
- `VPNG0003-R3.R6.R2`
- `VPNG0007-R7.R1`

## 7.4. User-defined check criterion and normalized target

**Implements:**
- `VPNG0003-R3.R6.R3.R1`

**Constrained by:**
- `VPNG0003-R3.R6.R3.R1.C1`

The product does not attempt to define one universal semantic "VPN path is good" predicate.

The user selects availability at Profile scope. A Profile may disable active checking,
select the reusable default description of each corresponding Device, or provide its own
description in the same canonical shape.

The probe runtime boundary receives only normalized requests:

```text
AvailabilityProbeIntent:
    availability_subject_id
    logical_path_id
    mechanism = icmp
    target = concrete IPv4
```

Therefore `AvailabilityProbeAgent` and `ActiveProbeDriver` receive only the resolved
subject-specific description and do not know whether it came from Device default or Profile
override.

Current accepted semantics:

1. absent Profile availability selection -> no active probe;
2. Profile description -> use that concrete description for each Profile/path subject;
3. Profile `default` -> use the corresponding Device default description for that subject;
4. missing Device default while `default` is selected is a configuration error;
5. no runtime target inference from interface/peer/routing observations is performed.

Description resolution remains above probe runtime and outside `VPNPathAdapter` policy.

Once a concrete target exists, evidence semantics remain user-relative:

```text
reply to the configured/normalized criterion -> positive evidence
valid check with no reply                    -> negative evidence
local execution failure                      -> no_evidence + diagnostic
```

`ProbeTechnicalObservation` carries only those three technical facts. The Agent emits
`AvailabilityOutcome` only when the completed attempt's immutable context still equals the
current context. A late result from a superseded generation emits no evidence at all; it is
not converted into `no_evidence`, because even that outcome belongs to the old context.

The availability subject, concrete target and concrete endpoint generation are therefore all
part of the observation context. Subject/target/path-binding change invalidates in-flight
results from the preceding context.

Future TCP/UDP/HTTP checks may add Driver implementations behind the same normalized
criterion contract, but they are not first-release capabilities.

# 8. ActiveProbeDriver

**Component type:** Driver

**Implements:**
- `VPNG0003-R3.R6`
- `VPNG0003-R3.R6.R1`
- `VPNG0003-R3.R6.R3`
- `VPNG0003-R3.R6.R3.R1`
- `VPNG0003-R3.R6.R3.R1.C1.R1`
- `VPNG0007-R7.R3.R2`
- `VPNG0007-R7.R5`

The Driver provides a narrow technical operation:

```text
check(concrete path observation identity, configured mechanism)
    -> technical observation result
```

It hides mechanism-specific execution from the Agent.

For the first release, the concrete supported Driver mechanism is ICMP echo.

The Driver executes one ICMP check through the concrete current VPN path toward the resolved
target and reports technical reply/no-reply/local-error facts. The Agent maps those facts to
`positive/negative/no_evidence` according to the criterion contract.

The EXP-067-backed Linux Driver proves numeric one-packet ICMP exit semantics under the
dedicated probe UID. Historical EXP-022/023 established that path-specific execution must bind
the attempt with `ping -I <current-ifname>`; the current NG3 Driver preserves that binding.
The recovered `oif` RPDB discriminator plus bound Driver execution are part of the accepted
multi-path path-selection mechanism and are exercised by the continuous availability path.

The reply deadline and outer process grace are finite lower runtime parameters, not
Release-1 user-facing availability knobs or latency guarantees. The outer process deadline
ensures an execution failure cannot leave one attempt indefinitely in flight.

Current technical mapping is:

```text
ping exit 0 -> reply
ping exit 1 -> no_reply
other exit / spawn timeout or failure -> local_error + bounded diagnostic
```

This mapping was proven while the process was selected by the dedicated probe RPDB and
admitted through the EXP-066 local nft owner, not through unrestricted ambient routing.

The executable Driver is `icmp_probe_driver.py::LinuxIcmpProbeDriver`.

TCP, UDP, HTTP and protocol-native liveness remain future possible Driver implementations,
not current capabilities.

## 8.1. Linux probe-plane implementation evidence boundary

Historical experiments still constrain the Linux ICMP implementation, but fresh conntrack
identity for every physical interface generation is no longer a Release-1 correctness goal
by itself.

Reusable evidence:

- EXP-024 proved on privileged CI and Debian 13 target that a probe process can be isolated
  selectively inside the shared managed namespace by capturing process identity on OUTPUT
  and carrying it into reverse INPUT through a dedicated conntrack mark;
- EXP-024 also disproved `meta skuid` on INPUT as a usable receiving-socket discriminator;
- EXP-025 proved on privileged CI and Debian 13 target that a marked ICMP conntrack entry can
  survive interface replacement and be inherited by a later probe that reuses the same
  tuple/ICMP identifier;
- EXP-026 proved in privileged CI that deleting the dedicated probe conntrack class by mark
  breaks that inheritance while preserving differently marked control state.

EXP-025 demonstrates a real lower-level identity imperfection, but it does not demonstrate
that a stale probe entry can synthesize a payload packet, migrate an established payload flow
to another logical path, or by itself create an ICMP reply. The availability product semantics
already contain two stronger boundaries:

- an observation result is accepted only for the current availability subject/path/target
  context;
- one isolated positive/negative observation does not immediately change effective preference
  because degradation/recovery use bounded confirmation accumulation.

The accepted Release-1 decision is therefore **not** to require probe-class conntrack cleanup
merely to guarantee a fresh technical conntrack identity for every probe generation.
EXP-026 remains useful mechanism evidence and optional future hardening, but its target
confirmation is not a prerequisite for Release-1 ICMP availability.

The implementation must instead preserve the product-relevant isolation invariants:

```text
probe-local state
    must not select or migrate payload routing

probe routing discriminator / table
    must remain disjoint from payload and established-flow affinity ownership

probe conntrack mark
    must never be generically restored into a forwarded payload packet mark

probe result
    must still belong to the current subject + logical path + target context
```

The probe owner remains confined to local `stack_output` / `stack_input` semantics and its
separate probe-routing resources. Stack established-flow affinity restores only explicitly
allocated payload-affinity marks at the host-boundary ingress; it does not perform a generic
`ct mark -> packet mark` restore for arbitrary connection marks.

A namespace-wide conntrack flush remains unacceptable. If later evidence shows that stale
probe state can violate payload path affinity, escape the selected probe path, or cause a
material availability failure not absorbed by the accepted confirmation semantics, EXP-026
or another narrow invalidation mechanism may be re-entered.

The former implementation deferral is retained as a historical decision record in
`design/deferrals/NG3-probe-local-system-materialization.md`; it no longer blocks ordinary
Release-1 ICMP probe materialization.


## 8.2. Probe network preconditions and shared lower policy boundary

**Implements:**
- `VPNG0003-R3.R6`
- `VPNG0003-R3.R6.R1`
- `VPNG0003-R3.R6.R2`
- `VPNG0004-R4.R1`
- `VPNG0004-R4.R2`
- `VPNG0004-R4.R5`
- `VPNG0007-R7.R3`
- `VPNG0007-R7.R3.R1`
- `VPNG0007-R7.R3.R2`

A path-specific availability observation is valid only when its local network preconditions
ensure that the probe is actually constrained to the intended path and cannot silently escape
through another Device or ordinary routing.

The availability side owns the semantic lifecycle/readiness of those observation
preconditions:

```text
active normalized availability channels
        ->
required probe-owner network policy
        ->
shared lower NetworkPolicyAdapter / Executor
        ->
verified probe execution precondition
        ->
physical probe attempt

The executable read-only gate is
`probe_precondition.py::verify_probe_execution_precondition`. It verifies the complete
current probe route/RPDB desired state and probe-local nft desired state against one
`StructuralPolicyPhysicalSnapshot`; an attempt is not execution-ready unless both comparisons
are exact. The verifier performs no repair or probe I/O.

One physical attempt is executed through
`probe_attempt.py::execute_probe_attempt_once`. It requires a confirmed readiness value containing the exact execution-context key
`(owner, mechanism, target, endpoint identity)` and whose interface snapshot still contains
that endpoint before invoking the Driver. It performs no scheduling or retry. If the
Agent context changes while Driver I/O is in flight, the existing generation equality gate
rejects the returned observation as stale rather than emitting evidence for the new context.


```

This does not turn `AvailabilityProbeAgent` into the owner of the remote network condition.
The Agent still observes that external condition; it may use lower Machinery to prepare and
verify its local measurement environment.

Payload-policy and probe-policy desired state are distinct semantic owner scopes even when
they share the same lower Linux realization boundary.

The lower network-policy contract must therefore preserve owner identity/scope and reject or
fail closed on unsafe inter-owner conflict before physical application.

A separate physical `ProbeRulesAdapter` is not introduced merely to preserve ownership.
The shared Adapter may realize both owners as long as its semantic contract keeps them
distinct.

When no enabled observation channel requires a probe-owner policy scope, that scope is
removed through the same verified cleanup boundary rather than being left as implicit
ambient state.

## 8.3. Pure probe network-policy projection

**Implements:**
- `VPNG0003-R3.R6`
- `VPNG0003-R3.R6.R1`
- `VPNG0003-R3.R6.R2`
- `VPNG0003-R3.R6.R3`
- `VPNG0003-R3.R6.R3.R1`
- `VPNG0003-R3.R6.R3.R1.C1.R1`
- `VPNG0004-R4.R6.R1.R5`
- `VPNG0004-R4.R6.R1.R5.R1`
- `VPNG0007-R7.R1`
- `VPNG0007-R7.R3.R2`

Once availability-description resolution has produced a concrete current description, the
lower probe policy is a pure projection. It does not choose the description and it does not
execute the observation:

```text
AvailabilityProbeIntent:
    owner = (profile_id, logical_path_id)
    target = concrete IPv4

+ current RoutePriorityPathRoute(logical_path_id)
+ ProbePolicyAllocation(owner)
+ lower probe process selector / conntrack mark
        ->
ProbeNetworkPolicyDesiredState
```

For the accepted Linux Release-1 ICMP mechanism the desired state contains:

```text
dedicated probe table:
    target/32 -> exact current path realization
    default   -> terminal blackhole

RPDB — required path-specific selector shape from EXP-022/023:
    probe process uid + ipproto icmp + exact target + exact current oif
        -> dedicated probe table

The executable ProbeRuleSpec, observer/comparison contract and Linux renderer include the
exact current oif discriminator. The ICMP Driver also binds execution with
`ping -I <current-ifname>`, so multiple logical paths sharing one target remain physically
distinguishable rather than collapsing onto uid+target alone.

stack_output:
    probe process uid + exact current oif + exact target + ICMP
        -> set dedicated probe conntrack mark
        -> accept

stack_input:
    exact current iif + exact remote source + ICMP + probe conntrack mark
        -> accept
```

The executable pure assembly boundary is
`probe_desired.py::build_probe_desired_assembly`. It composes
`AvailabilityDescriptionResolver`, `ProbeRoutingDemand`, the shared
`allocate_network_policy_layout` call and `build_probe_network_policy_desired_state`.
Payload and probe allocations are therefore selected in one layout operation rather than by
independent allocators.

The UID and conntrack mark are lower Linux allocation values. They are not user-facing
availability semantics and are not stored in `AvailabilityProbeIntent`. The supplied probe
UID must identify the dedicated probe worker rather than generic root/controller traffic;
using UID 0 as the process discriminator would not satisfy the accepted selective
probe-process isolation boundary.

This projection intentionally keeps routing and local admission owner-scoped and separate from
payload dispatch. It does not restore the probe conntrack mark into packet routing state and
does not require EXP-026 cleanup. The current Linux lower layer verifies and reconciles both
the route/RPDB owner and the probe-local nft owner against exact desired state, removing stale
owned state when the current owner/path/target set changes.

The executable pure reference is `probe_policy.py`. The current RPDB rule projection
includes the historical EXP-022/023 `oif` discriminator in addition to the EXP-065-proven
uid/ipproto/target fields. The earlier reduced-selector defect is retained only as historical
evidence in `NG3-2026-11-19-probe-path-discriminator-broken-review.md`; it is not an active
implementation state.

EXP-066 continues to supply current nft local-owner representation evidence. No normative
availability requirement is changed by this correction.

EXP-066 additionally confirms the exact-current-interface observation boundary for local nft
rules: when a rule was created against `path0` at one ifindex and that interface was deleted
and recreated with the same name at another ifindex, nft JSON exposed the rule's old raw
ifindex rather than resolving it to the new interface. The probe-local observer therefore
classifies same-name/new-ifindex rules as stale using the same current `InterfaceIdentity`
discipline as the rest of NG3.

## 8.4. Probe-local nft owner convergence

**Implements:**
- `VPNG0003-R3.R6`
- `VPNG0003-R3.R6.R1`
- `VPNG0003-R3.R6.R2`
- `VPNG0003-R3.R6.R3`
- `VPNG0003-R3.R6.R3.R1`
- `VPNG0003-R3.R6.R3.R1.C1.R1`
- `VPNG0007-R7.R3.R2`

Probe-local admission is one classified owner inside the existing `ip vpn_gate`
`stack_input` / `stack_output` chains. It does not get a private nft table, Manager or
lifecycle.

The authoritative comparison decodes only rules carrying the dedicated probe-local owner
comment and requires the exact EXP-066 expression shape. Current-interface identity is
resolved from the same link-bracketed inventory used by the composite nft observer. A raw
numeric interface operand left behind after interface replacement is retained as stale
physical identity rather than being rebound by name.

The semantic `ProbeLocalRuleSpec` includes `(Profile,path)` owner identity for traceability,
but that identity is deliberately not encoded into nft. If multiple semantic probe subjects
project to an identical physical admission rule, the desired local owner is the set-union of
that physical key rather than duplicate nft accepts. The physical key is:

```text
hook
current endpoint identity
target/source address
dedicated probe conntrack mark
dedicated process uid on OUTPUT only
```

Reconciliation uses one owner-specific full-diff nft batch:

```text
delete all stale probe-local handles
add all missing unique physical probe-local rules
```

This follows the existing local publication/integration atomic pattern. Since
`ip_forward=0` does not protect local traffic, stale probe-local accepts are removed before
payload cleanup. Missing probe-local admission is installed only after payload structural
additions and the other local-owner additions already ordered by the composite planner.

The executable owner is split narrowly:

- `probe_local_observation.py` — EXP-066-backed decode/comparison;
- `probe_local_mutation.py` — pure full-diff step;
- `linux_probe_local.py` — handle deletion and exact nft rendering;
- existing `composite_nft_*` — whole-table ownership, ordering, forwarding barrier and fresh
  postcondition checks.

No packet-mark restoration or conntrack cleanup is introduced by this owner.

## 8.5. Probe route/RPDB fail-closed convergence

**Implements:**
- `VPNG0003-R3.R6`
- `VPNG0003-R3.R6.R1`
- `VPNG0003-R3.R6.R2`
- `VPNG0003-R3.R6.R3`
- `VPNG0003-R3.R6.R3.R1`
- `VPNG0003-R3.R6.R3.R1.C1.R1`
- `VPNG0007-R7.R3.R2`

Probe route/RPDB state is reconciled independently from payload forwarding. The owner uses
its dedicated table and RPDB pools and never relies on the global payload ForwardingGate to
make an incomplete probe table safe.

The safety invariant is local to probe dispatch:

```text
an installed probe RPDB selector
    -> may point only at an exact current probe table

a probe table whose routes are being repaired
    -> has no installed selector until repair is complete
```

Therefore a route-table drift may require temporary withdrawal of an otherwise semantically
correct current probe rule. This is fail-closed: probe execution loses that route selector
until the table is exact again.

The one-step planner order is:

```text
selector pointing into a drifted table
    -> withdraw

other stale selector
    -> withdraw

missing terminal guard
    -> add

stale path route
    -> delete

stale terminal guard
    -> delete

missing exact target/path route
    -> add

missing desired selector
    -> add only after route state is exact
```

A simple count of missing/stale objects is not a valid convergence metric because
withdrawing a currently correct selector intentionally creates one missing desired rule while
improving safety. Probe convergence therefore uses a lexicographic safety rank:

```text
(
    installed selectors pointing at drifted tables,
    route differences,
    stale selectors,
    missing desired selectors,
)
```

Every successful one-step mutation must expose a strictly lower fresh rank. The bounded
transaction has no retry-on-error loop; an inter-attempt rank increase is a regression and
terminates the transaction.

Observation is link-bracketed around the shared whole-reserved route/RPDB inventory so
same-name/new-ifindex replacement cannot be silently adopted during convergence.

Executable contracts:

- `probe_routing_plan.py` — fail-closed step selection and safety rank;
- `probe_routing_convergence.py` — fresh one-step postcondition and bounded transaction;
- `linux_probe_routing.py` — link-bracketed observation plus EXP-065-backed exact mutation.

This coordinator only establishes the route/RPDB precondition for one probe attempt. It does
not schedule ICMP, resolve Profile/Device availability descriptions, own availability
confirmation or change payload route preference.

# 9. NetworkPolicyAdapter

**Component type:** Adapter

**Implements:**
- `VPNG0001-R1.R1`
- `VPNG0004-R4.R2`
- `VPNG0004-R4.R3`
- `VPNG0004-R4.R5`
- `VPNG0005-R5.R2`
- `VPNG0005-R5.R3`
- `VPNG0005-R5.R4`
- `VPNG0007-R7.R3`
- `VPNG0007-R7.R3.R2`
- `VPNG0007-R7.R5`

The Adapter is the shared boundary from owner-scoped semantic network policy into the lower
network-policy domain.

Current semantic owners include at least payload policy and probe-observation policy. Sharing
the physical Adapter does not merge those owners.

Its contract must express semantic operations such as:

```text
observe current owned policy state
apply desired semantic policy and verify postcondition
cleanup owned policy and verify absence
```

The upper Manager must not know:

- route-table allocation;
- route-owner protocol identifiers;
- rule priorities;
- physical gateway/onlink representation of a bound logical path;
- nft syntax;
- sysctl syntax;
- kernel command ordering;
- transaction scratch structures.

Those details belong below the Adapter boundary unless a future product requirement makes
one observable.

### 9.1. Semantic-to-physical route-priority realization boundary

`PayloadProfileRequest` is intentionally insufficient to construct an iproute2 command by
itself.

It contains semantic policy:

```text
profile_id
direction
destinations[]
ordered logical paths[]
```

The physical pure-priority backend additionally needs lower realization data:

```text
route-key destination / internal routing domain
logical path -> current RoutePriorityPathRoute
    current endpoint identity
    gateway?
    onlink
internal table allocation
internal route-owner protocol
owned working metric space
```

These lower values are **not** derived by PayloadTrafficManager and are not added to the
human configuration merely because the Linux backend needs them.

The NetworkPolicyAdapter/lower realization layer must combine:

- the Manager's semantic Profile/path order;
- current verified path binding/transport realization;
- internal owned-resource allocation;

into the physical route-key domain requests consumed by NetworkPolicyExecutor.

A missing or ambiguous physical realization for an otherwise allowed logical path is not
permission to invent a gateway, use ambient routing, or drop that path silently. It moves
the affected lower policy out of the pure-priority path and must remain fail-closed /
unconfirmed until structural realization/reconciliation can establish the required state.

This boundary also means that current `RoutePriorityPathRoute`, table/protocol values and
metric working space are lower internal contracts/evidence, not new product knobs.

The executable lower realization contract represents that internal data as:

```text
RoutePriorityDomainRealization:
    RoutePriorityDomainId
    table
    owner_protocol
    path_routes[]
    RoutePriorityMetricSpace

RoutePriorityMetricSpace:
    preference_slots[]  # strictly increasing Linux metrics
    scratch_metrics[]   # disjoint owned working space
```

Semantic `ordered_paths` are mapped to `preference_slots` in order. Because Linux prefers
the lower route metric, the preference slots must be strictly increasing numerically.
Multi-path realization requires at least one disjoint scratch metric so a cyclic permutation
can preserve make-before-break behavior.

The contract validates the internal representation but intentionally does not choose table,
protocol or metric values. Their allocation remains a lower Adapter responsibility.

That allocation must not be designed as an isolated priority-only namespace. Table IDs,
route-owner protocol, rule priorities and metric ownership are part of the same lower
network-policy ownership layout that will also realize structural routing/RPDB/filtering
state.

Therefore the next allocator unit is gated by the structural lower-policy layout:

- it may reserve/derive internal identifiers deterministically;
- it must keep owner scopes unambiguous for observation, mutation and cleanup;
- it must prevent collisions between independent Profiles/domains and probe/payload owner
  scopes;
- it must provide enough owned metric space for the accepted make-before-break algorithm;
- it must not reuse historical NG1/NG2 constants merely because they existed;
- it must remain entirely below the human-facing configuration contract.

The existing realization types are consumers of that future allocation contract, not the
authority that chooses global Linux resource namespaces.

### 9.2. Shared lower network-policy ownership/allocation layout

**Implements:**
- `VPNG0001-R1.R1`
- `VPNG0003-R3.R6`
- `VPNG0004-R4.R1`
- `VPNG0004-R4.R1.R1`
- `VPNG0004-R4.R2`
- `VPNG0004-R4.R5`
- `VPNG0004-R4.R6.R1.R1`
- `VPNG0005-R5.R2`
- `VPNG0005-R5.R4`
- `VPNG0005-R5.R5`
- `VPNG0007-R7.R1`
- `VPNG0007-R7.R3`
- `VPNG0007-R7.R3.R1`
- `VPNG0007-R7.R3.R2`

The lower Linux policy namespace is allocated from **semantic owner scopes**, not from
user-visible identifiers copied directly into kernel object names.

Current owner kinds are:

```text
PayloadPolicyOwner(profile_id)

ProbePolicyOwner(
    availability_subject_id = (profile_id, logical_path_id)
)
```

The owner key is semantic identity. Kernel resource numbers are internal realization.

#### Routing-table ownership

Each enabled payload Profile owns one internal routing table even when its current concrete
path set is empty. Keeping the table/domain present preserves the accepted rule that a
zero-path Profile remains a fail-closed policy domain instead of disappearing into ambient
routing.

A Profile table contains the structural routes for all of that Profile's remote
destinations plus a terminal fail-closed route. Pure-priority convergence mutates only the
ordinary path-route metrics inside that already-selected table.

Probe policy does not automatically receive one table per subject merely because the owner
exists. A probe-owner table is allocated only when the accepted physical probe mechanism
needs an independent path-routing domain. This keeps owner identity explicit without
pre-allocating unused kernel machinery.

Payload and probe table allocations come from disjoint lower resource pools.

#### RPDB ownership

Payload dispatch rules are generated from the normalized `(destination, Profile)` set and
are ordered deterministically by:

```text
prefix length descending
network address ascending
Profile ID ascending only as a final deterministic tie-break
```

Exact duplicate destination ownership is already rejected by configuration normalization,
so the final tie-break does not create policy semantics.

The payload RPDB pool must execute before ambient/main lookup for managed host-boundary
traffic. Probe rules, when required by the selected probe mechanism, use a disjoint
higher-precedence owner pool and an explicit probe discriminator; they do not reuse payload
dispatch identity.

Rule priority numbers are internal allocation, not configuration.

#### Route ownership markers

Linux route protocol values are role markers, not Profile/subject identifiers.

The lower platform contract reserves distinct marker roles for:

```text
managed path/unicast route
managed terminal/guard route
```

The exact numeric protocol values are platform constants and must be evidence-gated before
production use. Historical 201/202 behavior is reusable evidence but does not by itself make
those numbers an NG3 normative choice.

Owner scope is determined by the combination of allocated table/domain, route role/shape and
semantic allocation record. A protocol marker alone is never sufficient proof that an
arbitrary route may be deleted.

#### Metric ownership

For a payload Profile with `N` currently realized paths, the lower allocation supplies:

```text
N strictly increasing preference metrics
>= 1 disjoint scratch metric when N > 1
one terminal guard metric lower in preference than every preference/scratch metric
```

Availability changes only permute which already-eligible logical path owns each preference
slot. They do not allocate a second availability-specific metric namespace.

A zero-path Profile requires no preference/scratch metrics but still retains its terminal
fail-closed route.

The allocator must reject an unrepresentable path count before mutation. It must not silently
truncate paths or reuse a guard metric as scratch space.

#### nftables ownership

Packet filtering/NAT realization uses a dedicated VPN-GATE-owned nftables namespace inside
the managed network domain.

Payload and probe policy remain separate semantic owner scopes inside that namespace even
when one physical nft table is sufficient.

The lower allocator must not embed arbitrary user IDs directly into nft object names merely
for ownership. Stable internal owner tokens/indices may be used when per-owner objects are
required.

The dedicated nft namespace is cleanup identity for VPN-GATE packet-policy objects. A
pre-existing incompatible object in that reserved namespace is a marker conflict, not a
candidate for silent adoption or deletion.

##### nft namespace ownership marker

The first-release Linux nft namespace has one fixed table identity:

```text
family: ip
table:  vpn_gate
```

Table-name reservation alone is not sufficient evidence that a pre-existing table belongs
to this product.

An owned NG3 table therefore carries one exact versioned table comment:

```text
vpn-gate:ng3:owner-v1
```

The table-level observation states are:

```text
ABSENT
    no table ip vpn_gate exists

OWNED
    exactly one table ip vpn_gate exists
    and its table comment == "vpn-gate:ng3:owner-v1"

CONFLICT
    table ip vpn_gate exists
    but the ownership marker is absent, malformed or different
```

The marker is an ownership prerequisite, not blanket deletion authority.

Even an `OWNED` table must have its contained chains/rules/sets/objects inventoried against
accepted VPN-GATE shapes before cleanup or replacement. Any unexpected contained object
remains an explicit ownership conflict rather than something to delete merely because it
sits inside the marked table.

##### Invariant payload nft scaffold

The first-release payload nft namespace has two invariant base chains whose existence and
metadata do not depend on any particular accepted Device firewall/NAT values.

```text
chain payload_forward
    type filter
    hook forward
    priority 0
    policy drop
    comment "vpn-gate:ng3:payload-forward-v1"

chain payload_postrouting
    type nat
    hook postrouting
    priority 100
    policy accept
    comment "vpn-gate:ng3:payload-postrouting-v1"
```

`payload_forward` owns the final VPN-GATE verdict for IPv4 packets forwarded through the
managed network domain. Its default `drop` is structural fail-closed behavior: an empty
payload policy forwards nothing.

The newly accepted managed-stack default-policy requirements add two further filter hooks:

```text
chain stack_input
    type filter
    hook input
    priority 0
    policy drop
    comment "vpn-gate:ng3:stack-input-v1"

chain stack_output
    type filter
    hook output
    priority 0
    policy drop
    comment "vpn-gate:ng3:stack-output-v1"
```

**Implements:**
- `VPNG0004-R4.R6.R1.R5`;
- `VPNG0004-R4.R6.R1.R5.R1`.

These chains are appliance/control-plane policy, not the user's Device firewall. Required
loopback, probe, publication or integration-specific local exceptions are explicit
VPN-GATE-owned contributions. User Device rules never become arbitrary host `INPUT/OUTPUT`
rules, and these managed-domain hooks do not imply ownership of the ordinary host namespace
firewall.

EXP-040 passed on privileged Linux CI and accepts the exact
`stack_input/stack_output` owner shapes above. Empty DROP chains remained terminal despite
foreign unconditional-ACCEPT base chains before and after priority 0; explicit owned ICMP
allow rules restored the tested local traffic.

The invariant scaffold may therefore include all four accepted base chains
(`stack_input`, `payload_forward`, `stack_output`, `payload_postrouting`).
System/local allow contributions remain a separate policy unit and are not implied by the
scaffold itself.

##### Managed local/system allow policy

**Implements:**
- `VPNG0004-R4.R6.R1.R5`;
- `VPNG0004-R4.R6.R1.R5.R1`;
- `VPNG0001-R1.R2.R4.R6.R3` where a supported Device publication requires local transport traffic;
- `VPNG0001-R1.R3.C1.R1` for integration-specific local control traffic explicitly required by a supported onboarding contract.

The managed `stack_input` / `stack_output` exception layer is compiled only from explicit
VPN-GATE-owned **local/system allow intents**. It is not a second user firewall and it must
not derive permissions from Device firewall `ALLOW` rules.

A normalized contribution has this semantic shape:

```text
LocalSystemAllowIntent
    owner_function
        = loopback
        | probe
        | publication(device_id)
        | integration(integration_id)
    hook = input | output
    protocol
    current_interface_identity?
    source_prefix?
    destination_prefix?
    source_port?
    destination_port?
    peer_or_endpoint_identity?
```

Every field is a semantic selector, not raw nft syntax. A contribution is valid only when its
`owner_function` is backed by an already accepted product/integration need and every selector
required to prevent scope broadening is known. Unknown lower facts produce no wider fallback
rule.

The desired policy is the set-union of normalized contributions after canonical
deduplication. Composition does not introduce ordering semantics between independent
contributions: each contribution is a positive exception to the chain's terminal DROP.
A rule compiler may combine mechanically equivalent selectors only when packet acceptance is
provably unchanged.

The following are forbidden as implicit defaults:

- blanket `accept` in either local chain;
- blanket `ct state established,related accept` covering unrelated local traffic;
- acceptance based only on an interface name when current interface identity is required;
- publication wildcarding beyond the normalized Device publication intent;
- probe acceptance broader than the exact probe flow contract;
- copying Device firewall rules into `stack_input` or `stack_output`.

Lifecycle ownership follows the source intent. If a publication, probe path or supported
integration disappears from current desired state, its local/system contribution becomes
stale and must be removed through the same observe/compare/converge discipline as other owned
nft state. A stale contribution never remains merely because it would be harmless.

The policy Calculator therefore has a bounded responsibility:

```text
accepted current product/integration intents
    + current verified lower identities required by those intents
        -> desired LocalSystemAllowIntent set
```

The existing nft realization boundary is responsible only for compiling that desired set,
observing owned rules, classifying exact/missing/stale/conflicting state and converging to the
supplied desired state. It must not invent missing local permissions.

This unit deliberately does **not** define a universal fixed exception list. Exact loopback,
probe, publication and integration contributions are admitted only when the corresponding
already-supported function reaches its own bounded implementation unit and can provide the
necessary selectors. This keeps `INPUT=DROP` / `OUTPUT=DROP` fail-closed semantics intact
without manufacturing new product behavior.

###### Supported VPN integration local/system contribution — EXP-049 closure

EXP-049 first proved that a real in-stack userspace VPN needs explicit local transport
permission, then reran successfully after that permission was materialized through the normal
production convergence boundary.

The normalized first-release contribution is:

```text
IntegrationLocalTransportIntent
    integration_id
    protocol = tcp | udp
    current host-boundary InterfaceIdentity
    exact managed local IPv4
    exact remote IPv4
    exact remote port
    optional exact local port
```

Its desired lower shape is:

```text
stack_output:
    exact current host-boundary oif
    exact local saddr
    exact remote daddr
    exact remote dport
    [exact local sport when known]
    accept

stack_input:
    exact current host-boundary iif
    exact remote saddr
    exact local daddr
    exact remote sport
    [exact local dport when known]
    otherwise ct state established,related
    accept
```

The dynamic-local-port INPUT form is therefore not a blanket established-flow exception:
remote endpoint, remote port, local address and current boundary identity remain exact.

The owner class participates in the same whole-scope observe/compare/converge machinery as
other NG3 nft policy. It has explicit missing/stale/conflict classification, current interface
identity, atomic stale-delete/missing-add mutation, and no ambient-socket inference.

EXP-049 proves this shape with OpenVPN 2.6.14: exact UDP transport remains usable while
unrelated ICMP underlay traffic remains blocked by terminal local DROP.

###### Publication local/system contribution — EXP-046

Transport publication is the first function that has reached that bounded lower unit.

EXP-010/011 already establish the publication topology and real OpenConnect same-port
TCP/UDP transport. EXP-046 separately proves the exact managed local firewall contribution
for an already-normalized internal publication endpoint.

For one current host-boundary identity, exact managed local IPv4 address, transport protocol
and internal port, desired contribution is:

```text
stack_input:
    current host-boundary iif
    ip daddr = exact local publication IPv4
    tcp|udp dport = exact internal port
    accept

stack_output:
    current host-boundary oif
    ip saddr = exact local publication IPv4
    tcp|udp sport = exact internal port
    accept
```

No blanket `ct state established,related` exception is required.

EXP-046 proves real TCP and UDP request/response with both local base chains terminal-DROP.
Wrong port remains blocked, and the same endpoint/port arriving through a Device-side
interface remains blocked. The accepted lower owner marker is:

```text
vpn-gate:ng3:local-publication-v1
```

The internal `PublicationLocalEndpointIntent` is not external config grammar. It carries
only already-normalized publication facts plus the current host-boundary identity. Its
projection produces one INPUT and one OUTPUT contribution and set-deduplicates identical
physical rules across Devices.

The strict publication-local observer/comparator:

- decodes only rules carrying the publication owner marker;
- requires exact chain/direction, interface generation, local IPv4, protocol, port and
  plain `accept`;
- classifies same-name/old-ifindex contributions as stale;
- detects duplicate/malformed owned rules;
- grants no mutation authority.

The composite nft owner comparison now recognizes exact publication-local rules in addition
to Profile forward, Device firewall and payload NAT. Unknown `stack_input` /
`stack_output` rules remain whole-scope conflicts.

###### Publication local/system mutation — EXP-047

The managed IPv4 ForwardingGate is **not** a safety barrier for locally delivered
`stack_input` / `stack_output` traffic. Local publication mutation therefore has its own
lower safety primitive rather than inheriting payload-policy assumptions.

EXP-047 proves that one `nft -f -` batch is transactional for the publication-local owner
class:

- exact INPUT/OUTPUT additions become visible only when the whole batch commits;
- an invalid later command rolls back an earlier valid command from the same batch;
- exact-handle INPUT/OUTPUT deletion may be submitted in one transaction;
- the transaction leaves Profile forward / Device firewall / payload NAT objects untouched.

The lower desired state enforces a complete pair for every publication endpoint:

```text
one normalized publication endpoint
    -> exactly one stack_input rule
    -> exactly one stack_output rule
```

A partial physical pair is drift, not a legal desired state.

`select_local_publication_step` computes one atomic **full diff** across the publication-local
owner class:

```text
all observed stale publication-local handles
    + all missing exact desired publication-local rules
        -> one nft transaction
```

No old->new endpoint identity is inferred. Handles are ephemeral references from the current
fresh observation and include their exact hook/chain identity. There is no persistent handle
registry.

The Linux publication Driver renders only EXP-046-backed rule shapes and applies the whole
diff in one nft transaction. Fresh exact observation remains the postcondition authority.

The composite whole-table planner now includes publication-local state. Its safety ordering is:

```text
cleanup:
    stale local publication accepts
    -> stale Profile positive admission
    -> stale Device jump
    -> stale Device child
    -> stale NAT

addition:
    missing NAT
    -> missing Device child/jump
    -> missing Profile positive admission
    -> missing local publication full diff
```

The publication-local add is deliberately last because it is an independent positive local
permission and is not protected by ForwardingGate. Stale local permissions are removed first
for the same reason.

The privileged composite integration proves coexistence of Profile forward, Device firewall,
payload NAT and publication-local rules in one reserved table. It also proves one-step atomic
replacement of an existing publication endpoint rule pair with a new desired pair, followed
by exact whole-scope confirmation.

That historical publication review closed physical local-rule convergence only for Device
transport publication at the time. Probe-local and supported-integration exceptions now have
their own exact lower selector/observer/mutation contracts and participate in the shared
composite nft owner. Loopback remains outside current materialized exception classes.

The probe-local implementation preserves the separate EXP-024/025/026 evidence boundary
described in section 8.1; ordinary Release-1 ICMP probing does not require EXP-026 cleanup.

Concrete payload rules are added only by a fully normalized payload-policy projection. They
must not be inferred from historical TOML examples.

###### Host-side Device server publication mapping — EXP-052

**Implements:**
- `VPNG0001-R1.R2.R4.R6.R3`;
- `VPNG0001-R1.R2`;
- `VPNG0004-R4.R6.R1.R1`;
- `VPNG0004-R4.R6.R1.R5.R1`;
- `VPNG0007-R7.R1`, `VPNG0007-R7.R3`, `VPNG0007-R7.R5`.

One canonical Device publication has two lower postconditions:

```text
normalized publish_vpn_server
    |
    +--> managed-domain local publication admission
    |       EXP-046/047 owner in table ip vpn_gate
    |
    +--> host-boundary publication mapping
            EXP-052-backed separate owner scope
```

The host-boundary mapping is not Profile routing and is not merged into the managed nft
owner. The existing `NetworkPolicyAdapter` boundary gains a separate host-publication
realization sub-contract; no additional Manager/Agent is introduced:

```text
observe HostPublicationOwner
apply desired HostPublicationMapping + fresh verify
cleanup owned HostPublicationOwner + fresh verify absence
```

The pure lower projection consumes only normalized configuration facts. For each publication
it expands the already validated ordered host/internal `PortBundle` values positionally
into exact pairs. It never reparses the user string and never uses declaration order as a
conflict-resolution policy.

One physical host mapping is identified by:

```text
protocol
host selector
host port
current exact managed local publication IPv4
internal port
```

Identical physical mappings may be set-deduplicated. Two contributions that claim the same
effective external protocol/selector/host-port but require different internal targets are an
unrepresentable lower-policy conflict and must not be resolved by rule order.

For the accepted Linux nftables realization, the destination is rewritten only after proving
that the original destination belongs to the host publication surface:

```text
exact host IPv4 selector:
    fib daddr type local
    ip daddr = exact configured IPv4
    tcp|udp dport = exact host port

host-interface selector:
    fib daddr type local
    iifname = configured host interface
    tcp|udp dport = exact host port

omitted selector:
    fib daddr type local
    tcp|udp dport = exact host port

then:
    dnat to <current-managed-local-IPv4>:<exact-internal-port>
```

The `fib daddr type local` predicate is an ownership boundary, not an optimization. EXP-052
proves that without a local-destination gate the broader interface/port shapes would be
capable of capturing unrelated transit, while the accepted shape preserves both selected
publication and same-port foreign transit.

EXP-052 also proves TCP/UDP reverse conntrack translation and preservation of the external
client source at the managed listener. The mechanism therefore does not require a userspace
per-flow publication relay for this reference realization. Historical EXP-010/011 remain
valid topology/real-protocol evidence, not an implementation inheritance requirement.

Host publication and managed local admission are observed independently. Runtime readiness
for a requested publication requires both exact postconditions. Addition ordering places the
host mapping last, after required managed local admission is confirmed. Removal/replacement
removes stale owned host mappings before obsolete managed local admission is relaxed.

The host-side owner may create, observe and remove only its explicitly reserved publication
objects. Foreign host nft/routing state is neither adopted nor deleted.

The DNAT data path requires suitable host forwarding. Current NG3 intentionally does not make
the managed-domain `ForwardingGate` an owner of host-global forwarding state. EXP-052
therefore does **not** authorize this publication sub-contract to write
`net.ipv4.ip_forward` in the ordinary host namespace. The lower runtime may observe the
deployment/integration prerequisite and report publication unready when it is absent.
Changing ownership of host forwarding requires a separate requirement/design decision.

###### EXP-035 — проверка низкоуровневого nft-контракта NEW forwarding

**Implements:**
- `VPNG0002-R2.R1.R2` — remote destination/source определяется направлением NEW flow;
- `VPNG0002-R2.R3.R3` — разрешение инициирования flow зависит от direction;
- `VPNG0002-R2.R5.R1` — most-specific Profile selection нельзя подменять произвольным порядком allow rules;
- `VPNG0001-R1.R3.R2`, `VPNG0001-R1.R3.R3` — физические ingress/egress идентичности должны быть текущими;
- `VPNG0004-R4.R1`, `VPNG0004-R4.R2`, `VPNG0004-R4.R3.R2` — неподтверждённый или ошибочный lower rule не может расширять forwarding.

**Constrained by:**
- `VPNG0002-R2.R3.C1` — первая версия не принимает многопутевой inbound/bidirectional Profile;
- `VPNG0001-R1.R2.R4.R6.C1` — не выводить незакрытую пользовательскую grammar из lower nft синтаксиса.

**Scope:** только технический эксперимент с одной разрешающей rule shape для
host-boundary -> конкретный VPN endpoint: `meta iif` и `meta oif`
по числовым ifindices, точный IPv4 destination prefix, `ct state new`
и `accept`. Проверить nft JSON и фактическое поведение в
одноразовом network namespace с закрывающей `policy drop`.

Это **не** архитектурное принятие полного payload filter policy:
правила return flow, inbound permission, пересекающиеся префиксы с
most-specific конкуренцией, Device firewall и probe isolation остаются
обязанностями отдельной normalized policy projection. Даже если
эксперимент PASS, одиночный allow pattern нельзя публиковать как
полную компиляцию Profile. Его можно использовать как проверенную
lower primitive для последующего проектирования строгого owner
classifier и композиции.

**Components / interactions:** существующий нижний Linux nft
Driver/Adapter выполняет экспериментальные команды; pure
`NftNamespaceObservation` поставляет canonical JSON. Новый runtime
Manager/Agent/Executor, state store и event contract не вводятся.
Эксперимент необходим, потому что exact numeric-ifindex filter match
с prefix и conntrack нельзя считать доказанным только на основании
EXP-033 (тот проверял postrouting masquerade).

**External environment:** GitHub Actions privileged Linux runner,
`iproute2`, `nftables`, `conntrack` и ICMP в disposable namespaces.
Сопоставление с Debian target остаётся отдельной проверкой
совместимости при необходимости, а не обязательным условием
проведения этого эксперимента.

**Simplification / evidence:** один узкий набор rule/negative controls;
проверить hit и отсутствие bypass с иного ingress, иного egress,
вне-prefix traffic и same-name-new-ifindex. Не создавать
обобщённый firewall AST, runtime parse grammar, persistent index map,
retry engine или вторую policy-classification логику.

**Gate:** до PASS эксперимента нельзя считать эту lower-rule shape
платформенно подтверждённой; даже PASS не разрешает materialization
непроверенной полной Profile permission или открытие `ForwardingGate`.

**EXP-035 result:** PASS on privileged GitHub Linux CI. Numeric current
`meta iif/oif` plus `ct state new` and exact IPv4 destination prefix
matched only the intended NEW packet. Different ingress, different egress,
outside-prefix traffic and same-name/new-ifindex replacement did not match.
Current interface operands rendered symbolically; the stale old oif rendered
as a decimal-string ifindex. This evidence accepts the lower primitive only;
full payload filter semantics remain gated as stated above.

###### EXP-036 — проверка prefix-scoped stateful return primitive

**Implements:**
- `VPNG0002-R2.R1.R2` — remote prefix сохраняет одинаковый смысл в обоих направлениях;
- `VPNG0002-R2.R3.R3` — return traffic уже разрешённого flow может обслуживаться statefully;
- `VPNG0001-R1.R3.R2`, `VPNG0001-R1.R3.R3` — обратный packet path привязан к текущей concrete interface generation;
- `VPNG0004-R4.R1`, `VPNG0004-R4.R2`, `VPNG0004-R4.R3.R2` — stale/неподтверждённый return state не должен расширять forwarding.

**Constrained by:**
- `VPNG0002-R2.R3.C1` — Release 1 inbound/bidirectional max-path constraint остаётся;
- `VPNG0001-R1.R2.R4.R6.C1` — lower nft expression не выбирает user grammar.

Для outbound NEW primitive из EXP-035 кандидат stateful reverse primitive
должен быть **prefix-scoped**, а не только `ct state established,related`:
`meta iif = current path`, `meta oif = host boundary`,
`ip saddr = тот же remote prefix`, `ct state established,related`.
Иначе retained conntrack для старого/другого remote prefix мог бы получить
широкое разрешение через тот же interface pair после structural change.

EXP-036 должен проверить реальный bidirectional ICMP flow, отсутствие
разрешения для unsolicited reverse NEW, отсутствие return для remote source
вне prefix даже при отдельно разрешённом outbound NEW test packet, и
same-name/new-ifindex replacement. После замены новый outbound NEW rule
может быть создан для нового oif, но старый reverse rule по old iif не
должен пропустить reply; новый reverse rule должен восстановить flow.

Это по-прежнему **lower primitive evidence**, а не полный filter compiler:
inbound NEW, Device firewall composition, multi-Profile canonical projection
и full owner convergence остаются отдельными units.

**EXP-036 result:** PASS on privileged GitHub Linux CI. The prefix-scoped
reverse rule admitted a real established reply, rejected unsolicited reverse
NEW and an established reply whose remote source was outside the prefix, and
failed closed after same-name interface replacement until a current-ifindex
reverse rule was installed. Actual nft JSON renders the state set as
`["established","related"]`; live/stale interface rendering follows the
same symbolic/decimal-index rule established by EXP-033/035.

###### Authoritative payload_forward observation — design gate

**Component:** read-only direct Calculator over the owned nft table and one fresh,
unambiguous interface inventory.

**Implements:**
- `VPNG0002-R2.R1.R2`;
- `VPNG0002-R2.R3.R3`;
- `VPNG0002-R2.R5.R1`;
- `VPNG0001-R1.R3.R2`;
- `VPNG0001-R1.R3.R3`;
- `VPNG0004-R4.R1`;
- `VPNG0004-R4.R2`;
- `VPNG0004-R4.R5`.

**Constrained by:**
- `VPNG0002-R2.R3.C1`;
- `VPNG0001-R1.R2.R4.R6.C1`.

The observer does **not** compile Profile policy. It only classifies exact
lower rule shapes already proven by EXP-035/036 and preserves the semantic
fields required for a later desired-state comparison:

```text
NEW:
    ct state new
    exact iif
    exact oif
    one remote IPv4 prefix match (saddr or daddr)
    accept
    exact NEW owner comment

RETURN:
    ct state { established, related }
    exact iif
    exact oif
    one remote IPv4 prefix match (saddr or daddr)
    accept
    exact RETURN owner comment
```

Counters used by EXP-035/036 are instrumentation, not required policy.
The production owner shape therefore omits `counter`; accepting arbitrary
counter-bearing rules as production-owned would widen cleanup authority for
no accepted requirement.

Before implementation, EXP-037 must resolve two representation facts:
how nft JSON renders `/32` `ip saddr/daddr` matches, and the exact
no-counter expression arrays. The observer may normalize only evidence-backed
forms. Unknown comment, state set, prefix representation, extra expression,
action or field is an explicit conflict, never silently ignored.

Interface operands follow EXP-033/035/036: current names resolve through the
fresh inventory; decimal ifindices may resolve to a current identity only when
that exact index is present, otherwise remain stale numeric identity.
A same-name replacement never equals the old numeric generation.

**Scenario:** strict owner inventory must be able to distinguish current
recognized payload forwarding objects from stale recognized objects and
unknown/conflicting rules before any structural cleanup or activation.

**Necessity / simplification:** a pure Calculator is required because the
scaffold currently leaves all rules unclassified. No compiler, mutation,
policy ordering, handle cache, event owner, retry loop or firewall AST is
introduced. Rule handles identify observed objects only.

**Evidence plan:** EXP-037 for final no-counter JSON forms and `/32`;
rootless parser regression for NEW/RETURN, saddr/daddr, current/stale
interfaces, malformed state/prefix/comment/action/extra expressions,
duplicate handles and duplicate physical rules; privileged integration reads
the actual EXP-037 rules through the production observer.

**Gate:** EXP-037 is PASS. Implementation of the strict read-only observer is
therefore allowed. Passing the observer unit still does not authorize full
Profile filter materialization.

**EXP-037 evidence:** no-counter NEW/RETURN owner rules contain exactly five
expressions. `/32` remote matches render as a plain IPv4 address string;
non-host prefixes such as the tested `/24` render as a prefix object.
The observer accepts only these evidence-backed canonical forms.

**Gate amendment after EXP-037:** `VPNG0002-R2.R1.R1` permits arbitrary
strict IPv4 CIDR destinations, including `0.0.0.0/0`. EXP-037 closed only
`/32`; EXP-035/036 closed `/24`. Before implementation the observer gate
must additionally resolve nft canonicalization for `/0` and boundary
prefix lengths. EXP-038 is therefore required. If nft optimizes `/0`
by removing the payload-prefix expression, the observer design must be revised
rather than pretending the missing expression is equivalent by assumption.

**EXP-038 result:** PASS on privileged GitHub Linux CI. `/0`, `/1` and

###### Exact payload_forward desired data and actual-vs-desired comparison

**Component:** immutable lower desired data + pure Direct Calculator. This is
**not** the Profile/Device policy compiler.

**Implements:**
- `VPNG0002-R2.R1.R1`;
- `VPNG0002-R2.R1.R2`;
- `VPNG0002-R2.R3.R3`;
- `VPNG0002-R2.R5.R1`;
- `VPNG0001-R1.R3.R2`;
- `VPNG0001-R1.R3.R3`;
- `VPNG0004-R4.R1`;
- `VPNG0004-R4.R2`;
- `VPNG0004-R4.R5`.

**Constrained by:**
- `VPNG0002-R2.R3.C1`;
- `VPNG0001-R1.R2.R4.R6.C1`.

The higher semantic Calculator eventually composes Profile direction/destinations, path
bindings, most-specific Profile selection and the later accepted ordered Device firewall.
This historical lower unit predates that complete composition and therefore remains only the
exact positive Profile NEW/RETURN physical-rule sub-contract; it must not be described as the
complete Device firewall compiler.

This unit defines only one exact physical desired rule:

```text
PayloadForwardRuleSpec:
    kind = NEW | RETURN
    ingress = current InterfaceIdentity
    egress = current InterfaceIdentity
    remote_field = saddr | daddr
    remote_prefix = strict IPv4Network
```

and an immutable `PayloadForwardDesiredState` containing a physically unique
set of such specs. It has no Profile ID, Device ID or rule handle because those
are not part of physical nft rule identity. Semantic provenance remains above
this lower contract.

The comparator takes:

```text
strict observed payload_forward rules
+ one fresh interface inventory
+ exact lower desired state
    ->
confirmed desired specs
missing desired specs
stale recognized physical rules
conflicts
```

A recognized current-identity rule that is not in desired state is `stale`,
not confirmed. A stale-interface-generation rule is also `stale`. Any
observer conflict remains a conflict. Desired rules whose endpoints are not
present in the same current interface inventory are invalid input rather than
permission to add a rule to an unverified endpoint.

**Necessity / simplification:** this comparison is required before safe cleanup
or physical materialization, but it deliberately avoids creating a second
Profile classifier or pretending to represent the later ordered Device firewall semantics. No I/O, mutation,
stored handles, retry state or lifecycle component.

**Evidence:** rootless exact comparison tests over NEW/RETURN, duplicate desired
physical rules, unexpected recognized current rules, stale numeric generations,
missing rules, conflicts and non-current desired endpoints. Existing live
observer evidence remains sufficient; no new kernel fact is introduced.

**Gate:** PASS for lower desired data/comparison only. Full semantic compilation
and physical filter mutation remain separate gated units.

###### Forward semantic compiler — implemented pure Calculator

**Implements:** `VPNG0002-R2.R1.R2`, `VPNG0002-R2.R3.R3`,
`VPNG0002-R2.R5.R1`, `VPNG0001-R1.R2.R4.R6.R2`,
`VPNG0004-R4.R1`, `VPNG0004-R4.R3.R2`.

A naive union of Profile CIDR allow rules is not equivalent to accepted
most-specific classification. Example: a broad outbound Profile may allow
path B while a more-specific outbound Profile owning the packet allows only
path A. If the broad rule remains `daddr broad + oif B -> accept`, routing
drift or a mixed transition could forward the more-specific packet through B,
even though the selected Profile forbids that path.

The positive-only/default-drop lower model therefore requires the semantic
compiler to produce **disjoint effective remote-prefix fragments** before
creating physical allow rules:

- outbound: partition remote IPv4 space across all outbound/bidirectional
  candidate Profiles by the accepted global most-specific rule, then attach
  only the selected Profile's allowed paths to each fragment;
- inbound: for each concrete ingress logical path, first restrict candidates
  to inbound/bidirectional Profiles allowing that path, then partition remote
  source space by most-specific Profile for that path;
- return rules use the same selected fragments with reversed interface roles
  and the reverse remote field.

With disjoint fragments, all lower rules remain positive accepts under the
default-drop chain and rule order stays semantically irrelevant, matching the
accepted unordered `PayloadForwardDesiredState`.

The executable Calculator is `payload_forward_compiler.py`:

```text
PayloadProfileRequest set
+ exact current logical-path -> RoutePriorityPathRoute realization
+ current host-boundary InterfaceIdentity
    ->
PayloadForwardDesiredState
```

It reuses the accepted outbound and per-ingress inbound prefix partitions rather than
reimplementing most-specific selection.

For each outbound fragment/path it emits NEW `host -> path` with destination-prefix match
and RETURN `path -> host` with source-prefix match. For each inbound fragment after
ingress-path restriction it emits NEW `path -> host` with source-prefix match and RETURN
`host -> path` with destination-prefix match.

Zero-path Profiles emit no positive rules and therefore remain fail-closed under the
`payload_forward` base-chain DROP policy. The supplied physical path realization set must
match the semantic current path set exactly; one current endpoint cannot back multiple
logical paths, and the host boundary cannot be reused as a VPN path endpoint.

This Calculator does not compile Device firewall, NAT or publication policy.

**Evidence:** rootless compiler tests cover outbound/inbound/bidirectional, zero-path,
physical membership/endpoint identity, global outbound overlap subtraction and per-ingress
inbound partitioning. The pure structural pipeline now extends through
`config -> binding -> PayloadProfileRequest -> PayloadForwardDesiredState`.


###### Complete current payload lower desired-state assembly

**Component:** pure Calculator/composition boundary.

This unit does not add user semantics. It composes the already-normalized current payload
inputs into the exact two lower desired objects consumed by the activation subassembly:

```text
PayloadProfileRequest set
+ NetworkPolicyLayout
+ current RoutePriorityPathRoute set
+ current host-boundary InterfaceIdentity
+ normalized DeviceNatPolicyIntent set
+ normalized DeviceFirewallPolicyIntent set
+ normalized PublicationLocalEndpointIntent set
    ->
PayloadNetworkPolicyDesiredState:
    routing = PayloadRoutingDesiredState
    nft = CompositeNftDesiredState
```

The composition delegates rather than reinterprets:

- routing/RPDB -> `build_payload_routing_desired_state(...)`;
- Profile permission -> `compile_payload_forward_policy(...)`;
- Device NAT -> `build_payload_nat_desired_state(...)`;
- Device firewall -> `compile_device_firewall_policies(...)`;
- publication-local -> `build_local_publication_desired(...)`.

For every Device that currently backs a payload path, normalized NAT and firewall semantics
must be explicit inputs even when they mean no extra behavior:

```text
NAT omitted/disabled semantics      -> DeviceNatPolicyIntent(..., NONE)
firewall omitted semantics          -> DeviceFirewallPolicyIntent(..., rules=None)
```

Missing normalized Device policy for a current path is therefore an input error, never an
implicit allow/default.

Publication-local intents are independent positive local/system contributions, but every
intent supplied to this payload assembly must reference the same current host-boundary
identity used by routing and Profile policy. A different boundary generation is rejected
instead of creating a split desired state.

The shared `NetworkPolicyLayout` may also contain reserved probe allocations. This payload
Calculator consumes only its payload allocation/dispatch fields. It does not materialize
probe route/RPDB/nft state and must not be described as complete probe policy.

The output is immutable lower desired data. The Calculator performs no observation,
mutation, readiness decision, retry or lifecycle orchestration.

**Evidence plan:** rootless tests for zero-path fail-closed composition, one current path with
NAT/firewall/publication, missing normalized Device policy, publication boundary mismatch and
determinism under input-order changes. Existing owner-specific compiler tests remain
authoritative for each lower shape.

**Ordered Device firewall composition — accepted semantic architecture**

**Implements:**
- `VPNG0001-R1.R2.R4.R6.R2`;
- `VPNG0001-R1.R2.R4.R6.R2.R1`;
- `VPNG0001-R1.R2.R4.R6.R2.R2`;
- `VPNG0001-R1.R2.R4.R6.R2.R3`;
- `VPNG0001-R1.R2.R4.R6.R2.R4`;
- `VPNG0001-R1.R2.R4.R6.R2.R5`.

**Constrained by:**
- `VPNG0001-R1.R2.R4.R6.C1`;
- `VPNG0001-R1.R2.R4.R6.R2.R5.C1`.

The positive-only Profile partition remains the **hard Profile permission gate**, but it is
no longer the whole Device firewall. The accepted composition is:

```text
packet on exact managed host-boundary <-> current Device path pair
        |
        v
ordered Device firewall chain
        |
        +-- DENY   -> drop
        +-- REJECT -> active reject
        +-- ALLOW  -> return to Profile gate
        |
        +-- explicit-policy no match -> drop
        +-- omitted-policy default   -> return
        |
        v
Profile NEW/RETURN hard gate
        |
        +-- permitted -> accept
        +-- otherwise -> payload_forward policy drop
```

This order is required because Device `ALLOW` is only permission to continue to the
generated Profile guard; it is **not** an nft `accept` that can widen Profile permission.
Conversely, Device `DENY/REJECT` is terminal and can narrow traffic that Profile would
otherwise permit.

Linux/nftables performs packet-by-packet ordered evaluation. VPN-GATE only validates,
normalizes, compiles, orders and converges the rules.

User order is semantic inside the Device chain. A broad early rule remains broad; the
compiler must not reorder a later specific rule ahead of it. Direction is compiled relative
to the exact current path binding:

```text
OUT: iif = current host boundary, oif = current Device path
IN:  iif = current Device path,   oif = current host boundary
```

Source/destination address and port predicates match literal payload packet fields at this
FORWARD point. The existing Device `MASQUERADE` contract runs later in postrouting, so
outbound source fields are still pre-NAT here. External VPN transport addresses are not
payload source/destination fields.

A normalized firewall `PortBundle` is one set-membership predicate, not a list of separate
policy rules and not a source/destination positional mapping. Lower nft realization uses the
kernel-native expression shape: one exact port is a scalar operand, one inclusive range is a
range operand, and a multi-item bundle is a set containing exact and/or range operands. This
preserves one user rule / one terminal verdict and avoids expansion proportional to the
number of individual ports in a range.

The Device chain is traversed before both Profile NEW admission and the prefix-scoped
ESTABLISHED/RELATED return primitive. Therefore an explicit Device firewall applies to
actual packets in both directions and can terminate an already established flow; there is
no implicit Device-layer established-flow bypass ahead of user rules. Profile statefulness
still determines whether a returned flow is in Profile permission after Device `ALLOW`.

Omitted Device firewall configuration is normalized to the semantic equivalent of
unrestricted `IN ALLOW any` plus `OUT ALLOW any`. An explicit non-empty policy has a
terminal no-match `drop`. Canonical external one-line rule syntax is fixed in
`design/NG3/config-model.md`; this lower compiler consumes only normalized rule intents.

The current `PayloadForwardRuleSpec` and strict observer remain valid evidence/data for the
positive Profile NEW/RETURN sub-contract only. They are no longer a complete representation
of final `payload_forward` ownership once Device jump/ordered chains are materialized.
A later lower-policy unit must extend owner observation/desired state for jump, return,
drop/reject and ordered child-chain objects before physical Device firewall mutation is
authorized.

Endpoint-scoped Device rules are a future extension. They must resolve a configured logical
endpoint through confirmed transport provenance to the exact current binding; runtime
ifnames are not user-facing selectors. Under
`VPNG0001-R1.R2.R4.R6.R2.R5.C1`, this does not block ordinary Release-1 Device firewall
rules.

###### Device firewall lower structural ownership

EXP-041 proves the lower nft control-flow primitives required by the accepted composition:

- `payload_forward` may jump to one ordinary owned child chain for the exact current
  host-boundary/path pair;
- Device `ALLOW` is represented by child-chain `return`, so evaluation continues to the
  later Profile hard gate rather than accepting directly;
- Device `DENY` may terminate with `drop`;
- explicit-policy no-match is represented by a final terminal child `drop`;
- nft preserves the physical order of child rules;
- a `reject` action is structurally observable, while its final normalized
  protocol-appropriate realization remains separately gated.

The lower owner markers accepted for this structural layer are:

```text
child chain:   vpn-gate:ng3:device-fw-child-v1
base jump:     vpn-gate:ng3:device-fw-jump-v1
explicit rule: vpn-gate:ng3:device-fw-rule-v1
fallthrough:   vpn-gate:ng3:device-fw-fallthrough-v1
```

The generic nft namespace inventory preserves each contained object's physical
`source_order` in addition to canonical JSON. Existing unordered consumers may continue to
canonicalize locally; ordered Device firewall observation must use the preserved physical
order.

The structural observer recognizes:

- owned ordinary child-chain shape;
- exact current/stale interface identity for Device jumps;
- ordered explicit child rules whose final action is `return`, `drop` or `reject`;
- exactly positioned terminal fallthrough `drop`;
- conflicts such as a jump to a non-owned child chain, wrong owner markers, unsupported
  rule actions or fallthrough before later rules.

This is **structural ownership evidence only**. Match predicates are retained as canonical
JSON and are not yet promoted into normalized Device-firewall semantics. Therefore this
observer is not by itself authority to delete/rewrite arbitrary recognized rules, and it
does not close the separate protocol/port-predicate or final REJECT realization gates.

###### Device firewall normalized intent and exact lower desired comparison

The internal semantic model now represents an optional Device firewall independently of its
external grammar:

```text
DeviceFirewallPolicyIntent
    device_id
    rules = omitted | ordered non-empty rules

DeviceFirewallRuleIntent
    direction = IN | OUT
    action = ALLOW | DENY | REJECT
    protocol?
    source_ports: PortBundle?
    destination_ports: PortBundle?
    source_ipv4_cidr?
    destination_ipv4_cidr?
    comment?
```

Omitted policy remains distinct from an explicit policy. An explicit policy is non-empty and
preserves literal rule order. `PortBundle` preserves declared exact/range item order and
rejects duplicate/intersecting physical ports. The semantic model is independent from TOML
punctuation; the canonical Release-1 external spelling is selected by
`ConfigurationAdapter` and the current protocol vocabulary remains TCP/UDP/ICMP as defined
by the accepted user grammar.

A separate exact lower desired contract represents one owned child chain plus its exact
host/path jump and ordered physical rules. Predicate expressions and final nft actions are
canonical JSON at this boundary. The desired layer therefore records already-compiled lower
facts but does not compile semantic predicates itself.

`compare_device_firewall` compares:

- exact current ingress/egress identities;
- exact opaque lower child-chain identifier supplied by the caller;
- exact ordered rule sequence;
- exact predicate-expression JSON;
- exact lower action JSON;
- terminal-fallthrough position;
- stale extra owned chains/jumps;
- structural conflicts from the read-only observer.

A mismatch in rule order is a desired-state mismatch even when the same rule set is present.

The exact lower contract itself does not derive child-chain names. Production multi-path
composition assigns them in the semantic-to-lower compiler described below; the comparison
layer still grants no mutation authority.

###### Multi-path Device firewall composition and child-chain identity

**Implements:**
- `VPNG0001-R1.R2.R4.R6.R2`;
- `VPNG0001-R1.R2.R4.R6.R2.R1`;
- `VPNG0001-R1.R2.R4.R6.R2.R2`;
- `VPNG0001-R1.R2.R4.R6.R2.R3`;
- `VPNG0001-R1.R2.R4.R6.R2.R4`;
- `VPNG0007-R7.R1`;
- `VPNG0007-R7.R3.R1`.

The caller supplies normalized Device firewall intent for every Device that currently backs
a payload path, including explicit `rules=None` when the firewall is omitted. Missing
semantic input is an error rather than an implicit unrestricted firewall.

Current logical paths are sorted by canonical `LogicalPathId`. Their zero-based ordinal in
that current desired set is the internal lower token for child-chain naming:

```text
OUT: df_out_<8-digit lowercase hex ordinal>
IN:  df_in_<8-digit lowercase hex ordinal>
```

Examples:

```text
df_out_00000000
df_in_00000000
df_out_00000001
```

The emitted identifier contains no Device/Profile/user ID and uses only the already accepted
safe nft identifier character set. It is deterministic for the same current semantic path
set and requires no persistent token registry, history or collision-prone hash.

A membership change may renumber later current paths and therefore cause additional owned
chain replacement under the closed structural ForwardingGate. Release 1 does not promise
minimal nft-object churn during structural membership change; introducing persistent naming
state solely to avoid that churn is not justified.

For each current path with explicit Device firewall policy, the composition Calculator calls
the existing one-path semantic compiler with the current host/path identities and its two
allocated child-chain names. Omitted policy produces no child chains for that path.

The current physical path realization set must not contain duplicate logical paths, reuse one
endpoint for multiple logical paths, or reuse the host boundary as a VPN endpoint.

**Evidence plan:** rootless tests for omitted/explicit policy, canonical naming independent of
input order, same-Device multi-path uniqueness, missing normalized policy, duplicate policy
and endpoint identity conflicts. Existing EXP-041..044 evidence is sufficient for the
resulting safe chain-name syntax and lower mutation; no new kernel primitive is introduced.

The semantic compiler and bounded mutation slice are now evidence-backed as follows.

**Predicate realization — EXP-042.**

- IPv4 source/destination selectors compile to exact nft `ip saddr/daddr` expressions;
- protocol-only `tcp|udp|icmp` uses `meta l4proto`;
- TCP/UDP source/destination ports use protocol-specific payload expressions;
- nft canonicalization removes a redundant separate `meta l4proto tcp|udp` when a
  protocol-specific port expression already constrains the rule;
- `/32` renders as a plain IPv4 address while shorter prefixes render as prefix objects.

The compiler therefore produces the **observed canonical nft shape**, not a textual source
recipe. Ports require an already-normalized TCP/UDP protocol. Unsupported protocol tokens
remain a compile error rather than being guessed into a lower rule.

For one current Device/path the compiler uses two direction-specific child chains:

```text
OUT chain:
    ingress = current host boundary
    egress  = current Device path

IN chain:
    ingress = current Device path
    egress  = current host boundary
```

IN and OUT packet domains are disjoint, so filtering the original ordered policy into each
direction-specific subsequence preserves first-match semantics while avoiding redundant
interface predicates on every child rule. Each explicit chain ends in terminal `drop`.
Omitted Device firewall produces no Device child chains/jumps.

Lower action mapping is:

```text
ALLOW  -> return
DENY   -> drop
REJECT + TCP -> reject with tcp reset
REJECT + UDP/ICMP/unspecified IPv4 -> bare reject
```

EXP-043 proved the REJECT mapping on real forwarded traffic: TCP produced immediate reset /
`ECONNREFUSED`; UDP and generic/ICMP cases produced active ICMP port-unreachable rather
than silent timeout. For protocol-only TCP REJECT, nft canonicalization omits a redundant
`meta l4proto tcp` because the tcp-reset action itself constrains the protocol.

**Base-chain ordering — EXP-044.**

A Device jump appended after Profile NEW/RETURN accepts is unsafe: the earlier Profile
`accept` can terminate evaluation before Device policy. The accepted lower primitive for a
new jump is therefore `insert rule`, placing the Device jump before existing Profile rules.
The Profile observer delegates marked Device jumps to the Device structural observer rather
than treating them as malformed Profile rules.

**Bounded guarded mutation reference slice.**

`converge_device_firewall_step_once` is an Executor-style one-step convergence operation
behind the closed managed forwarding barrier. Its mutation order is:

```text
stale Device jump
    -> delete exact handle first

then stale unreferenced child chain
    -> flush + delete exact owned chain

then missing desired chain
    -> create child + ordered rules
    -> insert jump before Profile rules
```

Every step begins from a fresh link-bracketed nft observation and ends with fresh
whole-bounded-scope observation plus a closed-gate recheck. Command success is never treated
as postcondition proof. A wrapper error may still end in success only when fresh observation
independently proves strict progress/exact desired state.

The bounded slice recognizes the invariant scaffold, Profile NEW/RETURN rules and Device
firewall objects. It intentionally refuses coexisting NAT or local/system rule classes with
`CONFLICT`; this is a limitation of this reference slice, **not** a product constraint.

The live guarded integration proves initial two-direction materialization, replacement via
`delete jump -> delete chain -> create`, insertion before Profile acceptance, fresh
postcondition verification and persistent `ip_forward=0` throughout. A first live run also
exposed the protocol-only TCP-REJECT canonicalization mismatch; the desired compiler was
corrected to the observed nft shape and the full workflow then passed.

###### Combined Profile / Device firewall / NAT structural convergence

The first combined lower-policy Executor now covers all currently materialized payload owner
classes in the reserved nft table:

```text
invariant four-chain scaffold
Profile payload_forward NEW/RETURN rules
Device firewall child chains + jumps + ordered child rules
payload_postrouting NAT rules
```

`CompositeNftDesiredState` is a composition of the existing exact lower desired contracts;
it does not introduce a new policy language or re-interpret Profile, Device or NAT semantics.

`compare_composite_nft_policy` runs all existing strict owner-specific comparisons against
one fresh observation and then proves that every remaining object in the reserved table is
classified by one accepted owner class. A rule or chain that is not covered by the current
materialized classes is a whole-scope conflict even if each known sub-comparison is locally
clean.

This is deliberate for `stack_input` / `stack_output`: local/system allow contributions
are not silently accepted by the combined payload Executor until their exact lower owner
shape has its own evidence and implementation unit.

EXP-045 proves the missing Profile write primitives in coexistence with Device and NAT:

- a new Profile NEW/RETURN rule may use ordinary `add rule`; it remains after already
  inserted Device jumps;
- stale Profile rules may be deleted by exact observed handle;
- those operations preserve Device child/jump objects and NAT contributions.

The combined pure step planner chooses exactly one mutation in this order:

```text
1. stale Profile positive admission
2. stale Device jump
3. stale Device child chain
4. stale NAT
5. missing NAT
6. missing Device child + inserted jump
7. missing Profile positive admission
```

The addition order is intentional: a new positive Profile permission is exposed only after
its required NAT and Device restriction have already been materialized. Device jump cleanup
remains before child-chain cleanup because nft references must be removed first.

`converge_composite_nft_step_once` is the combined guarded Executor. For every step it:

1. closes and confirms the managed IPv4 ForwardingGate;
2. obtains one link-bracketed whole-table snapshot;
3. performs composite owner/desired comparison;
4. chooses one pure planned step;
5. rechecks the closed gate immediately before the write;
6. performs exactly one lower mutation;
7. obtains a fresh link-bracketed whole-table snapshot;
8. requires stable interface identity inventory and strict distance reduction;
9. rechecks the gate and never opens it.

A successful command is never treated as proof. A command wrapper error may count as
successful convergence only when the fresh composite observation independently proves
strict progress.

The Linux combined backend uses the already accepted Device and NAT Drivers and adds only
the EXP-045-backed Profile add/delete primitives. It does not own local/system exceptions.

The privileged combined integration starts from scaffold-only state, materializes NAT,
two direction-specific Device chains/jumps and Profile NEW/RETURN, verifies that both Device
jumps remain physically before Profile accepts, then converges all three policy classes back
to scaffold-only state. The observed cleanup order is Profile rules -> Device jumps ->
Device chains -> NAT. `ip_forward` remains disabled throughout. An unclassified
`stack_input` rule produces `CONFLICT` with no mutation.

This closes combined structural convergence for the currently materialized Profile,
Device-firewall and NAT owner classes. Extending the same whole-scope Executor to
local/system INPUT/OUTPUT exceptions remains a separate lower-evidence unit, not a product
semantic decision.

No deny-rule ordering or nft jump graph is introduced merely to solve Profile prefix
overlap; the already accepted canonical CIDR partition remains the simpler Profile-gate
mechanism. Ordered chains exist because user-authored Device firewall order is now itself an
accepted product semantic.

###### Profile most-specific CIDR partition Calculator

**Component type:** pure Direct Calculator. This is Profile classification
in bulk form, **not** final effective permission and not nft compilation.

**Implements:**
- `VPNG0002-R2.R1.R2`;
- `VPNG0002-R2.R3.R3`;
- `VPNG0002-R2.R5.R1`;
- `VPNG0004-R4.R1`.

Input is the existing set of `PayloadProfileRequest` objects and, for inbound
partitioning, one concrete `LogicalPathId`. Output is a canonical set of
disjoint `(profile_id, remote_prefix_fragment)` entries.

Outbound partition considers only outbound/bidirectional Profiles and applies
the same global most-specific selection as `classify_outbound_profile`.
Inbound partition first restricts to inbound/bidirectional Profiles containing
the supplied ingress path, then applies the same most-specific selection as
`classify_inbound_profile`.

A broader Profile fragment is split by every more-specific prefix owned by a
different candidate Profile. Nested prefixes belonging to the same Profile are
semantically redundant for selection and may collapse. Exact same prefix
owned by different candidate Profiles is an error, never arbitrary order.

The partition is **Profile permission only**. Ordered Device firewall composition,
path-specific lower rules and protocol/port restrictions are downstream
responsibilities. An envelope can narrow fragments but cannot use this
Calculator to expand Profile permission.

**Necessity:** positive-only nft rules must not rely on rule ordering or
routing correctness to reproduce most-specific Profile selection. A disjoint
partition provides an independently testable semantic basis for later lower
rule generation.

**Simplification:** use standard strict IPv4 CIDR subtraction/collapse only.
No ACL AST, decision tree runtime, persistent prefix trie, rule ordering,
network I/O or mutation.

**Evidence:** rootless tests compare partition ownership against the existing
point classifiers over every address in bounded test networks, including
nested prefixes, default route, same-Profile redundancy and path-relative
inbound selection.




`/31` remain explicit prefix objects; `/32` is a plain IPv4 address string.
The same forms are used by NEW daddr and RETURN saddr matches. The strict
observer implementation gate is therefore open for all accepted IPv4 CIDR
prefix lengths.





`payload_postrouting` exists as the stable owner boundary for supported payload source-NAT
realization. It is valid and intentionally empty when no accepted Device/path requires NAT.
Its base-chain policy is `accept`; the presence of the chain alone never creates NAT.

The two chain comments are lower schema/version markers. A same-name chain with missing or
different marker, hook, type, priority or policy is an ownership/shape conflict.

##### Payload source-NAT lower contract

The internal normalized NAT semantic is produced from canonical
`use_outbound_nat = false|true`:

```text
NatIntent.NONE
NatIntent.MASQUERADE
```

For one current logical path owned by a Device:

```text
NONE
    -> no VPN-GATE payload NAT contribution for that path

MASQUERADE
    -> one postrouting masquerade contribution for payload
       entering from the managed ordinary/host boundary
       and leaving through that path's current concrete endpoint
```

The physical match must bind to the exact current interface identities, not merely reusable
interface names.

The intended Linux/nft match is therefore based on numeric current interface indices:

```text
meta iif == host_boundary.ifindex
meta oif == path_endpoint.ifindex
masquerade
```

A same-name/new-ifindex endpoint must not inherit a stale NAT contribution before the new
binding is accepted and structural policy is rebuilt.

The NAT contribution intentionally does not repeat Profile destination prefixes.

Reason:

1. `payload_forward` is evaluated before postrouting and owns payload permission;
2. only traffic already admitted by the complete forwarding policy can reach the NAT action;
3. one Device/path may be shared by multiple Profiles;
4. duplicating destinations into NAT would create a second policy-classification surface
   with no requirement benefit.

The host-boundary ingress match also keeps locally generated probe/control traffic out of
payload NAT.

NAT intent is structural and availability-independent. Availability may reorder eligible
paths but cannot create/remove a Device NAT contribution.

If several Profiles share the same current path, their identical NAT contribution is
deduplicated by the exact `(host boundary identity, path endpoint identity)` pair.

This lower contract does not choose the final human-facing `nat` field spelling. It consumes
an already normalized semantic intent.

EXP-033 passed on the current Linux/nftables target.

The rule was created with numeric interface indices and behaved as exact ifindex identity.
Current nft JSON representation is intentionally normalized as follows:

- while the stored ifindex resolves to a current interface, the operand is rendered as that
  interface name even with `nft -n -j list ruleset`;
- after the interface disappears, the same stored operand is rendered as a decimal-string
  ifindex;
- recreating the same interface name with a new ifindex does not make the stale rule match.

Therefore authoritative NAT observation must normalize an nft meta-interface operand using a
fresh current interface inventory:

```text
textual ifname
    -> current InterfaceIdentity(ifname, ifindex)

decimal-string operand
    -> unresolved/stale numeric ifindex unless that exact index is independently present
```

It must never compare only textual interface names.

EXP-033 also proved real source translation, ingress scoping and same-name replacement
behavior. The exact nft rule comment is `vpn-gate:ng3:payload-nat-v1`; the rule handle is
incidental.

###### Authoritative payload NAT rule observation

**Component:** read-only direct Calculator for normalized nft observation/comparison.

**Implements:**
- `VPNG0001-R1.R2.R4.R6.R1` — explicit Device NAT intent projected onto an exact current path;
- `VPNG0001-R1.R3.R2` — unambiguous current physical endpoint binding;
- `VPNG0001-R1.R3.R3` — replaced endpoint must not inherit old interface identity;
- `VPNG0004-R4.R3.R2` — structural NAT changes may not bypass a restrictive transition;
- `VPNG0004-R4.R4` — unconfirmed network state cannot authorize forwarding;
- `VPNG0004-R4.R5` — authoritative actual state is required after uncertainty.

**Constrained by:**
- `VPNG0001-R1.R2.R4.R6.C1` — lower NAT observation does not assume an unaccepted human-facing configuration grammar.

**Scenario and responsibility:** After an external Device endpoint disappears or is recreated
with the same name, the product must distinguish the old physical NAT rule from the new
desired path binding before any structural reconciliation. An existing read-only nft
Adapter supplies canonical objects in the owned table; a fresh interface inventory
supplies current `(ifname, ifindex)` identities. The direct Calculator classifies the
owned NAT chain and compares recognized physical rules against already normalized
`PayloadNatDesiredState`, returning confirmed/missing/stale/conflict without mutation.

**Interactions and external environment:** The Calculator has synchronous, explicit
inputs and no kernel I/O, timer, retained history or event ownership. The Adapter's
table ownership and invariant scaffold checks must pass before using its output.
The only external facts are the observed nft JSON representation and fresh Linux link
identity. EXP-033 supplies the platform evidence for name/decimal-index renderings.

**Necessity and simplification:** Exact physical rule classification is required before
deleting or replacing any owned NAT object; desired-state projection alone cannot prove
actual current state. One pure Calculator is sufficient: no additional Agent, cache,
async event/retry flow, second NAT routing policy, or persistent interface history is
introduced.

**Constraints and lifting:** A conflict, invalid/stale endpoint or incomplete ownership
classification cannot be turned into permission to forward or delete state. The observer
changes no user-visible NAT capability and imposes no new product restriction; only
future physical NAT mutation remains gated behind the structural `ForwardingGate`.

**Evidence plan:** Rootless tests cover strict whole-chain recognition, current and
stale ifindices, same-name replacement, unexpected owned expressions/comments, duplicate
rules, missing desired state and invalid/ambiguous inventory; existing EXP-033 establishes
real nft/kernel representation. Run NG3 Python CI on the actual reviewed branch,
perform expert review against this architecture, and record dispositions before accepting
this review unit.

The strict NAT observer operates only after table/scaffold ownership is confirmed and consumes:

```text
canonical nft objects from table ip vpn_gate
+
one fresh current InterfaceIdentity inventory
```

Every rule in `payload_postrouting` is inside VPN-GATE's owned policy boundary and must be
classified. It is not safe to ignore a rule merely because its comment is unfamiliar.

The only currently accepted payload NAT rule shape is:

```text
chain = payload_postrouting
comment = "vpn-gate:ng3:payload-nat-v1"

expr[0]:
    meta iif == <interface operand>

expr[1]:
    meta oif == <interface operand>

expr[2]:
    masquerade

no additional semantic expressions
```

Rule `handle` is retained as exact current kernel-object identity for a later mutation
planner, but it is not semantic desired-state identity.

Interface operands normalize as follows:

```text
ifname string:
    resolve through fresh current interface inventory
    -> current InterfaceIdentity

decimal-string ifindex:
    if exact current ifindex exists, resolve to that InterfaceIdentity
    otherwise retain as stale/unresolved numeric interface identity

other textual/numeric form:
    conflict
```

A stale/unresolved numeric identity never confirms a desired current
`PayloadMasqueradeSpec`.

The observer must report an explicit conflict for:

- missing/wrong NAT owner comment;
- wrong chain/table/family;
- missing or repeated iif/oif match;
- name/index operand that cannot be normalized unambiguously;
- any extra match/action/expression;
- NAT action other than plain masquerade;
- duplicate normalized physical NAT rule.

Thus actual-vs-desired comparison can classify:

```text
confirmed desired masquerade contribution
missing desired contribution
stale recognized owned contribution
conflicting/unrepresentable owned NAT rule
```

and can do so without equating same-name/new-ifindex endpoints.

Observation remains read-only. Physical NAT add/delete is not accepted until this parser and
comparison contract are executable and reviewed.

EXP-034 has subsequently proved on the selected GitHub Linux/nft target that a recognized
stale NAT rule can be deleted by its observed handle after same-name interface replacement,
without deleting the new current rule. A nonexistent handle delete fails without changing
the observed nft objects. This is **technical evidence only**, not authority for production
mutation: full owned-scope classification, an independently confirmed disabled
`ForwardingGate`, fresh pre/post-observation, and guarded structural convergence remain
necessary before any runtime NAT write path is accepted.

###### Guarded NAT-only structural mutation reference slice

**Component type:** a bounded direct `NetworkPolicyExecutor` operation with a lower
Linux nft Driver and the existing read-only Calculator. This is deliberately a
partial reference slice, **not** completion of full Release 1 structural policy.

**Implements:**
- `VPNG0001-R1.R2.R4.R6.R1`;
- `VPNG0001-R1.R3.R2`;
- `VPNG0001-R1.R3.R3`;
- `VPNG0004-R4.R3.R2`;
- `VPNG0004-R4.R4`;
- `VPNG0004-R4.R5`.

**Constrained by:**
- `VPNG0001-R1.R2.R4.R6.C1` — no guessed external NAT grammar.

**Scenario:** One recognized old exact-ifindex NAT rule remains in the marked
payload postrouting chain after a Device endpoint was replaced. The required
current physical NAT desired state may need stale rule deletion and new rule
addition, but no packet may forward during the mixed transition.

**Responsibilities and interactions:** The direct Executor first converges the
owned managed-netns `ForwardingGate` to `DISABLED` and confirms a fresh read.
An injected lower Driver obtains one nft ruleset observation bracketed by two
fresh link inventories; relevant current `(ifname, ifindex)` identities must
agree. Existing pure observers confirm the table/scaffold and classify every
rule in `payload_postrouting` against the supplied normalized desired state.
The Executor must additionally account for **every other object** in the owned
nft table; this bounded slice explicitly refuses mutation if there is any
unsupported object or a rule in `payload_forward`. This refusal is a missing
reference capability, not a new product-level constraint. The eventual complete
structural Executor must combine the independently reviewed forward/probe and
NAT classifications rather than silently narrowing supported payload traffic.

**One-step mutation / postconditions:** With no conflicts and exact current
desired endpoint identity, choose one deterministic recognized stale handle for
deletion, or one missing desired current exact-ifindex masquerade for addition.
Recheck `ForwardingGate == DISABLED` immediately before each write. After
each write, obtain a fresh bounded structural snapshot and prove the expected
**whole-chain change**: delete removed exactly that handle and preserved all
other rules, or add introduced exactly one recognized desired physical NAT
rule with a fresh handle while preserving all previous rules. A successful
nft command is not an independently confirmed postcondition.

**Failure recovery:** A thrown/failed lower command cannot authorize replay
of a stale plan. Reobserve the owned scope and gate; report the authoritative
current result or an unconfirmed failure. Do not open forwarding, silently
delete a conflict, adopt a same-name replacement, or keep an old handle as a
persistent desired-state identity. A later retry must plan from fresh state.
All VPN-GATE structural writes to this owned namespace must be serialized;
unrecognized concurrent external changes cause a fail-closed refusal.

**External evidence and necessity:** EXP-033 validates numeric-ifindex rule
realization and stale interface representation; EXP-034 validates exact-handle
old-rule deletion and failure isolation on the selected Linux/nft target.
A physical Driver is necessary for actual kernel actuation; the existing
read-only Calculator is reused for all classification. No second policy
classifier, background Agent, retry queue, stored handle registry, async
completion protocol or new user configuration is introduced.

**Scope / constraint lifting:** Since this reference slice permits only an
empty forward chain and no other unknown table objects, it is safe but
**not sufficient for the production case with materialized forward/probe
rules**. No acceptance of first-release product scope reduction follows.
The complete structural Executor remains separately gated on composition
with the full nft owner classifiers, RPDB/routes and final forwarding
activation.

**Evidence plan:** rootless fake Driver/Gate tests for lost barrier,
unknown nft objects, stale/duplicate/conflicting NAT, exact single-step
postconditions and failed command re-observation; a disposable-netns
physical backend integration for real add/delete with `ip_forward=0`.
Only after independent expert review may this partial lower slice be
considered executable reference evidence. It must never reopen the root
forwarding barrier.

##### Ordinary-side Profile gateway NAT boundary

**Implements:**
- `VPNG0001-R1.R2.R4.R4.R4`;
- `VPNG0001-R1.R2.R4.R4.R4.R1`;
- `VPNG0004-R4.R6.R1.R6`;
- `VPNG0004-R4.R6.R1.R6.R1`.

**Constrained by:**
- `VPNG0001-R1.R2.R4.R4.R4.C1`.

This is a second source-NAT purpose and must not be conflated with Device
`NatIntent.MASQUERADE`.

```text
Device VPN-side NAT
    ordinary -> managed firewall -> Device/path postrouting masquerade -> VPN

Profile ordinary-side gateway NAT
    VPN -> managed Device/Profile firewall -> explicit host boundary
        -> host forwarding toward ordinary network
        -> optional Profile-scoped gateway source NAT
```

The first exists to make ordinary-originated traffic usable through a VPN path. The second
exists only when an ordinary-network next hop needs replies to return through the VPN-GATE
host without being taught routes to remote VPN prefixes.

A packet whose destination is the VPN-GATE host itself is locally delivered on the host side
and does not require the gateway-forwarding NAT contribution. The semantic intent therefore
does not mean "SNAT every inbound VPN packet"; it means "SNAT the already-permitted
VPN-originated packet when the host forwards it onward through the owned ordinary-side
gateway boundary".

The normalized upper intent is conceptually:

```text
ProfileGatewayNatIntent:
    profile_id
    mode = NONE | MASQUERADE
```

This type name is architectural shorthand, not accepted external configuration syntax.

The Device/Profile firewall runs before the packet leaves the managed network domain.
Consequently source address/port filtering still sees the original remote payload sender.
Ordinary-side gateway NAT must never be moved ahead of that managed policy boundary.

###### Profile association across the host boundary

Per-Profile gateway NAT cannot safely reclassify packets on the host merely by remote source
prefix.

Inbound Profile classification is path-relative:

```text
actual ingress logical path
    +
remote source prefix
    ->
selected Profile
```

Two Profiles may therefore overlap in remote prefix space while being unambiguous because
they admit different ingress paths. Once several managed paths converge on one ordinary host
boundary, source CIDR alone no longer carries that provenance.

The lower boundary must preserve the **host-side consequence** of the already-selected Profile,
but EXP-063/064 show that arbitrary Profile identity does not need to cross the namespace
boundary.

The normalized Release-1 host-side behavior of a remote-initiated Profile is exactly two bits:

```text
stateful return steering = enabled | route-return
ordinary-side gateway NAT = disabled | enabled
```

so the complete behavior space is four fixed classes:

```text
STATEFUL_NO_NAT
STATEFUL_NAT
ROUTE_NO_NAT
ROUTE_NAT
```

The EXP-064 candidate boundary contract is therefore:

```text
actual VPN ingress + remote source
        ->
selected Profile inside managed policy
        ->
stack connection keeps Profile routing-domain association
        +
Profile normalized host behavior selects one fixed boundary lane
        ->
host ingress lane establishes host connection behavior class
        ->
host return/NAT behavior
```

The host never reconstructs the Profile from source CIDR and does not need a per-Profile host
resource. Multiple Profiles with the same normalized host behavior share the same lane while
remaining distinct inside the managed stack.

EXP-063 disproved transient packet-mark handoff across the cross-netns veth boundary as a
carrier: packets crossed, but the receiving namespace did not retain the exported packet mark.
EXP-064 proved the fixed behavior-lane carrier technically across all four combinations, including
overlapping remote prefixes, forwarded gateway NAT, route-return/stateful-return, stack-side
established-flow affinity, host-local no-NAT and unrelated-host isolation.

The lane identity is lower infrastructure, not user policy. However this candidate cannot be adopted while `VPNG0004-R4.R6.R1.R6.R1` is read literally as requiring full Profile identity to cross the boundary. Host-side behavior must not be
inferred from source CIDR, current VPN ifname or Device identity. If the selected lane/owner
state cannot be confirmed, the corresponding host-boundary behavior is unready.

###### Ownership and component boundary

The semantic owner remains the existing payload/Profile policy owner. No new long-lived
Manager is introduced.

The existing `NetworkPolicyAdapter` gains a **separate host-boundary behavior realization
sub-contract** because the host-side mutable state is outside the managed network namespace:

```text
Profile normalized intent
    -> fixed HostBoundaryBehaviorLane

observe HostBoundaryBehaviorOwner
apply desired active lanes + return/NAT behavior + verify
cleanup owned behavior state + verify absence
```

This owner scope is disjoint from the managed-domain `table ip vpn_gate` owner scope. The
host-side owner may mutate only explicit VPN-GATE lane/return/NAT resources and must treat
unrelated host firewall/routing state as foreign.

The four-class vocabulary is fixed by accepted Release-1 semantics rather than by Profile
count. Concrete interface names/addresses and lifecycle allocation remain lower
implementation details; they are not user-facing knobs.

###### Managed-stack dispatch to the selected behavior lane

Conditional on resolving `VPNG0004-R4.R6.R1.R6.R1` in favor of Profile-derived host behavior rather than literal cross-boundary Profile identity, the EXP-064 carrier does not require a second Profile classifier. The stack already preserves
the accepted inbound Profile as its Release-1 return-affinity connection mark and has a
higher-precedence mark-to-Profile-table RPDB rule. For a remote-initiated NEW flow, the same
already-established Profile association may also select the initial packet's Profile table
inside the managed namespace.

That Profile table gains a preferred ordinary-side default route through the current endpoint
for the Profile's normalized `HostBoundaryBehaviorLane`, while the existing terminal guard
remains as the fail-closed fallback. Zero-current-path Profiles do not materialize a lane
route.

Conceptually:

```text
VPN ingress
    -> path-relative Profile classifier
    -> save Profile connection association
    -> select the same Profile routing table for this inbound packet
    -> Profile table:
         remote destinations -> VPN path routes
         ordinary-side default -> selected behavior lane
         terminal guard -> fail closed
```

The packet mark used for this table selection is stack-local implementation state. It is not
the cross-namespace carrier rejected by EXP-063 and is cleared/lost without consequence at
the boundary; host behavior is derived only from the actual behavior-lane ingress.

The pure projection is represented separately by
`host_boundary_lane_routing.py`; it deliberately does not masquerade a behavior lane as a
VPN `LogicalPathId`. Production activation remains gated until these lane routes and the
corresponding ingress table selection are composed into the existing structural desired-state
transaction behind the closed ForwardingGate.

A structural transition that changes Profile gateway NAT or its boundary association is not
eligible for the pure route-priority fast path. The affected forwarding must remain
restrictive until managed policy, association and host-boundary NAT postconditions are all
freshly verified.

###### Return path and failure semantics

For a forwarded VPN-originated packet, successful ordinary-side source NAT makes the
ordinary-network destination reply to the VPN-GATE host gateway address. Normal conntrack
reverse NAT then restores the remote destination on the reply before routing it back toward
the explicit managed boundary.

This capability does not replace the existing requirement that traffic for managed remote
prefixes be routed into the VPN-GATE boundary. It only avoids requiring each downstream
ordinary host to know those remote routes.

Failure or ambiguity in host-side NAT observation, owner classification or Profile
association cannot be treated as "NAT probably active". The Profile gateway-NAT function is
reported unconfirmed/unready and no new boundary NAT permission is activated from guessed
state.

**Simplification:** no universal host-firewall Manager, per-packet userspace proxy, endpoint
provisioning service, durable association journal or guessed host-route editor is introduced.

**Evidence:** EXP-063 rejects transient cross-netns packet-mark handoff. EXP-064 proves the
fixed behavior-lane mechanism technically, including overlapping remote prefixes on distinct
ingress paths, all four return/NAT combinations, reverse NAT, host-local no-NAT and unrelated
host isolation. Production ownership/convergence and managed-domain lane lifecycle remain
separate implementation gates.

The scaffold is deliberately independent from the root structural barrier:

- structural rebuild happens while verified `ip_forward=0`;
- the scaffold may then be created/repaired and verified;
- final allow/NAT rules are materialized behind the still-closed root barrier;
- RPDB activation and full route+nft verification still occur before re-enabling forwarding.

A foreign nft base chain outside `table ip vpn_gate` is not adopted or deleted by this
scaffold. For safety, the payload forward chain must still prevent a foreign unconditional
`accept` chain at another priority from bypassing its default drop.

EXP-032 passed on the current Linux/nftables target.

The accepted JSON metadata is:

```json
{"comment":"vpn-gate:ng3:payload-forward-v1","family":"ip","handle":1,"hook":"forward","name":"payload_forward","policy":"drop","prio":0,"table":"vpn_gate","type":"filter"}

{"comment":"vpn-gate:ng3:payload-postrouting-v1","family":"ip","handle":2,"hook":"postrouting","name":"payload_postrouting","policy":"accept","prio":100,"table":"vpn_gate","type":"nat"}
```

Handles are incidental and excluded from scaffold identity.

The live packet test also proved:

- an empty `payload_forward policy drop` blocks transit;
- foreign unconditional-accept base chains at priorities `-100` and `100` do not bypass
  that drop;
- explicit allow rules inside `payload_forward` can permit the tested path;
- the empty `payload_postrouting` chain contains no NAT rule.

Observation uses full JSON ruleset inventory rather than treating a failed
`list table` command as proof of absence:

```text
nft -j list ruleset
```

This keeps:

- valid table absence;
- malformed/unsupported owned-table shape;
- command/JSON observation failure;

as distinct states.

The marker is lower implementation state. It is not user configuration and does not encode a
Profile/Device ID.

EXP-031 passed against the current nftables target.

The marked table is currently observed as:

```json
{"comment":"vpn-gate:ng3:owner-v1","family":"ip","handle":2,"name":"vpn_gate"}
```

and an unmarked same-name table as:

```json
{"family":"ip","handle":3,"name":"vpn_gate"}
```

The numeric handle is incidental kernel identity and is not part of the ownership marker.

The executable observer must therefore compare `family`, `name` and exact `comment`,
while retaining contained objects separately for later strict shape classification.

#### Deterministic allocation and configuration change

Allocation is deterministic for one accepted semantic owner set.

A minimal implementation may rank canonical owner keys and assign the next available entry
from an ordered platform resource pool. Persistent hash maps or durable allocation journals
are not required merely to preserve numeric IDs across a configuration change.

No product requirement promises stable table/rule/metric numbers across a structural
configuration transition.

If a configuration change changes owner membership or allocation rank, the change is a
**structural** network-policy transition. It must pass through the accepted restrictive
barrier/reconciliation path; it is not eligible for the pure-priority fast path.

#### Cleanup and conflict rule

Reserved lower resource spaces are not permission for blind deletion.

Cleanup/recovery must:

1. inventory the reserved resource scope;
2. prove each candidate resource matches an accepted VPN-GATE owner/role shape;
3. delete/reconcile only proved owned resources;
4. treat an unexpected object inside a reserved table/priority/protocol/nft namespace as an
   observable ownership conflict and fail closed rather than silently deleting foreign
   state.

This applies equally to current and stale allocations from a previous accepted
configuration.

Because table/rule allocations may change across a structural configuration transition,
cleanup identity must be derivable from the reserved lower namespace and exact resource
shape, not solely from the current configuration's allocation map.

#### Platform resource-space contract

Concrete numeric pools are lower Linux platform constants.

They must satisfy:

- disjoint payload/probe table pools;
- disjoint RPDB owner pools with the required precedence relative to ambient/main lookup;
- route protocol marker values that are representable and observable through the accepted
  inventory mechanism;
- enough metric space for the largest accepted currently realized path set plus scratch and
  terminal guard;
- no arbitrary small product limit when a larger kernel resource space can be used safely;
- privileged evidence for the actual chosen Linux numeric ranges before production code
  relies on them.

The user configuration never contains these values.

#### Accepted current Linux platform space

EXP-028 passed in privileged GitHub Linux CI, including both first and last values of the
declared table/RPDB pools. The current NG3 Linux reference implementation therefore uses:

```text
payload table pool:
    [0x80000000, 0xC0000000)

probe table pool:
    [0xC0000000, 0x100000000)

probe RPDB priority pool:
    [0x2000, 0x4000)      # 8192..16383

payload RPDB priority pool:
    [0x4000, 0x6000)      # 16384..24575

ambient/main lookup priority:
    32766

managed terminal/guard route protocol:
    201

managed path/unicast route protocol:
    202

first preference route metric:
    1

terminal guard route metric:
    0xffffffff

owned nftables namespace:
    family ip
    table vpn_gate
```

The high table ranges are role-classifiable by their top bits and avoid common low routing
table IDs. The selected RPDB quarters deliberately leave priorities `1..8191` and
`24576..32765` outside VPN-GATE ownership for other explicitly provisioned network-domain
policy while keeping probe rules before payload rules and payload rules before the standard
main lookup.

EXP-028 also records an observation relevant to future strict structural inventory:
with current iproute2 `-N`, `RTN_BLACKHOLE` may be rendered as numeric string `"6"`.
Parsers must normalize the semantic route type rather than require only the word
`"blackhole"`.

These are current Linux implementation constants, not user-facing schema. A materially
different kernel/iproute2/nftables platform must rerun the platform evidence gate rather
than assuming the numeric contract is portable without verification.

The executable pure allocator implements this contract over an injected
`NetworkPolicyPlatformSpace` rather than hard-coding production constants. It:

- ranks payload Profiles by canonical ID for table allocation;
- ranks probe routing demands by `(profile_id, logical_path_id)`;
- allocates payload dispatch priorities by longest-prefix-first destination order;
- keeps payload/probe table and RPDB pools disjoint;
- rejects Linux reserved table IDs and RPDB priority 0;
- requires probe RPDB space to precede payload dispatch and payload dispatch to precede the
  platform's ambient/main lookup;
- derives the same Profile-local preference metric namespace independently in every Profile
  table;
- preserves zero-path Profiles with a table/guard allocation but no priority metric space;
- exposes reserved pool membership independently of the current allocation map so stale
  resources from a previous configuration remain classifiable for cleanup.

# 10. NetworkPolicyExecutor

**Component type:** Executor

**Implements:**
- `VPNG0004-R4.R2`
- `VPNG0004-R4.R3`
- `VPNG0004-R4.R3.R1`
- `VPNG0004-R4.R3.R2`
- `VPNG0004-R4.R5`
- `VPNG0005-R5.R2`
- `VPNG0005-R5.R3`
- `VPNG0007-R7.R1`
- `VPNG0007-R7.R5`

The Executor converges the lower network domain from freshly observed current state to the
caller-selected desired semantic state.

The executable reference now separates a single physical-attempt contract from retry policy:

```text
fresh authoritative observation
        ->
pure convergence plan
        ->
apply semantic steps
        ->
fresh authoritative observation
        ->
exact postcondition check
```

A failed physical step terminates that attempt. The remaining plan is discarded, the
Executor re-observes before returning failure, and any later attempt must re-plan from that
new observation. The attempt helper contains no hidden retry loop.

A successfully issued command sequence is not confirmation. Success requires a fresh final
observation that exactly matches the desired one-route-per-logical-path assignment.

Required properties:

- observe before planning when the previous result is not authoritative;
- use a deterministic plan for one transaction;
- verify the resulting postcondition;
- never report desired state as confirmed merely because commands were issued;
- after partial failure, re-observe before planning another mutation;
- prefer a safe restrictive result when the required postcondition cannot be confirmed.

The Executor distinguishes two transition classes.

## 10.1. Pure priority permutation — make-before-break route-slot transaction

**Implements:**
- `VPNG0004-R4.R3.R1`
- `VPNG0003-R3.R2`
- `VPNG0003-R3.R3`
- `VPNG0003-R3.R4`
- `VPNG0003-R3.R8`
- `VPNG0003-R3.R8.R1`

When the desired change alters only priority/order of the same eligible unicast path set,
the Linux implementation uses owned ordinary metric space and must be able to identify one
currently unused metric whenever a route move requires working space.

### Priority convergence domain

One executable priority-convergence attempt is scoped to **one independently observable
route key** inside a Profile routing domain, not to an aggregate union of all Profile
destinations.

For the current IPv4 direction this means that a backend instance/planning snapshot
represents one concrete owned route-key scope such as one destination prefix in the
appropriate internal routing table/domain, together with the eligible logical paths for
that route key.

This boundary is required because a Profile may materialize multiple kernel route entries
for different destinations. After a physical partial failure, one destination can contain a
temporary duplicate or completed move while another destination is still at the old
assignment. Aggregating such rows into one `logical_path -> metrics` map would lose
authoritative state and could falsely justify deletion or success.

Therefore:

- each route-key domain is observed and converged from its own fresh kernel snapshot;
- one current domain snapshot is normalized from numeric IPv4 iproute2 JSON by exact
  owner-protocol + destination scope and current path endpoint identity;
- path identity matching includes the current `(ifname, ifindex)` endpoint plus the
  expected gateway/onlink shape, so same-name interface replacement or a foreign owned row
  cannot impersonate the accepted logical path;
- route forms not representable by the single-path priority contract (multipath/nexthop
  forms, cross-family `via`, or unrepresented flags) fail observation instead of being
  silently projected into a simpler state;
- the path-level `logical_path -> observed metrics` model is valid only inside one such
  route-key domain;
- temporary progress may differ between route-key domains while convergence is in flight,
  but every affected domain must preserve the pure-priority safety invariant: every eligible
  path remains represented and no ineligible path is introduced;
- completion of a Profile-level priority change is confirmed only after all affected
  route-key domains have fresh postconditions matching the same desired logical-path order;
- coordinator execution is deterministic over a canonical destination order, performs no
  hidden retry, and does not infer Profile success from per-domain command return values;
- after all bounded domain attempts finish, the coordinator performs a second fresh
  verification pass across every affected domain; only that final aggregate postcondition
  may mark the Profile priority change confirmed;
- failure in one domain does not permit stale-plan replay in that or another domain; each
  further attempt starts from fresh observation of the domain it will mutate.

No requirement promises an atomic simultaneous metric permutation across all destination
prefixes. The required observable invariants are preserved path membership/safety during
the transition and the configured effective order after verified convergence.

For Release-1 outbound availability, pure-priority convergence does not require an additional
per-flow path-affinity owner. The sticky active-path semantics in section 5 keep the currently
healthy ordinary path first after failover/recovery and therefore avoid recovery-driven
migration by construction. An explicit Profile-local reserve membership deliberately opts
into failback to a recovered higher-baseline path. Managed-stack return affinity remains a
separate concern for remote-initiated traffic.

The unused/free metric is inferred operationally from freshly observed current state. It is
not configuration, semantic state or a permanently materialized "hole".

In particular, EXP-027 proved that an all-live steady state needs no configured/materialized
gap: the next unused ordinary metric is sufficient for the first move. Other layouts may
naturally expose a free metric between ordered regions as a consequence of the current route
arrangement.

The only move primitive is:

```text
X currently at Mold
Mfree is free

1. add the same allowed route X at Mfree
2. verify/continue transaction
3. delete X at Mold
```

Between steps 1 and 3:

- every eligible path still has at least one route;
- `X` temporarily has two route copies with different metrics;
- no unrelated or previously ineligible path is introduced.

After deletion, `Mold` becomes the new free metric position.

The deterministic planner repeats this primitive until the current route ordering equals the
desired ordering.

The executable convergence layer additionally accepts a **freshly observed owned-route
snapshot** in which one logical path may temporarily have more than one metric after a
partially completed make-before-break move.

Its normalized recovery semantics are:

- identical logical-path membership remains mandatory for the priority-only path;
- an already-observed redundant route copy may be deleted only while another confirmed copy
  of the same logical path remains;
- after redundant copies are normalized, further movement is expressed only as the semantic
  `RoutePriorityMove(from_metric, to_metric)` primitive;
- a `RoutePriorityMove` retains the architectural meaning
  `add new copy -> verify -> delete old copy`; it is not exposed as independently replayable
  raw add/delete commands;
- a path with no observed route, an inter-path metric collision, a route outside the owned
  metric space, or a structural membership difference is rejected from this priority-only
  convergence path;
- after any partial execution failure the remaining plan is stale: the Executor must
  re-observe authoritative state and produce a new convergence plan before another mutation.

The convergence planner itself is not postcondition evidence. Confirmation still belongs to
the physical Executor/Adapter boundary after Linux mutation and re-observation.

The availability-specific composition above this generic Executor is intentionally thin: `availability_route_priority.py` maps the effective `PayloadProfileRequest` order produced by `AvailabilityManager` into the existing `RoutePriorityDomainRealization` / `RoutePriorityDomainRequest` contracts and invokes the existing Profile-level coordinator. It does not own a second metric namespace, planner or Linux mutation path.

The current executable Linux backend now closes that boundary for the **pure-priority
single-route-key** subset:

- route observation is bracketed by two current interface inventories;
- relevant `(ifname, ifindex)` identities must remain stable across that observation window;
- every mutation re-observes the whole route-key domain before and after the physical step;
- add-before-delete is accepted only when the fresh after-add snapshot equals the exact
  expected whole-domain state;
- delete-old is followed by another fresh exact whole-domain postcondition check;
- duplicate cleanup is likewise prechecked and verified against the whole domain;
- any unrelated route drift inside the same domain invalidates the semantic step rather than
  being ignored;
- the backend issues exact argv-based iproute2 commands inside the managed namespace and does
  not use shell interpolation.

This physical slice does not yet imply completion of structural policy mutation, RPDB/nft
materialization, multi-domain Profile orchestration or daemon lifecycle.

Priority mutation is serialized **per Profile/routing domain**:

- only one priority transaction for that Profile/domain mutates its metric layout at a time;
- the active transaction plan is immutable and is not cancelled halfway through;
- newer desired orders may be coalesced to the latest desired order while the active
  transaction completes;
- after final verification, a later transaction starts from freshly observed materialized
  state and the latest desired order;
- replay of every intermediate availability transition is neither required nor desired;
- unrelated Profiles/domains are not globally serialized merely because one Profile is
  moving metrics.

This is the NG3 re-derivation of the historical "metric hole" algorithm. Historical NG2
EXP-027 already demonstrated the relevant Linux property: the same path can temporarily
exist at two metrics, exact deletion removes only the old copy, and the full eligible set
remains present for both ordinary prefixes and `default`.

The historical evidence is reusable because the kernel claim is materially identical; the
NG2 product semantics are not inherited by that fact.

## 10.2. Structural policy transition — guarded fail-closed convergence

**Implements:**
- `VPNG0004-R4.R3.R2`
- `VPNG0004-R4.R1`
- `VPNG0004-R4.R2`
- `VPNG0004-R4.R5`

If membership, direction, filtering/NAT or another structural policy dimension changes, the
priority-only route-slot proof no longer applies.

The Executor may establish/retain a restrictive guard for the affected traffic while it
changes lower state, and may temporarily interrupt forwarding when necessary to preserve the
safety postconditions.

It must never preserve continuity by passing traffic through a path or policy state that is
forbidden by either the old or new accepted policy.

After partial failure it re-observes authoritative lower state before planning further
mutation.

### 10.2.1. Complete structural routing desired state

Before a structural transaction is applied, the lower Adapter/Calculator must be able to
derive a complete desired routing projection for the affected payload owner set.

For each enabled Profile the projection contains:

```text
one allocated Profile table

one terminal fail-closed route:
    table = Profile table
    type = BLACKHOLE
    destination = default
    protocol = guard marker
    metric = terminal guard metric

for every Profile destination and current realized logical path:
    one desired path route
    table = Profile table
    destination = Profile destination
    protocol = path marker
    metric = current semantic preference slot
    endpoint/gateway/onlink = verified integration realization

for every Profile destination:
    one host-boundary RPDB dispatch rule
    iif = current verified managed host-boundary endpoint
    to = Profile destination
    table = Profile table
    priority = deterministic allocation
```

A zero-path Profile therefore still has:

- its allocated table;
- its terminal guard;
- its destination dispatch rules;

and has no ordinary path routes. Dispatching its traffic into that table must terminate in
the guard rather than fall through to ambient/main routing.

The lower desired projection is data only. Constructing it does not mutate Linux state and
does not claim the policy is active.

The verified managed host-boundary endpoint is an internal runtime fact, not a user-visible
route/rule field.

### 10.2.2. Structural activation barrier

A structural transition is wider than route-table preparation.

In particular, installing a new RPDB dispatch rule can make a newly prepared Profile table
reachable. That activation must not occur before the filtering/NAT state required by the
same new semantic policy is safe.

#### Root barrier primitive

The first-release structural barrier is the managed network namespace's own IPv4 forwarding
gate:

```text
net.ipv4.ip_forward = 0
```

This sysctl belongs to the isolated managed network domain, not to the ordinary host network
namespace.

The Executor may begin allowing structural mutation only after:

```text
write ip_forward = 0
        ->
fresh reread
        ->
observed value == 0
```

A successful write command without the confirming reread is not a barrier.

This primitive is deliberately below the user configuration contract. It is not a policy
knob and does not depend on Profile direction, NAT spelling, Device firewall grammar or
current route allocation.

The root barrier is global to managed IPv4 forwarding. Structural transitions may therefore
temporarily interrupt forwarding for Profiles whose individual semantic policy did not
change. Release 1 does not promise continuity across a structural policy transition; the
separate pure-priority fast path remains the mechanism for non-disruptive priority-only
changes.

The global barrier is chosen intentionally instead of a per-Profile nft deny rule:

- it does not depend on correctly classifying overlapping Profile prefixes while state is
  mixed;
- it remains effective when path bindings or RPDB allocations are being replaced;
- it does not depend on the final NAT/Device-firewall grammar;
- critically, it does not rely on the nft namespace being already trusted while nft
  ownership/conflict recovery is itself in progress.

If the Executor cannot verify `ip_forward=0`, it must not begin or continue an allowing
structural rebuild. From a previously verified state the requested structural transition is
aborted. During startup/recovery from UNKNOWN state, inability to establish the barrier is a
hard failure and no new allowing state is materialized.

The managed namespace forwarding gate therefore becomes explicit lower owned state:

```text
ForwardingGate:
    desired = enabled | disabled
    observed = 0 | 1 | unknown
```

Only `observed = 0` is sufficient as the structural barrier.

EXP-030 passed in privileged GitHub CI and proved the selected primitive on the current Linux
target with real forwarded packets:

- the managed namespace value was independently writable/readable;
- changing it did not change the host namespace value;
- `ip_forward=1` passed transit ICMP across a two-interface routing namespace;
- `ip_forward=0` blocked that same transit path;
- restoring and rereading `1` restored forwarding.

The executable lower backend may therefore use
`ip netns exec <managed-ns> sysctl ... net.ipv4.ip_forward`, but success remains defined by
the fresh reread value rather than process exit status alone.

#### Structural transaction ordering

With the root barrier verified, the first-release physical structural transaction uses an
**exact-before-release** ordering:

```text
fresh lower observation
        ->
set/reread managed-netns ip_forward = 0
        ->
prepare/verify every desired terminal guard
        ->
delete/verify stale payload RPDB dispatch
        ->
delete/verify stale payload routes
        ->
prepare/verify desired ordinary path routes
        ->
converge/verify required nft filtering/NAT/local-system state
        ->
install/verify missing desired RPDB dispatch
        ->
verify exact desired payload routing + nft state
    - no missing payload route/rule
    - no stale payload route/rule
    - no payload-owner conflict
    - nft desired state exact
        ->
set/reread managed-netns ip_forward = 1
        ->
fresh final exact routing + nft verification
        ->
confirmed
```

The semantic postcondition remains:

> while structural state is mixed or unconfirmed, affected traffic cannot traverse a policy
> that is forbidden by either the previously accepted or newly accepted policy.

This refinement removes an ambiguity in the earlier draft ordering that placed generic
"stale cleanup" after barrier release. The current authoritative
`PayloadRoutingComparison.confirmed` contract is exact: stale payload routes or RPDB rules
are not a confirmed desired state. More importantly, a stale RPDB rule or a stale path route
can remain reachable and can represent behavior forbidden by the new policy.

Release 1 already permits forwarding interruption during structural change. Therefore the
smallest safe implementation is to retire stale payload routing state **under the verified
closed root barrier**, not to expose a mixed old/new routing set and clean it later.

Terminal guards are prepared before stale route cleanup. This preserves a restrictive table
fallback for every desired Profile table before ordinary route membership is rewritten.
Stale RPDB dispatch is then removed before stale routes so obsolete tables cease to be
selected by payload dispatch while their contents are retired.

A route-table preparation helper may still create a new guarded table before nft activation,
because no missing desired RPDB rule reaches it yet. EXP-048 proves this physically: adding
the terminal guard and desired path route did not change real host traffic until the RPDB
dispatch rule was installed.

EXP-048 also proves the converse safety property: with RPDB dispatch active, deleting the
ordinary path route leaves the terminal blackhole authoritative and prevents fallback to
ambient/main routing.

RPDB addition is therefore an activation step, never a standalone preparation optimization.
It occurs only after guarded routes and the required nft policy are exact.

Delayed cleanup after barrier release is not part of the first-release structural Executor.
A future optimization may defer cleanup only for state independently proven unreachable and
semantically irrelevant; such an optimization requires its own evidence and must not weaken
the exact-before-release postcondition.

This is why the pure-priority path remains a separate fast path: only there is path
membership/filter/NAT unchanged and the semantic make-before-break proof sufficient without a
structural barrier.

### 10.2.3. Authoritative structural route/RPDB observation

Structural recovery requires inventory of the **whole reserved lower namespace**, not only
resources named by the current allocation map.

The current Linux observation commands are:

```text
ip -j -N -4 route show table all
ip -j -N -4 rule show
```

EXP-029 established the current iproute2 6.19 numeric JSON form relevant to the accepted NG3
resource space:

- non-main high table IDs are numeric strings;
- route protocols are numeric strings;
- ordinary unicast type may be omitted;
- `RTN_BLACKHOLE` is numeric string `"6"`;
- host-route `/32` destination may be rendered as a bare IPv4 address;
- route scope is numeric string `"253"` for the tested direct-device routes;
- RPDB `priority` is numeric;
- RPDB lookup table is a numeric string;
- payload destination selector is represented by `dst` plus `dstlen` for prefixes;
- EXP-048 additionally proves that a payload RPDB host destination may be rendered as a bare
  IPv4 `dst` with omitted `dstlen`, which is normalized narrowly as `/32`;
- `src = "all"` is explicit in the tested rules;
- EXP-029 showed that `fwmark` / `fwmask` are hexadecimal strings for a marked RPDB
  test rule, but that rule was an inventory-shape surrogate rather than the selected
  Release-1 probe-routing discriminator;
- EXP-065 confirms current representation for the tested
  `uidrange + ipproto + target` subset: numeric JSON uses integer `uid_start` /
  `uid_end`, bare host `dst`, and `"ipproto-1"` for ICMP;
- EXP-022/023 show that the full proven path-specific selector also includes `oif`.
  Current NG3 observation does not yet normalize that field and is therefore incomplete for
  multi-path same-target probing.

The structural observer must normalize these representation forms into typed semantic lower
objects. Until the `oif` correction is implemented, the current probe RPDB observer/renderer
must not be treated as a complete path-specific Release-1 mechanism. A marked rule inside the
probe RPDB pool remains an unsupported reserved shape.

Rows outside VPN-GATE reserved table/priority pools may be ignored by this owner-specific
inventory. Rows **inside** reserved pools must not be silently ignored merely because their
shape is unexpected.

For a reserved object the observer returns either a recognized managed route/rule or an
explicit ownership conflict / unsupported reserved shape.

Observation failure, malformed JSON and ownership conflict are distinct from a valid empty
managed inventory.

The route observer resolves any managed `dev` through the same fresh `(ifname, ifindex)`
interface inventory used elsewhere. Same-name interface replacement must therefore remain
visible.

This observation boundary is read-only. It does not authorize cleanup or activation by
itself.

### 10.2.4. Executable cross-domain structural convergence

The first-release reference implementation now closes the guarded route/RPDB+nft boundary
without introducing another semantic owner.

The invariant four-chain nft scaffold remains a separate lower bootstrap/repair prerequisite.
The cross-domain Executor does not silently create or adopt it:

```text
scaffold absent/incomplete
    -> PRECONDITION_FAILED
    -> run the already accepted scaffold bootstrap/repair boundary

reserved nft ownership/shape conflict
    -> CONFLICT
    -> no structural mutation
```

Once that prerequisite is satisfied, one authoritative structural snapshot is:

```text
fresh link inventory
    -> full reserved IPv4 route JSON
    -> full reserved IPv4 rule JSON
    -> full nft ruleset JSON
    -> fresh link inventory
```

The two link inventories must be identical. Route/RPDB and nft comparisons therefore consume
one common current interface generation rather than independent nested observations.

Each Executor invocation:

1. closes and rereads the managed IPv4 ForwardingGate;
2. obtains one fresh cross-domain snapshot;
3. computes current routing+nft comparison;
4. selects at most one mutation from the accepted exact-before-release phase planner;
5. rechecks that the ForwardingGate is still closed;
6. applies exactly one route/RPDB or nft mutation;
7. obtains a fresh cross-domain snapshot;
8. accepts command failure as non-authoritative when the fresh state nevertheless proves
   strict progress;
9. otherwise keeps forwarding closed and returns the observed failure/conflict.

No stale mutation plan is replayed. A later invocation always replans from fresh state.

The complete structural transaction is an explicit coordinator over that one-step contract,
not a retry loop hidden inside the Executor:

```text
STEP_APPLIED with strict distance decrease
    -> invoke one fresh one-step attempt

CONFIRMED
    -> transaction confirmed

any other terminal one-step status
    -> stop transaction immediately

unfinished fresh attempt starts farther from desired than the prior verified final state
    -> REGRESSED
    -> stop this transaction
```

The structural distance is a technical count of unresolved lower-state differences; it is
not a product health score. Every accepted `STEP_APPLIED` result strictly decreases it.
Between attempts the next fresh state may be equal or closer because of independent
progress. If an unfinished transaction has moved farther away, the current transaction
stops rather than converting external churn into hidden retries. If that fresh attempt has
already reached and verified `CONFIRMED`, the exact confirmed state remains authoritative.

Because distance is non-negative and every continued step strictly decreases it, no
arbitrary `max_steps` / retry count is required for termination. A later Manager audit may
start a new transaction from fresh state after a failed/regressed transaction; it does not
resume the old plan.

Privileged run `43951600267` additionally exercises this coordinator after a
same-name/new-ifindex refusal: using the new current interface identity, the coordinator
performs the remaining multi-step restoration and reaches confirmed forwarding through the
new VPN generation.

The Linux route/RPDB Driver is intentionally mutation-only. It uses the EXP-048-backed exact
argv forms for:

- terminal blackhole guard add/delete;
- ordinary path-route add/delete;
- payload host-boundary RPDB dispatch add/delete.

It does not perform an independent observation and does not infer ownership from a reserved
table/priority alone. Stale deletes consume typed objects produced by the whole-reserved
observer.

When a fresh post-write snapshot is fully exact, activation is a separate verified phase:

```text
exact routing+nft while ForwardingGate=DISABLED
    -> recheck gate still DISABLED
    -> set/reread ForwardingGate=ENABLED
    -> fresh whole cross-domain snapshot
    -> reread gate
    -> CONFIRMED only if state is still exact and gate is ENABLED
```

If the post-activation whole-state verification fails, the Executor immediately attempts to
restore and reread `ForwardingGate=DISABLED`. A verified re-close is reported as a failed
activation/final verification, not as success. Failure to confirm the safety re-close is a
separate `SAFETY_RECLOSE_FAILED` result.

The root forwarding barrier protects managed payload forwarding only. Publication-local
INPUT/OUTPUT state remains governed by its EXP-047 atomic full-diff contract and is included
in the nft exactness check; the Executor does not pretend that `ip_forward=0` blocks local
traffic. Probe-owned local/system state must therefore participate in the same explicit
owned local-policy exactness boundary once materialized. The historical probe-materialization
deferral is superseded for Release 1 as recorded in section 8.1 and
`design/deferrals/NG3-probe-local-system-materialization.md`; EXP-026 cleanup is not a
prerequisite for ordinary ICMP probe materialization.

Privileged integration run `43949342868` proves on the current GitHub Linux environment:

- an old accepted route/RPDB+nft policy can carry real traffic through ALT;
- every mixed-state convergence step retains `ForwardingGate=DISABLED` and real traffic is
  blocked;
- the exact new policy is activated only after routing+nft confirmation and then carries real
  traffic through VPN;
- an injected exception after a physically successful final RPDB add is recovered from fresh
  state and does not cause blind replay;
- a zero-path Profile retains desired RPDB dispatch plus terminal blackhole and cannot fall
  through to ambient/main routing after forwarding is re-enabled;
- same-name/new-ifindex replacement makes the stale desired interface generation invalid
  before mutation, leaves forwarding closed and materializes no new path route.

This executable reference does not subsume the pure-priority fast path. Priority-only metric
movement remains the non-disruptive path when structural membership/filter/NAT semantics are
unchanged.

# 11. Event contracts

The architecture currently needs only semantic event edges required by Engine roles.

## 11.1. Availability observation

`AvailabilityProbeAgent -> PayloadTrafficManager`

**Implements:**
- `VPNG0003-R3.R6`
- `VPNG0003-R3.R6.R1`
- `VPNG0003-R3.R6.R2`
- `VPNG0003-R3.R6.R3`
- `VPNG0007-R7.R5`

The event must identify the availability subject and logical path and carry only the bounded
observation information needed by the Manager.

The event carries normalized `AvailabilityEvidence`.

Local inability to execute the observation mechanism produces `no_evidence` plus diagnostic
state unless the observation contract proves that the failure itself demonstrates path
unusability.

By `VPNG0003-R3.R6.R3`, only evidence that observes a relevant path property may become
`positive` or `negative`.

No requirement currently justifies:

- durable replay;
- global revision numbers;
- a persistent event log;
- a universal ordering service.

## 11.2. Payload state publication

`PayloadTrafficManager -> observers`

**Implements:**
- `VPNG0006-R6.R2`
- `VPNG0006-R6.R4`

The Manager publishes a current projection that distinguishes desired/effective/unknown
state where that distinction affects behavior or safety.

System-wide current status is composed by `RuntimeStatusAgent` from authoritative owner
snapshots; see section 13.

Publication success is separate from convergence success.

If the Manager has already applied and freshly verified the required semantic state but
publishing the resulting current projection fails transiently:

- the verified semantic/physical operation is not blindly repeated solely because the
  publisher failed;
- the owner retains enough current verified projection to retry publication;
- a later audit/reconciliation may republish the current projection without mutating already
  matched lower state;
- unexpected internal programming/runtime faults remain errors and are not converted into a
  fake successful publication state.

This follows `VPNG0005-R5.R3`, `VPNG0006-R6.R3`, `VPNG0006-R6.R4` and keeps mutation retry separate
from information-delivery retry.

# 12. Startup, shutdown and recovery

This pass does **not** introduce a LifecycleManager.

No accepted requirement currently proves that lifecycle orchestration needs an independent
long-lived semantic component.

Instead, the architecture records only required postconditions:

**Implements:**
- `VPNG0001-R1.R2`
- `VPNG0004-R4.R4`
- `VPNG0005-R5`
- `VPNG0005-R5.R1`
- `VPNG0005-R5.R4`
- `VPNG0005-R5.R5`
- `VPNG0005-R5.R6`
- `VPNG0005-R5.R6.R1`
- `VPNG0005-R5.R6.R2`
- `VPNG0005-R5.R6.R3`
- `VPNG0007-R7.R1`

Required orchestration semantics:

1. acquire/establish instance ownership/exclusion needed to prevent competing mutation;
2. before trusting a new candidate configuration, observe and cleanup/contain stale owned
   state from an incomplete or previous instance using only ownership markers/invariants that
   do not depend on successfully parsing the new config;
3. if stale owned state cannot be safely cleaned or contained, do not proceed as though a
   known baseline exists; retain/re-establish protective restriction and report the failure;
4. load and validate the candidate Device/Profile configuration before dependent actuation;
5. construct/verify the managed network domain and protective fail-closed boundary before
   declaring payload ready;
6. create/start runtime components only after their prerequisites exist;
7. external VPN process/interface presence is **not** a general startup-success prerequisite:
   an enabled Profile may reach ready structural policy with zero current paths and remains
   fail-closed until valid bindings appear;
8. materialize current Profile policy from valid bindings and verify required safety/readiness
   postconditions from fresh observation;
9. only then report successful start/readiness;
10. during shutdown, quiesce ongoing activity before deleting state it depends on where
    dependency requires this order;
11. attempt cleanup of independent owned domains even if another cleanup fails;
12. preserve all material failures for observability.

Startup/stop interaction is phase-bounded:

- stop/shutdown handlers must be effective before startup begins creating owned mutable state;
- if a stop is requested during STARTING, finish/abort the current bounded phase safely and do
  not begin later startup phases;
- once startup may have created forwarding-capable or other safety-relevant owned state, stop
  must execute containment/cleanup rather than exit and abandon partial state;
- a stop between lower-state apply and readiness publication must not leave owned forwarding
  active after process exit.

This is the recovered semantic value of the historical
`LOCK -> CLEANUP -> LOAD/VALIDATE -> APPLY -> RUN` ordering. The exact CLI/service-manager
mechanism and exact phase implementation are replaceable.

## 12.0.1. Network-policy activation subassembly

**Implements:**
- `VPNG0004-R4.R4`;
- `VPNG0004-R4.R5`;
- `VPNG0005-R5.R1`;
- `VPNG0005-R5.R6.R1`;
- `VPNG0006-R6.R3`;
- `VPNG0006-R6.R4`.

**Constrained by:**
- `VPNG0007-R7.R1`;
- `VPNG0007-R7.R3.R1`.

This is a bounded procedural subassembly inside startup/reconciliation. It is **not** the
product `start` operation and does not own instance locking, managed-domain creation,
configuration parsing, runtime scheduling, shutdown or user-facing status publication.

Its input is already-normalized lower desired state:

```text
PayloadRoutingDesiredState
CompositeNftDesiredState
current Linux platform allocation
```

It does not invent missing Device NAT/firewall/publication grammar or derive semantic policy.

The activation sequence is:

```text
1. converge/reread ForwardingGate = DISABLED
2. while closed, observe nft namespace + invariant scaffold
3. scaffold handling:
   ABSENT
       -> run existing guarded scaffold bootstrap once
   OWNED + exact invariant scaffold
       -> do not run scaffold-only repair
       -> allow coexisting objects to be classified by the structural transaction
   OWNED + missing invariant chains + no non-scaffold objects
       -> run existing guarded scaffold repair once
   marker/scaffold conflict
       -> fail
   incomplete scaffold + non-scaffold objects
       -> fail: safe scaffold-only repair is not proven for that mixed state
4. run the bounded complete structural transaction
5. READY only when the structural transaction is CONFIRMED
```

The distinction in step 3 is necessary because
`prepare_payload_nft_scaffold_once(...)` is intentionally a scaffold-only mutation unit.
An exact scaffold may already contain legitimate Profile/Device/NAT/publication rules; those
objects are not a reason to run scaffold repair and are instead classified by the complete
cross-domain structural observer. Conversely, repairing an incomplete scaffold while other
objects coexist is not silently generalized beyond the existing evidence.

Any failure after the initial containment phase triggers one independent safety-containment
attempt:

```text
converge/reread ForwardingGate = DISABLED
```

This containment attempt is not a retry of scaffold preparation or structural convergence.
If containment is confirmed, the activation result preserves the original failing stage and
lower diagnostic. If containment cannot be confirmed, the result is a distinct containment
failure and readiness remains false.

No failed scaffold operation or failed structural transaction is retried inside this
subassembly. A later Manager reconciliation may invoke a new activation attempt from fresh
state as required by `VPNG0005-R5.R3`.

The result is a current bounded readiness projection:

```text
READY
    structural transaction confirmed exact state and verified forwarding activation

NOT READY
    failing phase + lower result/diagnostic
    + confirmed failure containment when obtainable
```

This projection is suitable input to later lifecycle/status assembly but is not itself a
global lifecycle state machine.

**Evidence plan:**

- rootless tests for absent/exact/conflicting/partially repairable scaffold states;
- rootless proof that lower failures are not retried and failure containment is distinct;
- privileged disposable-network-namespace test beginning with no `vpn_gate` table:
  bootstrap scaffold, activate a zero-path fail-closed policy without ambient fallback, then
  activate a current VPN path through the same subassembly.

## 12.0.2. Controller instance exclusion and runtime-directory integrity

This is an implementation-safety prerequisite for lifecycle assembly, not a new user-facing
multi-instance feature.

One process that has acquired the controller lifetime lock is the sole process allowed to
orchestrate the managed-domain and network-policy owner boundaries for that deployment
instance. A second process must fail immediately before cleanup, bootstrap or actuation.

The lower normalized deployment input is:

```text
InstanceLockSpec:
    runtime_directory: absolute path
    expected_owner_uid
```

The lock filename is an internal fixed implementation name and is not independently
configurable. The lifecycle layer may later select the runtime-directory path from packaging
or service configuration; this unit does not define external TOML syntax.

Before lock acquisition, the runtime directory is safely ensured/verified:

- the path is absolute;
- if absent and creatable, create it with mode `0700`;
- the final path component must not be a symlink;
- an existing object must be a directory;
- mode must be exactly `0700`;
- owner UID must equal the normalized expected service identity;
- wrong owner/mode/type is a fatal error and is not silently repaired.

The lock file is opened with:

```text
O_RDWR | O_CREAT | O_CLOEXEC | O_NOFOLLOW
mode 0600
```

After opening, `fstat` must confirm a regular file, mode `0600`, and the same expected
owner UID.

The process then attempts:

```text
flock(fd, LOCK_EX | LOCK_NB)
```

and keeps that file descriptor open for the whole controller lifetime.

A busy lock is a distinct `another instance is running` failure. No wait/backoff/retry
belongs to this boundary.

The lock file may remain on disk after process exit. The kernel-held flock, not file
existence/PID text, is authoritative, so a stale regular lock file does not block a later
process after the previous descriptor is gone.

Acquisition happens before any cleanup or managed-domain mutation. If a termination request
arrives before lock acquisition, the process owns no gateway resources and must not perform
cleanup merely because it attempted startup.

This contract intentionally carries forward the previously tested RC2/RC3 lock-path
hardening while avoiding their external path/default as an NG3 product contract.

## 12.0.3. Bounded controller startup assembly

The first executable startup composition is procedural and phase-bounded. It does not create a
LifecycleManager or runtime reconciliation loop.

Inputs are lower/deployment contracts plus a config loader that, after successful validation,
returns a pure current-state desired builder:

```text
InstanceLockSpec
ManagedNetworkDomainSpec
NetworkPolicyPlatformSpace
Linux command runner

load_validated_policy()
    -> PreparedPayloadPolicy

PreparedPayloadPolicy.build_current(
    current host-boundary InterfaceIdentity,
    fresh managed-domain InterfaceIdentity inventory
)
    -> PayloadNetworkPolicyDesiredState
```

The loader/builder seam is intentional:

- candidate config load/validation must happen after controller lock + stale-domain
  containment;
- fresh domain creation must happen only after candidate config has validated;
- current ifindex facts do not exist until the managed domain is present;
- final NAT/firewall/publication external grammar and integration-specific path realization
  remain outside lifecycle orchestration.

The startup sequence is:

```text
1. acquire controller lifetime lock
2. preflight managed domain WITHOUT creating it
       existing -> ForwardingGate=DISABLED + exact infrastructure verify
       absent   -> confirm namespace + host boundary both absent
3. load/validate candidate normalized policy
4. ensure managed domain
       absent -> create contained infrastructure + exact verify
       existing -> repeat contained exact verify
5. fresh managed-domain link inventory
6. pure build_current(host_boundary, interfaces) -> complete payload desired state
7. activate_network_policy(...)
8. READY only when activation is READY
9. return startup session while retaining lifetime lock
```

A busy lock exits before domain/config/policy work.

A config-validation failure occurs before fresh domain creation. If an old exact domain
already existed, it remains protectively closed by preflight.

After successful domain ensure, failure to observe current links or build desired state causes
one explicit `ForwardingGate=DISABLED` containment verification before the lock is released.

Activation failures reuse the activation subassembly's own failure-containment result and are
not retried by startup.

Startup failure does not automatically destroy a successfully verified managed domain. A
contained exact domain is safe reusable infrastructure for a later start; destructive
teardown belongs to explicit stop/cleanup orchestration. Fresh-domain creation failures still
roll back inside the managed-domain lifecycle itself.

A successful startup returns a session object containing the acquired lock and confirmed
lower results. Releasing the lifetime lock while forwarding remains active is not a startup
operation; the future stop/cleanup boundary must quiesce/contain/cleanup before releasing it.

This assembly still does not define:

- the external POSIX-signal/service-manager adapter that supplies the stop-request predicate;
- runtime Manager reconciliation scheduling;
- user-facing readiness/status publication mechanism.

## 12.0.4. Bounded controller stop / owned-domain cleanup

**Implements:**
- `VPNG0005-R5.R4`;
- `VPNG0005-R5.R5`;
- `VPNG0005-R5.R6.R2`;
- `VPNG0006-R6.R3`.

**Constrained by:**
- `VPNG0001-R1.R3.C1`;
- `VPNG0004-R4.R6.R1`;
- `VPNG0007-R7.R1`.

For the currently executable controller lifetime, a READY startup session owns no runtime
Manager/Agent loops yet. Its stop boundary therefore remains procedural rather than inventing
a generic quiesce framework.

The bounded stop sequence is:

```text
require retained controller lifetime lock
    ->
attempt fresh ForwardingGate=DISABLED convergence
    ->
regardless of that result, attempt owned managed-domain teardown
    ->
fresh teardown postcondition:
    named managed namespace absent
    host boundary veth absent
    ->
only after confirmed teardown release controller lifetime lock
```

The teardown attempt is independent from the preceding containment result. Failure to confirm
the gate must not suppress the stronger cleanup attempt of removing the owned network domain.
Conversely, a teardown failure does not justify releasing the lifetime lock while this
controller process remains alive.

Results distinguish:

- **STOPPED** — owned domain absence is confirmed; lifetime lock is released;
- **CLEANUP_FAILED_CONTAINED** — teardown failed, but forwarding closure was independently
  confirmed; lifetime lock remains held for explicit cleanup retry/diagnosis;
- **CLEANUP_FAILED_UNCONTAINED** — teardown failed and forwarding closure is not confirmed;
  lifetime lock remains held and the unsafe/incomplete postcondition is explicit.

A successful domain teardown is a stronger terminal postcondition than a failed earlier gate
observation: once the named namespace and host boundary are freshly confirmed absent, no
VPN-GATE-owned managed forwarding domain remains connected to host traffic.

`VPNG0001-R1.R3.C1` establishes administrator ownership of VPN provisioning and
VPN-specific configuration; it does **not** establish that the runtime lifecycle of a VPN
process executing inside the managed domain must remain administrator-owned.

The in-process bounded-stop implementation deliberately does not enumerate or kill VPN
processes. EXP-049/050 now establish the Release-1 deployment boundary instead: only
administrator-prepared stack-specific VPN systemd units explicitly bound to the managed-domain
lifecycle participate, and systemd supervises/stops their cgroups before VPN-GATE destroys the
managed domain.

The complete supported deployment stop therefore closes forwarding first, stops the
managed-domain lifecycle anchor, confirms the bound VPN unit/cgroup and endpoint are gone, and
only then completes `stop_controller_once(...)` managed-domain teardown. Arbitrary
administrator processes that were not bound through this contract are neither adopted nor
silently killed.

The current bounded stop has no generic callback list, retry queue or cleanup registry. When
future runtime Managers/Agents become executable, their independently required quiesce/release
operations must be added as concrete cleanup domains under `VPNG0005-R5.R5`, preserving the
same rule: one cleanup-area failure does not suppress attempts in other independent areas.

## 12.0.5. Bounded controller restart composition

**Implements:**
- `VPNG0005-R5.R6.R3`;
- `VPNG0006-R6.R3`.

**Constrained by:**
- `VPNG0005-R5.R6.R2`;
- `VPNG0007-R7.R1`.

Restart adds no new lifecycle mechanism. It composes the already accepted stop and startup
operations:

```text
restart(current READY session)
    ->
stop_controller_once(...)
    ->
if stop != STOPPED:
    report restart STOP_FAILED
    do not invoke startup
    ->
start_controller_once(...)
    ->
if start READY:
    report restart READY with the new startup session
else:
    report restart START_FAILED with the exact startup result
```

A successful stop releases the prior lifetime lock only after owned-domain absence is
confirmed. The following startup therefore reacquires controller ownership through the normal
hardened lock path and re-establishes all startup postconditions from fresh state.

Restart does not retain a special cross-stop ownership token and does not hide a lock-busy
result from the new startup attempt. If another legitimate controller acquires the deployment
lock after the successful stop and before the new start, this restart attempt fails visibly
rather than bypassing the normal single-controller exclusion contract.

There is no restart-specific retry, rollback journal, saved kernel snapshot or partial-start
resume state. Failure after successful stop leaves the result exactly as the ordinary startup
operation reports it; a later operator action may start again from authoritative state.

## 12.0.6. Phase-bounded STARTING termination checkpoints

**Implements:**
- `VPNG0005-R5.R1`;
- `VPNG0005-R5.R4`;
- `VPNG0005-R5.R5`;
- `VPNG0005-R5.R6.R1`;
- `VPNG0005-R5.R6.R2`;
- `VPNG0006-R6.R3`.

**Constrained by:**
- `VPNG0007-R7.R1`.

The core startup assembly does not own POSIX signal installation or service-manager mechanics.
It accepts one replaceable read-only process-control input:

```text
stop_requested() -> bool
```

The deployment/process adapter must make that input effective before invoking startup if it
needs asynchronous SIGTERM/SIGINT or equivalent stop handling. A signal handler must not run
network mutations; it only records the request. The synchronous controller remains the sole
owner of cleanup ordering.

The startup checkpoints are after bounded phases, never in the middle of a lower mutation:

```text
entry
    -> stop requested: return STOPPED; acquire no lock

acquire lifetime lock
    -> stop requested: release lock; return STOPPED

managed-domain preflight
    -> checkpoint

candidate policy load/validation
    -> checkpoint

managed-domain ensure
    -> checkpoint

fresh interface observation
    -> checkpoint

pure desired-state build
    -> checkpoint

network-policy activation
    -> FINAL STARTING checkpoint BEFORE READY
```

At every checkpoint after confirmed managed-domain preflight, a stop request invokes the same
owned-domain cleanup primitive used by product stop:

```text
attempt ForwardingGate=DISABLED
    ->
independently attempt managed-domain teardown
    ->
confirmed namespace + host-boundary absence
    ->
release lifetime lock
```

No later startup phase may begin after a checkpoint observes the request.

The final checkpoint is safety-critical. If activation has just confirmed an exact active
forwarding policy but a stop request is already pending, startup must not construct/publish a
READY session. It immediately enters cleanup while still holding the original controller
lifetime lock.

A successful interrupted cleanup returns startup `STOPPED`; this is not startup success and
does not expose a READY session.

If interrupted cleanup cannot confirm its required postcondition, startup returns an explicit
`STOP_CLEANUP_FAILED` result carrying a stopping context that retains the acquired lifetime
lock. The caller may inspect/retry cleanup through that retained ownership context; startup
must not silently release the lock or continue to READY.

Ordinary startup phase failure remains an ordinary startup failure. A concurrent stop request
does not rewrite a failed phase into success. Existing phase-specific failure containment
still applies, and no later startup phase is entered.

This unit intentionally does **not** define a POSIX-signal class, event loop, background
thread, retry loop or daemon state machine. Those are replaceable process-interface
mechanisms. The invariant being implemented is only:

```text
asynchronous stop request
    -> observed at the nearest completed bounded startup phase
    -> no later startup phase
    -> if owned managed-domain work has begun, bounded cleanup under the same lock
    -> never READY after an already-observed stop request
```

Historical RC2/RC3 signal-safe STARTING checkpoints are evidence that this interaction is a
real lifecycle boundary; their daemon/event-loop implementation is not inherited.

## 12.1. Product lifecycle control surface

The lifecycle operations required by `VPNG0005-R5.R6` are exposed through a thin product
control surface.

The architecture does not require that surface to be a specific CLI, service manager,
socket or API. Those are replaceable interface mechanisms.

Semantically:

```text
start
    -> run startup orchestration
    -> report success only after required readiness/safety postconditions

stop
    -> run quiesce + cleanup orchestration
    -> report success only after required cleanup postconditions

restart
    -> stop/cleanup as required
    -> start from the resulting authoritative state
    -> never report success while previous required cleanup remains unresolved
```

The control surface is not a long-lived domain Engine and owns no independent lifecycle
policy. It invokes procedural assembly/orchestration whose postconditions are already
defined by the lifecycle requirements.

This keeps product control operations explicit while avoiding a LifecycleManager that has no
independently required semantic state.

For the current scope, procedural lifecycle orchestration remains the accepted architecture.
A dedicated Engine would require a later requirement proving an ongoing semantic
responsibility that cannot be represented by these direct operations.

## 12.2. Local Manager reconciliation

**Implements:**
- `VPNG0005-R5.R2`
- `VPNG0005-R5.R2.R1`
- `VPNG0005-R5.R3`
- `VPNG0005-R5.R3.R1`
- `VPNG0007-R7.R1`
- `VPNG0007-R7.R1.R1`

Any Manager that owns mutable external state keeps the current accepted desired semantic
state and periodically re-observes its own managed domain while the corresponding function
is active.

The reconciliation loop is local to the Manager:

```text
current desired state
        +
periodic audit / relevant event
        |
        v
observe authoritative actual state
        |
        +-- already satisfied --> no physical mutation;
        |                        publish/republish confirmed projection if needed
        |
        +-- drift / previous recoverable failure
                    |
                    v
             converge through Adapter
                    |
                    v
             verify postcondition
```

The periodic audit is a fallback for silent drift. Relevant external or internal events may
trigger earlier reconciliation, but correctness does not depend on receiving such an event.

The exact audit interval is a local implementation parameter unless a later product
requirement makes recovery latency user-visible.

No global scheduler, durable retry queue, missed-tick replay or retry-history journal is
introduced.

If an audit occurs while reconciliation is already active, at most one future reconciliation
need must be retained; multiple equivalent triggers may be coalesced because the next
reconciliation always starts from freshly observed actual state.

A recoverable failure does not enqueue the failed command sequence for replay. The Manager
retains desired semantic state and on a later reconciliation re-observes reality and computes
a new convergence operation from current state.

This architecture makes retry idempotence a property of semantic reconciliation rather than
command replay.

## 12.3. Первая исполняемая alpha-сборка runtime

**Implements:**
- `VPNG0001-R1.R2`;
- `VPNG0001-R1.R3.C1.C1.R1`;
- `VPNG0001-R1.R3.C1.C1.R3`;
- `VPNG0004-R4.R4`;
- `VPNG0004-R4.R5`;
- `VPNG0005-R5.R1`;
- `VPNG0005-R5.R2`;
- `VPNG0005-R5.R3`;
- `VPNG0005-R5.R6.R2`;
- `VPNG0005-R5.R6.R3`;
- `VPNG0007-R7.R1`;
- `VPNG0007-R7.R7`.

**Allowed early implementation by:**
- `VPNG0007-R7.R8.C1`;
- `VPNG0007-R7.R8.R3`.

**Constrained by:**
- `VPNG0001-R1.R2.R4.R6.C1`;
- `VPNG0001-R1.R3.C1.C1`;
- `VPNG0005-R5.C1`.

Первый исполняемый alpha-runtime не вводит новую продуктовую семантику. Он соединяет уже
принятые нижние контракты в один процесс `rou.alpha_runtime` и один systemd deployment
slice.

Startup использует существующий `start_controller_once(...)`. После подтвержденного READY
процесс удерживает controller lifetime lock и запускает локальный
`PayloadTrafficManager`-подобный audit/reconcile loop:

```text
accepted config loaded once at start
    +
retained DeviceBindingState
    +
periodic fresh managed-netns interface observation
        ->
fresh binding projection
        ->
pure current lower desired build
        ->
read-only exact structural audit
        |
        +-- exact + ForwardingGate ENABLED
        |       -> no mutation
        |
        +-- drift / endpoint generation change / recoverable lower failure
                -> guarded activate_network_policy(...)
                -> close forwarding first
                -> converge from fresh authoritative state
                -> verify exact postcondition
```

Audit interval в alpha равен одной секунде и является локальным implementation parameter по
§12.2, а не пользовательской latency guarantee. Config hot-reload не вводится: изменение
конфигурации требует нового start/restart и тем самым не создает неоговоренную live-change
semantics.

Alpha deployment использует:

```text
vpn-gate-alpha.service
    Type=notify
    RuntimeDirectory=/run/vpn-gate-alpha
    -> runtime создает /run/netns/vpn-gate-alpha
    -> READY=1 только после подтвержденной fail-closed startup policy

stack-specific VPN unit
    BindsTo=vpn-gate-alpha.service
    After=vpn-gate-alpha.service
    NetworkNamespacePath=/run/netns/vpn-gate-alpha
```

`Type=notify` нужен для фактической ordering semantics: start job controller unit завершается
только после появления managed namespace и подтвержденного startup postcondition, поэтому
последующий VPN unit не пытается открыть еще не существующий `NetworkNamespacePath`.

При штатном `systemctl stop vpn-gate-alpha.service` reverse systemd ordering сначала
останавливает bound VPN unit/cgroup; затем controller получает stop, выполняет
`stop_controller_once(...)` и подтверждает отсутствие managed namespace + host boundary.

Первый alpha evidence slice был собран до принятия финальной Device grammar и поэтому
исторически использовал internal `NatIntent.NONE`, omitted Device firewall, no publication
и remote-side return route. После configuration-format review это является только описанием
EXP-051 evidence topology, а не текущей Release-1 grammar или новым constraint.

Canonical Release-1 configuration теперь определяется `design/NG3/config-model.md`.
Ранний Python runtime может реализовывать только подмножество этих capability, но обязан
явно отклонять запрошенную ещё не materialized capability вместо silent ignore.

Если periodic audit обнаруживает exact managed-domain mismatch, alpha пытается прежде всего
подтвердить `ForwardingGate=DISABLED` и публикует diagnostic в journal; он не усыновляет
произвольные процессы или вручную поврежденные namespace artifacts.

Python alpha публикует current-only `RuntimeStatusAgent` snapshot атомарно в
`/run/vpn-gate-alpha/status.json`. Journal markers остаются implementation/evidence
diagnostics и не объявляются финальным stable status interface.

# 13. RuntimeStatusAgent

**Component type:** Agent

**Implements:**
- `VPNG0006-R6`
- `VPNG0006-R6.R1`
- `VPNG0006-R6.R2`
- `VPNG0006-R6.R3`
- `VPNG0006-R6.R4`
- `VPNG0007-R7.R1`
- `VPNG0007-R7.R1.R1`
- `VPNG0007-R7.R3.R1`
- `VPNG0007-R7.R5`

The Agent observes current projections published by the Engines that own product domains and
composes a user-facing current status snapshot.

It is deliberately an Agent rather than a Manager because it does not actuate or own the
represented domains.

Inputs are current-snapshot InfoEvents, including where applicable:

- accepted/configured intent reported by the owner that accepted it;
- current logical VPN-path binding/effective path information;
- current payload policy/effective ordering;
- availability observation/diagnostic state;
- lifecycle/readiness/cleanup failures;
- lower-domain convergence failures that prevent required postconditions.

The Agent stores only the latest relevant snapshot per authoritative source. It does not
store event history, reconstruct past transitions or become a system-of-record.

Conceptual output:

```text
RuntimeStatusSnapshot:
    configured_intent
    confirmed_effective_state
    availability_state
    readiness
    blocking_problems
    unknown_or_unconfirmed_fields
```

Availability presentation in the current alpha uses only bounded current state:

- `disabled` — Profile availability is not configured;
- `unconfirmed` — availability-enabled Profile exists, but current runtime/reconcile truth is
  not confirmed;
- `monitoring` — the availability cycle is current and no confirmed problem owner exists for
  that Profile;
- `problem` — at least one current `(Profile, logical path)` owner has an established
  availability problem.

`monitoring` deliberately does not claim that every remote target is positively proven
healthy; it states that current availability machinery is operating and has no established
problem state.

Truthfulness rules:

- a desired/configured value is never reported as confirmed actual merely because it was
  requested;
- missing or stale authoritative information is represented as unknown/unconfirmed;
- a local source retains ownership of its semantic truth; the StatusAgent only composes;
- conflicting snapshots are surfaced as an inconsistency/problem rather than resolved by a
  hidden status policy;
- current status contains no unbounded history.

The presentation mechanism is outside this component contract. CLI, API, text output or
another user-facing surface may render the same current `RuntimeStatusSnapshot` without
changing status semantics.

Historical work discussed a dedicated aggregated `ProfileState` combining binding,
payload-rules, publication and probe diagnostics. That aggregation was explicitly not
finalized in the recovered material and is **not** imported as an NG3 requirement here.
Current R6 remains satisfied by truthful composition of authoritative snapshots; any stronger
Profile-specific verdict model requires separate requirement work.

A final status query therefore does not require direct knowledge of kernel commands or
internal Manager state.

## 13.1. Target production runtime implementation boundary

**Implements:**
- `VPNG0007-R7.R8`;
- `VPNG0007-R7.R8.R1`;
- `VPNG0007-R7.R8.R2`;
- `VPNG0007-R7.R8.R3`.

**Constrained by:**
- `VPNG0007-R7.R8.C1`.

Rust is a target **implementation boundary**, not a new component role and not a source of
product semantics. The component contracts, requirement trace and observable network
behavior defined by this architecture remain authoritative across the implementation-language
transition.

The final production/stable runtime boundary includes code that participates in:

```text
configuration normalization
lifecycle / runtime state
policy calculation and reconciliation
VPN-path observation
OS/network-state observation and actuation
```

For the first release that claims conformance to this production boundary, those runtime
responsibilities must execute from the Rust implementation. A Python module is not allowed to
remain a hidden production-path dependency merely because it was the original executable
reference.

The current `design/NG3/code/python/rou/` implementation has a different role:

```text
accepted requirements + architecture contracts
        |
        +--> executable Python reference/evidence
        |
        +--> later Rust production implementation
                |
                +--> must preserve the same product semantics
```

By `VPNG0007-R7.R8.C1`, alpha/beta releases may ship the Python reference runtime while the
product semantics and integration applicability are still being proven. Such a release must
not be described as the final production/stable implementation boundary.

Code outside the runtime boundary may continue to use the language most appropriate to its
job. In particular, disposable experiments, CI/evidence harnesses, test fixtures,
build/install tooling, code generation and research/reference implementations do not need to
be rewritten solely to satisfy the runtime-language requirement.

### Unsafe/FFI boundary

Production Rust defaults to safe Rust. Any `unsafe` block or memory-unsafe FFI boundary must:

- exist only where a required lower mechanism cannot be expressed through the safe boundary
  already available;
- be localized behind a narrow technical contract;
- document the invariant that makes the unsafe operation sound;
- have focused tests/evidence for that boundary;
- not be used to bypass ownership/state invariants that can be expressed in safe Rust.

A broad `unsafe` implementation is not considered compliance merely because the source
language is Rust.

### First Rust production-boundary slice

The initial executable Rust production-boundary unit is deliberately a pure contract:
`design/NG3/code/rust/vpng-runtime/src/availability_confirmation.rs`.

It implements the same bounded availability confirmation state transition already represented
by the Python reference `availability_confirmation.py`:

```text
current AvailabilityConfirmationState
+ current AvailabilityOutcome
+ finite local degradation/recovery thresholds
    ->
next AvailabilityConfirmationState
```

This first slice is selected because it has no Linux I/O, scheduling, parser grammar, FFI or
lifecycle ownership. It therefore proves the production-language contract and test/evidence
shape without simultaneously changing a lower mechanism.

The Rust crate applies `#![forbid(unsafe_code)]` at crate scope. No FFI or `unsafe` boundary
is introduced.

During migration, Python remains executable reference/evidence for early releases under
`VPNG0007-R7.R8.C1`. A Rust unit replaces production responsibility only when its complete
upstream/downstream contract has been ported and acceptance evidence demonstrates semantic
parity; the existence of a Rust implementation alone does not remove or bypass the Python
reference path.

The next dependency-adjacent Rust unit ports the pure
`AvailabilityPriorityCalculator` contract together with a reusable `LogicalPathId` value
type. Its boundary remains:

```text
configured allowed logical-path order
+ established problem paths
+ current Profile active path
+ Profile-local reserve Device membership
    ->
same logical-path membership in effective preference order
```

The Rust calculator is not allowed to mutate routes, own active-path lifecycle, infer path
health, or change structural membership. Those responsibilities remain in the existing
Manager/lower convergence contracts.

The next Rust parity slice ports the bounded `AvailabilityRoutingState` projection for one
Profile. It owns only the previously accepted active-path identity and returns:

```text
previous active path
+ current configured path membership
+ established problem paths
+ reserve Device membership
    ->
next active path
+ current effective path order
```

A disappeared active path is treated as stale bounded state and replaced from current
membership. All-problem or empty membership clears the active identity. The Rust projection
delegates ordering semantics to the Rust `AvailabilityPriorityCalculator`; it performs no
routing I/O and does not own confirmation state.

The next Rust unit ports the bounded semantic core of `AvailabilityManager` together with
the current probe-context value types required by that core. The port owns:

```text
current synchronized observation contexts
+ fresh ProbeEvidence
+ bounded confirmation state
+ per-Profile active routing state
+ already-normalized Profile/path membership
    ->
problem owners
+ effective Profile/path order
```

Context replacement resets partial confirmation for that subject; stale evidence is rejected;
`NO_EVIDENCE` is neutral; reserve/ordinary recovery semantics reuse the previously ported
routing-state projection.

This is intentionally **manager-core parity**, not yet the complete Rust ConfigurationAdapter
or alpha assembly. The Python implementation currently also verifies that the supplied
Profile set equals the enabled Release-1 config Profile set. Until Rust configuration
normalization is ported, the Rust Manager core accepts an already-normalized current Profile
set and validates only duplicate Profile identity and probe-context membership. A later Rust
configuration/assembly unit must restore the complete upstream set-equality gate before this
core can replace that production responsibility.

### Migration/evidence rule

Porting Python reference behavior to Rust is an implementation replacement, not a redesign.
The Rust unit must trace to the same R/C and architecture contract as the behavior it
replaces. A semantic difference discovered during porting is returned to requirement/design
review instead of being justified as a language-port artifact.

Sufficient evidence for the final production-language transition includes:

- unit/contract evidence for the Rust implementation against the accepted normalized domain
  contracts;
- end-to-end regression of the product scenarios used to accept the corresponding Python
  reference behavior;
- packaging evidence that the claimed production runtime does not execute Python runtime
  modules;
- an auditable inventory of production `unsafe`/memory-unsafe FFI boundaries and their
  local justifications.

No dual-runtime abstraction, plugin language layer or generic FFI framework is introduced
until a separate requirement requires it.

# 14. Requirement coverage in this architecture pass

| Requirement area | Architecture status |
| --- | --- |
| `VPNG0001-R1.R1` forwarding | represented by PayloadTrafficManager + NetworkPolicyAdapter |
| `VPNG0001-R1.R2` declarative operation | canonical Release-1 Device/Profile grammar fixed in `config-model.md` and normalized by ConfigurationAdapter; only endpoint-scoped future firewall selector remains deferred |
| `VPNG0001-R1.R3` VPN-channel service | logical path identity/binding and administrator onboarding architecture accepted |
| `VPNG0001-R1.R3.C1` first-release admin provisioning | accepted constraint; no VPN provisioning Manager |
| `VPNG0001-R1.R3.C1.R1` admin instructions/contract | required onboarding contents architecturally defined; concrete per-integration documents remain implementation work |
| `VPNG0001-R1.R3.C2` isolated VPN data-plane endpoint | architecture constraint derived from managed-network isolation |
| `VPNG0001-R1.R3.C2.R1` isolated-channel onboarding result | placement result architecture accepted; concrete provisioning commands remain implementation-specific |
| `VPNG0002-R2` subtree — payload policy | Profile destinations/direction/device_order compile deterministically through PayloadPolicyCalculator |
| `VPNG0003-R3.R1`–`VPNG0003-R3.R5`, `VPNG0003-R3.R7` path ordering/adaptation | represented by PayloadTrafficManager + AvailabilityPriorityCalculator |
| `VPNG0003-R3.R6` subtree — path-usability evidence | subject-specific user criterion accepted; Profile selects disabled, Device default, or same-shape Profile override, normalized to a concrete ICMP/IPv4 description before probe runtime |
| `VPNG0004-R4` subtree — safety | isolation, verified convergence, make-before-break priority permutation and guarded structural transition accepted |
| `VPNG0005-R5.R1`, `VPNG0005-R5.R4`, `VPNG0005-R5.R5`, `VPNG0005-R5.R6` lifecycle | postconditions and thin control surface represented; long-lived LifecycleManager intentionally absent |
| `VPNG0005-R5.R2`, `VPNG0005-R5.R3` recovery | local Manager reconciliation with periodic audit and fresh observation; no retry queue/replay |
| `VPNG0006-R6.R1` configured intent visibility | RuntimeStatusAgent composes owner-published accepted intent |
| `VPNG0006-R6.R2`, `VPNG0006-R6.R4` effective/truthful state | RuntimeStatusAgent composes authoritative current snapshots and preserves unknown/unconfirmed state |
| `VPNG0006-R6.R3` system failure visibility | RuntimeStatusAgent aggregates current blocking diagnostics without becoming policy owner |
| `VPNG0007-R7` subtree — implementation quality | applied as cross-cutting architecture rules; target production runtime language boundary is Rust, with Python allowed for early/reference releases under R7.R8.C1 |

# 15. Deliberately omitted machinery

The following are deliberately absent from this first architecture because no accepted NG3
requirement currently makes them necessary:

- global event journal;
- generic reliable replay bus;
- universal revision/epoch framework;
- global state machine for availability;
- attempt-history storage;
- separate route-priority Manager;
- separate availability route writer;
- independent lifecycle Engine;
- configuration super-object containing every subsystem detail;
- universal probe mechanism abstraction beyond the narrow Driver contract;
- kernel-specific routing allocation objects in upper Managers.

This omission is an implementation of `VPNG0007-R7.R1`, not a claim that such machinery can
never become necessary.

# 16. Implementation freedoms and future extensions

## 16.1. Remaining configuration semantics

The configuration boundary itself is now defined and the VPN-path binding contract is
architecturally closed.

The core Device/Profile human-facing configuration contract is now recovered and recorded in
`design/NG3/config-model.md`.

Remaining interface freedom is narrower:

- parser/serialization implementation details that do not change accepted TOML semantics;
- any future live-change/reload capability, which is not currently promised;
- future endpoint-scoped Device firewall syntax under its explicit Release-1 constraint;
- lower implementation of accepted publication/gateway-NAT capabilities where architecture
  already defines the semantic ownership but complete physical materialization remains work.

These freedoms must not be expanded into a universal configuration framework without a new
requirement.

## 16.2. Availability description resolution

The product semantics and architecture boundary are now defined:

- availability is subject-specific (Profile + logical VPN path);
- Device may carry one reusable default probe description;
- Profile independently selects no check, Device default, or its own same-shape description;
- Device default and Profile override both normalize to the same concrete ICMP + exact IPv4
  runtime description;
- `AvailabilityDescriptionResolver` performs this pure selection before probe runtime;
- selecting Device default does not merge evidence or health state across Profiles;
- missing selected defaults are configuration errors, not runtime target-derivation problems;
- runtime interface/peer/routing observations are not used to invent probe targets.

Future TCP/UDP/HTTP mechanisms remain outside current scope.

## 16.3. User-visible status presentation

Status aggregation semantics and ownership are now defined by `RuntimeStatusAgent`.

Still replaceable as interface implementation detail:

- concrete CLI/API/text presentation format;
- formatting and filtering for different operator surfaces.

These do not require another domain component unless later product requirements make
presentation behavior itself semantic.

## 16.4. Lifecycle ownership

Affected requirements:
- `VPNG0005-R5.R1`
- `VPNG0005-R5.R2`
- `VPNG0005-R5.R3`
- `VPNG0005-R5.R4`
- `VPNG0005-R5.R5`
- `VPNG0005-R5.R6`

Lifecycle control semantics and autonomous local reconciliation are now explicit. They
still do not justify a separate global lifecycle component.

For the first release, VPN provisioning and VPN-specific configuration remain outside
VPN-GATE ownership by `VPNG0001-R1.R3.C1`. For a supported in-stack VPN process, however,
EXP-049/050 establish the systemd-bounded lifecycle boundary: the administrator supplies the
stack-specific unit/configuration, systemd supervises its process/cgroup, and deployment stop
ordering removes the explicitly bound VPN runtime before VPN-GATE destroys the managed
network domain.

Procedural controller assembly plus systemd dependency ordering remains the simpler accepted
architecture; a separate global LifecycleManager is still unnecessary.

## 16.5. Administrator-facing VPN-channel onboarding implementation

The onboarding architecture is closed:

- the administrator provisions/configures the external channel;
- its data-plane endpoint must be present inside the managed domain;
- configuration binds a stable logical path identity to one verified current endpoint;
- availability-check description may be Profile-owned or inherited from the corresponding Device default;
- acceptance/rejection and unresolved target/binding conditions are observable.

Remaining work is concrete documentation and integration implementation for each supported
VPN technology.

# 17. Current architecture principle

For this NG3 pass:

> If a component cannot point to a requirement, it does not enter the architecture.

And conversely:

> A requirement is allowed to remain without architecture until its semantics are concrete
> enough to justify one.
