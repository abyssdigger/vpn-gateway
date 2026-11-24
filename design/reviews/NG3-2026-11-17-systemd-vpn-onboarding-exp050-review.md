# VPN-GATE NG3 — Release-1 systemd VPN onboarding and EXP-050 lifecycle review

> **Current requirement mapping (2026-11-20):** the systemd-specific requirement subtree
> used by this historical review was later normalized without changing the accepted systemd
> architecture/evidence:
>
> - historical `VPNG-U001-R1.R3.C1.C1` -> current `VPNG-U001-R1.R3.C3`
>   (external VPN runtime lifecycle ownership/supervision constraint);
> - historical `VPNG-U001-R1.R3.C1.C1.R1` -> current `VPNG-U001-R1.R3.C3.R1`
>   (external lifecycle integration contract);
> - historical `VPNG-U001-R1.R3.C1.C1.R2` -> current `VPNG-U001-R1.R3.C1.R1.R2`
>   (policy-neutral administrator onboarding configuration);
> - historical `VPNG-U001-R1.R3.C1.C1.R3` -> current `VPNG-U001-R1.R2.R4.R6.R4`
>   (Device client-side VPN transport/control intent).
>
> The concrete systemd/`NetworkNamespacePath`/`BindsTo`/`After` mechanism remains selected
> architecture and evidence, not current generic requirement wording.

> **Current requirement interpretation (2026-11-20):** `VPNG-U005-R5.C1` now serves only as
> the boundary of required automatic recovery/adoption after unsupported external
> intervention. Historical statements below that directly attribute a blanket
> fail-closed reaction to `C1` preserve the review's original reasoning, but current
> containment/readiness behavior is justified by the specific safety/readiness invariant
> that was lost.

**Date:** 2026-11-17  
**Cycle:** `ng3-design-cycle-20261117-systemd-vpn-onboarding-exp050-35m`  
**Evidence run:** `44072821011`  
**Evidence commit:** `12942efbb8de40b0381f1de454aecf23c8a1a5fb`

## Scope

This review closes the Release-1 administrator-managed VPN integration boundary discovered by
EXP-049 and the dependent bounded lifecycle gate required by EXP-050.

The reviewed unit covers:

- administrator/systemd onboarding into the managed network namespace;
- bounded integration-local transport admission;
- first-release ownership boundaries;
- normal VPN `systemctl start/stop/restart` semantics while the managed domain remains alive;
- deployment-level stop ordering before managed-domain destruction;
- changed VPN-specific configuration;
- aggressive VPN-specific configuration;
- administrator documentation for OpenVPN, WireGuard/wg-quick and OpenConnect.

It does not introduce automatic vendor-unit discovery/adoption or a custom VPN process
supervisor.

## Requirement trace

Primary closure:

- `VPNG-U001-R1.R3.C1.R1.R1`;
- `VPNG-U001-R1.R3.C1.C1`;
- `VPNG-U001-R1.R3.C1.C1.R1`;
- `VPNG-U001-R1.R3.C1.C1.R2`;
- `VPNG-U001-R1.R3.C1.C1.R3`;
- `VPNG-U005-R5.C1`;
- `VPNG-U005-R5.C1.R1`;
- `VPNG-U007-R7.R7.R1`;
- `VPNG-U007-R7.R7.R1.R1`.

The existing lifecycle/safety requirements under `VPNG-U005-R5` remain the normative
postcondition and cleanup basis.

## F1 — systemd is the Release-1 VPN process supervisor

The accepted operational shape is:

```text
administrator
    -> VPN-specific configuration
    -> distinct stack-specific VPN systemd unit/instance/drop-in

systemd
    -> process/cgroup supervision
    -> start/stop/restart
    -> dependency/ordering propagation

VPN-GATE
    -> managed network domain
    -> fail-closed network policy
    -> bounded local transport admission
    -> fresh endpoint observation/binding/reconciliation
```

The stack-specific VPN unit is bound to the managed domain with semantics equivalent to:

```ini
[Unit]
BindsTo=<managed-domain/controller unit>
After=<managed-domain/controller unit>

[Service]
NetworkNamespacePath=<managed-netns path>
```

This preserves ordinary administrator `systemctl start/stop/restart` behavior without
requiring VPN-GATE to implement PID tracking, process-tree discovery or restart supervision.

**Disposition:** accepted.

## F2 — automatic unit capture is not needed for Release 1

Release 1 does not need to discover, clone, patch, enable, disable or adopt arbitrary vendor
systemd units.

The administrator prepares a distinct stack-specific service identity. A separate instance of
a vendor template is preferred when available; an alias is not treated as a separate service.

