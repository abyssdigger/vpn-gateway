# NG3 managed Device runtime composition review — 2026-11-25

**Review unit:** A.012 Release-1 runtime composition over production D.001  
**Source reviewed:** `1fd69c02f3d8e3e520076dc0cdaf06343dca5fff`  
**Requirements:** `VPNG-U001-R1.R3.R7*`  
**Architecture:** A.001, A.002, A.008, A.012, D.001  
**Stable evidence:** `EV-00090`

## Scope

This review checks the previously explicit A.012 materialization gap: placement relative to
Private-network creation and fresh path observation, continuous current reconciliation,
dependency-safe product stop, preservation of external-Device compatibility, and publication
of the authoritative managed realization into A.008. D.002/D.003 peer ownership is outside
this review and remains the R8 frontier.

## Findings

### F1 — startup ordering is explicit and fail-safe

**Decision:** accepted  
**Resolution:** fixed

`start_controller_once` exposes a bounded Private-network preparation seam after the managed
network and ordinary-side portal are confirmed, but before fresh VPN-path interface observation.
Alpha uses only that seam for A.012. If preparation fails, controller-owned startup rollback is
performed and READY is not published.

### F2 — ordinary reconciliation observes A.012 before dependent path/policy state

**Decision:** accepted  
**Resolution:** fixed

Each normal alpha reconciliation freshly calls A.012 first. A D.001 problem or generation
mismatch therefore becomes a current problem before dependent C.004/payload reconciliation can
treat the old base realization as current.

### F3 — shutdown never bypasses A.012 ownership

**Decision:** accepted  
**Resolution:** fixed

Review found and corrected one implementation defect before acceptance: the first composition
attempt still called generic Private-network teardown after an unconfirmed managed cleanup.
The accepted source instead disables forwarding, confirms removal of product-owned structural
payload and return-affinity dependencies, then grants `dependency_free_device_ids` and requires
confirmed A.012 absence. If either stage is unconfirmed, `stop_controller_once` is not called.

### F4 — A.008 receives owner truth rather than reconstructing it

**Decision:** accepted  
**Resolution:** fixed

`RuntimeStatusAgent` now retains the latest `ManagedDeviceRealization`, including desired and
confirmed base generations, confirmed state, waiting state and problem state. It performs no
kernel observation and does not derive lifecycle confirmation from configuration.

### F5 — external Devices retain the previous path

**Decision:** accepted  
**Resolution:** fixed

A.012 receives only explicit `managed_vpn` entries. The existing base configuration remains
available through the compatible normalized contract, and external Devices continue to be
observed/bound through the pre-existing path without D.001 mutation.

### F6 — R8 is not accidentally claimed

**Decision:** accepted  
**Resolution:** fixed

This block materializes only the managed base lifecycle of R7. WireGuard peer selection,
peer-generation availability context and mutable shared-prefix `AllowedIPs` remain D.002/D.003
work under R8.

## Verification

GitHub Actions run `45519755877` on the reviewed source:

- `unit` job `138888449127` — PASS;
- installed `linux-alpha-smoke` job `138888449063` — PASS;
- dedicated `linux-managed-device-runtime` job `138888449316` — PASS.

The dedicated kernel job emitted:

- `A012_RUNTIME_START_BEFORE_PATH_OBSERVATION=PASS`;
- `A012_RUNTIME_STATUS_PROJECTION=PASS`;
- `A012_RUNTIME_DEPENDENCY_RELEASE_AND_STOP=PASS`;
- `A012_RUNTIME_PRIVATE_NETWORK_TEARDOWN=PASS`;
- `A012_RUNTIME_RESULT=PASS`.

## Verdict

**PASS.** The A.012 component-local contribution to `VPNG-U001-R1.R3.R7*` is fully
materialized in the current Release-1 runtime. The next managed-WireGuard frontier is R8
D.002/D.003; it is not required to keep A.012 marked partial.
