# NG3 2026-11-24 — ManagedDeviceManager core review

**Review unit:** A.012 current orchestration core, without runtime wiring  
**Reviewed source:** `eef712648e60c112e9276a865599f3e80964a240`  
**Architecture:** A.012 ManagedDeviceManager  
**Requirements:** `VPNG-U001-R1.R3.R7*`

## Verdict

**PASS — A.012 CORE IS MATERIALIZED PARTIALLY; PRODUCT RUNTIME WIRING REMAINS OPEN.**

## Findings and dispositions

### F1 — structural demand is sufficient for the first lifecycle contract

**Decision:** accepted.

The Manager treats a managed Device as desired-present only when it is both explicitly present
in `CurrentConfig.managed_vpns` and active in the normalized structural configuration.
External Devices do not enter A.012 state at all.

### F2 — desired generation must include current secret content

**Decision:** accepted.

D.001 now exposes a non-mutating `desired_generation` operation. It validates current secret
files and derives the same opaque base-generation token used by `converge_present`.
A.012 computes this before mutation and accepts success only when D.001 returns the same
confirmed generation.

A secret-read/validation failure therefore becomes problem state rather than silently
preserving an old confirmed generation.

### F3 — desired absence is not permission to remove the base VPN

**Decision:** accepted.

A.012 calls `converge_absent` only for Devices explicitly listed in
`dependency_free_device_ids`. Otherwise it fresh-observes D.001. If the base VPN is still
present, the projection is `waiting_for_dependencies`, not success and not a deletion
attempt.

This preserves the architecture rule that product-owned dependent policy and dynamic
VPN-specific state must be removed before D.001 base teardown.

### F4 — removing managed_vpn from configuration cannot forget an owned instance

**Decision:** accepted.

The Manager retains previously managed Device IDs in current-only memory after they disappear
from the new managed configuration until D.001 confirms absence. Once absence is confirmed,
the old ID leaves A.012 state. No durable command journal is introduced.

### F5 — lifecycle failure is a truthful problem state

**Decision:** accepted.

D.001 exceptions or generation inconsistencies produce a projection with `problem` and no
false confirmed state. Reconciliation does not infer success from command submission or from
previous Manager state.

### F6 — runtime materialization is deliberately not claimed

**Decision:** accepted.

The current alpha loader still rejects `managed_vpn` before runtime lifecycle work. The
controller startup sequence creates the managed network domain after policy validation, so
proper A.012 wiring requires a new explicit phase after Private-network creation and before
fresh VPN-path observation. Stop/reload must likewise supply dependency-release confirmation.

Those changes are not hidden in this core unit. A.012 requirement edges are therefore
[`partial`], not [`full`].

## Evidence

GitHub Actions run `45479580505`, unit job `138748981952`: PASS.

Unit coverage proves:

- external Device produces no A.012 subject and no lifecycle call;
- structurally demanded managed Device reaches matching desired/confirmed generation;
- present but undemanded Device waits without deletion until dependencies are released;
- released dependency permits confirmed absence;
- removal of management remains tracked until owned absence;
- D.001 failure does not become confirmation;
- desired/confirmed generation mismatch becomes problem.

Stable evidence address: `EV-00080`.

## Result

The remaining A.012 work is no longer semantic design. It is runtime composition:
introduce the managed-Device reconciliation phase at the correct controller lifecycle point,
propagate dependency-release truth during reload/stop, and publish realization state to A.008.