Future automatic unit capture/configuration remains an optional later feature, not an alpha
prerequisite.

**Disposition:** accepted as a first-release constraint.

## F3 — real integration transport requires an explicit owned local-policy class

The initial EXP-049 FAIL demonstrated that exact endpoint placement/binding was insufficient:
terminal managed `stack_input` / `stack_output` DROP killed the OpenVPN underlay.

The repaired implementation adds one bounded semantic owner:

```text
IntegrationLocalTransportIntent
    integration_id
    protocol
    current host-boundary identity
    exact managed local IPv4
    exact remote IPv4
    exact remote port
    optional exact local port
```

It participates in the existing structural/composite observe/compare/converge transaction with
missing/stale/conflict classification and owner marker:

`vpn-gate:ng3:local-integration-v1`

No ambient socket discovery or blanket local permit was introduced.

The final OpenVPN evidence uses exact UDP server port `11940` and exact client port
`11941`, so both directions are exact on ports and endpoint/boundary identity.

**Disposition:** accepted.

## F4 — EXP-049 now passes through the actual administrator/systemd shape

The final applicability evidence runs the OpenVPN client as a real systemd service with
`NetworkNamespacePath` into the managed namespace.

Both clean cycles prove:

- VPN service MainPID inside the managed netns;
- real `vpn0` created there;
- fresh exact binding;
- production local integration rules;
- production network-policy activation;
- controlled payload traversal;
- unrelated local underlay ICMP remains blocked;
- normal service stop removes the VPN endpoint;
- managed-domain cleanup reaches absence.

The historical failed EXP-049 result remains retained because it is the evidence that forced
the local-integration owner class.

**Disposition:** `VPNG-U001-R1.R3.C1.R1.R1` repaired from
`[rejected_closure]` to `[closed]`.

## F5 — EXP-050 passes same-config and changed-config restart

Two clean lifecycle cycles passed.

Same-config restart:

```text
cycle 1: pid 4872 / ifindex 2 -> pid 5048 / ifindex 3
cycle 2: pid 5665 / ifindex 2 -> pid 5840 / ifindex 3
```

Changed VPN-specific configuration:

```text
tun-mtu = 1400
cycle 1: pid 5221 / vpn0 ifindex 4 / mtu 1400
cycle 2: pid 6015 / vpn0 ifindex 4 / mtu 1400
```

Fresh NG3 observation/reconciliation used the new endpoint generation and controlled payload
passed. No old process/interface generation was required.

**Disposition:** bounded service restart through systemd is accepted.

## F6 — bounded deployment stop prevents orphan VPN namespace holders

The successful tested stop sequence is:

```text
ForwardingGate DISABLED
    ->
stop managed-domain systemd lifecycle anchor
    ->
BindsTo / reverse After ordering stops bound VPN unit
    ->
confirm service inactive
    + old MainPID absent
    + cgroup empty
    + vpn0 absent
    ->
VPN-GATE managed-domain cleanup
    ->
confirm namespace + host boundary absent
```

This directly addresses the namespace-retention concern without a custom process manager.

The in-process `stop_controller_once(...)` remains intentionally scoped to VPN-GATE-owned
network resources. The deployment/systemd boundary stops the explicitly bound VPN cgroups
before final domain destruction.

**Disposition:** accepted.

## F7 — aggressive VPN configuration is bounded by the supported integration contract

The aggressive OpenVPN case attempted a route plus an external hook that would modify RPDB,
nft, sysctl and a marker file.

Under the supported integration contract:

- `route-noexec` prevented OpenVPN route materialization;
- arbitrary external scripts were not elevated with `script-security 2`;
- no aggressive route/RPDB/nft/sysctl marker was produced;
- OpenVPN explicitly diagnosed the forbidden hook and the systemd service failed visibly.

Therefore the safe first-release contract is not “accept arbitrary legacy VPN hooks inside the
stack.” It is policy-neutral VPN configuration plus explicit externalization/prohibition of
conflicting managed-domain mutations.

For wg-quick the analogous documented restriction is `Table = off` plus removal/externalization
of conflicting hooks. OpenConnect uses an administrator-owned wrapper/template because no
automatic service adoption is required by the product contract.

**Disposition:** accepted.

## F8 — direct root damage remains outside the supported lifecycle

Deleting or mutating VPN-GATE-owned namespace/veth/dependency artifacts out of band is
administrator intervention.

VPN-GATE must remain fail-closed and diagnostic when such invariant loss is observable, but
Release 1 need not forensic-adopt arbitrary processes or namespace references left by manual
root damage.

The administrator documentation states this boundary.

**Disposition:** accepted.

## Component-model review

The implementation remains consistent with the component model:

