# NG3 2026-11-18 — Linux VPNPathAdapter runtime collection review

## Verdict

**PASS for the executable Linux/alpha observation boundary.**

The accepted `VPNPathAdapter` architecture is now represented by one explicit stateless Linux
runtime Adapter rather than duplicated raw interface-observation code in controller startup and
periodic alpha reconcile.

## Requirements

**Implements:**

- `VPNG0001-R1.R3.R1`;
- `VPNG0001-R1.R3.R2`;
- `VPNG0001-R1.R3.R3`;
- `VPNG0001-R1.R3.R4`;
- `VPNG0001-R1.R3.R4.R1`;
- `VPNG0001-R1.R3.R4.R2`;
- `VPNG0001-R1.R3.R4.R3`;
- `VPNG0001-R1.R3.R4.R3.R1`;
- `VPNG0001-R1.R3.R4.R4`;
- `VPNG0004-R4.R6.R1.R4`;
- `VPNG0007-R7.R3`;
- `VPNG0007-R7.R5`.

No R/C wording or closure state changed.

## Implementation

Added `linux_vpn_path_adapter.py`.

One observation does exactly:

```text
fresh full managed-netns ip-link snapshot
    -> strict current InterfaceIdentity(ifname, ifindex) inventory
    -> optional exact verified host-boundary generation requirement
    -> current tuple of concrete interface identities
```

The Adapter retains no inventory, generation history, binding state, timer or retry state.

The existing `DeviceBindingState` and `project_device_bindings(...)` remain the separate
bounded current binding projection owned by the payload/controller layer. The new lower
Adapter therefore does not become a second logical-path state owner.

## Production-shaped wiring

Both executable paths now consume the same Adapter:

- bounded controller startup;
- periodic alpha reconcile.

The previous duplicated inline raw `ip -j link show` observation is removed from both paths.

The alpha's one-second periodic timer remains only a wakeup cadence. Every tick obtains a new
authoritative snapshot. No event payload or previous snapshot is treated as current truth.

## Failure semantics

A lower observation command failure or invalid inventory raises
`VpnPathObservationError`. It is never converted to an empty endpoint set.

When a previously verified host-boundary `InterfaceIdentity` is required, a same-name
interface with a different ifindex does not satisfy the observation. This preserves the
existing concrete-generation safety contract.

Binding selector ambiguity remains the existing projector's error and is not hidden by the
Adapter.

## Evidence

Workflow `44345359341` on implementation head
`47bfaddcb1eca7c6c236819c6a77e517c64e2c7d`:

- unit job `134946162925` — **success**;
- installed Debian 13 alpha smoke job `134946163432` — **success**.

The installed alpha continued to prove the full live path, including:

```text
EXP051_RUNTIME_STATUS_ZERO_PATH=PASS
EXP051_FIRST_PAYLOAD=PASS
EXP051_RUNTIME_STATUS_FIRST_PATH=PASS
EXP051_ROUTE_RETURN_HOST_LOCAL_REPLY=PASS
EXP051_RUNTIME_STATUS_NEW_GENERATION=PASS
EXP051_VPN_ONLY_RESTART_RECONCILED=PASS:...old_ifindex=2:new_ifindex=3
EXP051_STACK_STOP_CLEAN=PASS
EXP051_RESULT=PASS
```

The overall workflow remains red because the inherited
`linux-nft-marked-host-bootstrap` job runs EXP-057, the intentionally failed/rejected shared
mark bootstrap alternative. That job is not evidence against this unit.

## Review findings

### F1 — raw observation was duplicated above the accepted Adapter boundary

Startup and periodic reconcile each issued and parsed the current link snapshot directly.

**Disposition:** fixed by routing both through `LinuxVpnPathAdapter`.

### F2 — the Adapter must not steal Device binding lifecycle ownership

A tempting implementation would retain previous interface inventory or stable slots inside
the Linux Adapter.

**Disposition:** rejected. The Adapter is stateless. Existing bounded
`DeviceBindingState` remains the only retained binding projection state.

### F3 — host-boundary same-name replacement must fail the current observation

Name-only validation would allow a recreated boundary endpoint to inherit the old generation's
authority.

**Disposition:** the Adapter optionally requires the exact verified
`InterfaceIdentity(ifname, ifindex)`; same-name/new-ifindex is an observation failure.

## Architecture/gap consequence

The current executable reference no longer has a separate "full VPNPathAdapter runtime
collection" gap. It has a real fresh-observation Adapter used by startup and periodic alpha
runtime.

No requirement makes Netlink event delivery itself semantic. Netlink may later replace or
supplement the polling wakeup mechanism, but the authoritative decision boundary remains the
fresh full snapshot.

Remaining separately-gated executable gaps are now:

- Profile ordinary-side `+snat` physical materialization;
- availability probe execution/runtime assembly;
- stable production packaging/version lifecycle and a stable external status API.

## Requirement-state inventory

No requirement-state transition occurred.

- resolved `decomp`: six, unchanged;
- pending `decomp`: none;
- active `unreal`: none;
- active `broken`: none;
- active `[rejected_closure]`: none.

The existing gateway-NAT requirement decision and availability target-platform evidence gate
remain unchanged.

## Conclusion

The executable alpha now follows the accepted `VPNPathAdapter` component boundary rather than
merely implementing equivalent raw observation inline.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG0007-R7.R3` -> `VPNG9001-R1.R1.R3`
- `VPNG0007-R7.R5` -> `VPNG9001-R1.R1.R5`

The original IDs in the historical body are intentionally preserved.