- integration transport facts are normalized semantic input;
- desired local integration rules are a pure policy projection;
- strict observer/comparator owns lower interpretation;
- mutation is a bounded Executor/Adapter responsibility;
- systemd, not a new VPN-GATE Manager, supervises VPN process trees;
- existing controller/network-policy transactions remain the owner of managed network state.

No new universal process manager, durable lifecycle journal, callback registry, arbitrary
service adoption layer or ambient-socket policy inference was introduced.

## Simplification review

Explicitly avoided:

- custom VPN PID/cgroup registry;
- arbitrary namespace-holder discovery;
- automatic vendor-unit cloning;
- blanket INPUT/OUTPUT established-flow permission;
- generic privileged hook execution;
- translating arbitrary VPN helper scripts into Device/Profile policy;
- a second independent nft convergence path.

The new implementation exists only because the real EXP-049 failure required a concrete
supported-integration local transport owner.

## Evidence

Final privileged/systemd run:

`44072821011`

Evidence commit:

`12942efbb8de40b0381f1de454aecf23c8a1a5fb`

All NG3 workflow jobs passed, including:

- unit suite;
- route-priority;
- policy-platform;
- structural-inventory;
- forwarding-barrier;
- nft owner/scaffold;
- payload NAT/forward convergence;
- endpoint provenance;
- combined EXP-049 + EXP-050 Debian 13/systemd job.

Experiment markers include:

```text
EXP049_RESULT=PASS
EXP050_CYCLE_1_START=PASS
EXP050_CYCLE_1_RESTART_SAME_CONFIG=PASS
EXP050_CYCLE_1_RESTART_CHANGED_CONFIG=PASS
EXP050_CYCLE_1_AGGRESSIVE_SUPPORTED_CONTRACT=PASS
EXP050_CYCLE_1_SYSTEMD_BOUNDED_VPN_STOP=PASS
EXP050_CYCLE_1_RESULT=PASS
EXP050_CYCLE_2_START=PASS
EXP050_CYCLE_2_RESTART_SAME_CONFIG=PASS
EXP050_CYCLE_2_RESTART_CHANGED_CONFIG=PASS
EXP050_CYCLE_2_AGGRESSIVE_SUPPORTED_CONTRACT=PASS
EXP050_CYCLE_2_SYSTEMD_BOUNDED_VPN_STOP=PASS
EXP050_CYCLE_2_RESULT=PASS
EXP050_RESULT=PASS
```

## Requirement-state inventory

### `decomp`

Six accumulated links remain resolved:

1. `VPNG-U001-R1.R2`: `VPNG-U005-R5 -> VPNG-U005-R5.R6`.
2. `VPNG-U001-R1.R3.C1.R1`: `VPNG-U004-R4.R6 -> VPNG-U004-R4.R6.R1`.
3. `VPNG-U001-R1.R3.C1.R1`: `VPNG-U001-R1.R3 -> VPNG-U001-R1.R3.R2`.
4. `VPNG-U001-R1.R3.C1.R1`: `VPNG-U001-R1.R2 -> VPNG-U001-R1.R2.R2`.
5. `VPNG-U001-R1.R3.C2.R1`: `VPNG-U004-R4.R6 -> VPNG-U004-R4.R6.R1`.
6. `VPNG-U004-R4.R6.R1.R6.R1`: `VPNG-U001-R1.R3 -> VPNG-U001-R1.R3.R2`.

Pending `decomp`: **none**.

### `unreal`

**none**

### `broken`

**none**

### `[rejected_closure]`

**none**

## Mechanical requirement check

```text
normative R/C nodes:                    154
closed:                                 154
pending_closure:                          0
rejected_closure:                         0
open/malformed:                           0
closed without architecture reference:    0
decomp links:                              6, all resolved
active unreal:                             0
active broken:                             0
```

## Verdict

**PASS.**

The Release-1 supported VPN boundary is now small and evidence-backed: administrator-prepared
stack-specific systemd services, systemd process supervision, VPN-GATE-owned managed network
policy, explicit bounded transport facts, and policy-neutral VPN-specific configuration.

The next logical unit can stop designing VPN lifecycle and move toward the first functioning
alpha deployment/runtime assembly.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005-R5` -> `VPNG-M001-R1.R1`
- `VPNG-U005-R5.C1` -> `VPNG-M001-R1.R1.C1`
- `VPNG-U005-R5.C1.R1` -> `VPNG-M001-R1.R1.C1.R1`
- `VPNG-U005-R5.R6` -> `VPNG-M001-R1.R1.R6`
- `VPNG-U007-R7.R7.R1` -> `VPNG-D001-R1.R1.R7.R1`

The original IDs in the historical body are intentionally preserved.
