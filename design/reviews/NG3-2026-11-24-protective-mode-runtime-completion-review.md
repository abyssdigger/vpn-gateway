# NG3 2026-11-24 — Protective mode runtime completion review

**Scope:** completion of A.011 / `VPNG-U004-R5*` required by the approved
`release/0.1.0/RELEASE-SCOPE.md`.

**Reviewed implementation head:** `73db9b4ba1104c399dbaa00bf29610e848134073`  
**Reviewed architecture/trace head:** `2195a0c529ce4eb8820b86a3d33590cad343d22f`

## Verdict

**PASS — A.011 ProtectiveModeManager is fully materialized for the approved 0.1.0 scope.**

The three former release blockers `VPNG-U004-R5`, `VPNG-U004-R5.R1`, and
`VPNG-U004-R5.R4` are no longer partial. The current architecture has no remaining
`partial` or `none` component requirement edges.

This review closes the implementation blocker only. It is not a new 0.1.0 release-preparation
attempt and does not revive the failed first attempt.

## Findings and dispositions

### F1 — explicit operator/automation control

**Decision:** accepted.  
**Resolution:** complete.

A.011 exposes source-scoped `status`, `enter`, and `leave` through the installed
root-local `vpn-gate-control` surface backed by
`/run/vpn-gate-alpha/control.sock`.

The socket/CLI is replaceable deployment machinery. Product semantics remain in
`ProtectiveModeManager`.

Independent request sources are preserved: one source cannot clear another source's request.

### F2 — confirmed entry and complete IP containment

**Decision:** accepted.  
**Resolution:** complete.

Entry reports success only after C.010 freshly confirms the separately owned protective gate.

Linux end-to-end evidence proves, while active:

- ordinary-side -> managed-domain IPv4 is blocked;
- managed-domain -> ordinary-side IPv4 is blocked;
- forwarding between VPN paths is blocked;
- managed namespace/interfaces and diagnostic/runtime context remain present.

The containment state is the separately identifiable
`inet vpn_gate_protective` owner-scoped table, rather than namespace/interface teardown.

### F3 — finite-cadence continuous confirmation

**Decision:** accepted.  
**Resolution:** complete.

A.011 has an independent audit worker. It fresh-observes C.010 with finite cadence and repairs
exact owned drift while protection is requested active.

Control-client handling and periodic safety audit run in separate workers, so an incomplete or
stalled authorized control request cannot suspend the audit cadence. Unit evidence explicitly
covers this boundary.

Linux evidence deletes the protective table out of band and observes its automatic
re-materialization before traffic is allowed again.

### F4 — safe leave and failed-leave retention

**Decision:** accepted.  
**Resolution:** complete.

Final leave is serialized against ordinary runtime reconciliation. With an empty source set,
A.011 freshly re-establishes/confirms applicable normal desired/runtime state before C.010 is
removed.

If normal state is unconfirmed, leave returns an explicit `leave_blocked` result and the
protective gate remains/re-becomes confirmed active.

Installed-bundle QA proves both:

- normal safe leave restores payload;
- an intentionally conflicting ordinary `vpn_gate` state causes leave to fail while payload
  remains blocked, followed by automatic safe release only after normal-state recovery.

### F5 — runtime lifecycle and installation

**Decision:** accepted.  
**Resolution:** complete.

The Release-1 runtime starts A.011 only after normal startup state is confirmed and fails startup
if the initial inactive protective state cannot be confirmed.

The service is stopped before managed-domain teardown. The alpha and release installers expose
the same supported `vpn-gate-control` operator path.

The actual generated 0.1.0 tarball is installed in Debian 13/systemd QA before the control
surface is exercised.

### F6 — release-scope isolation from aggressive helper

**Decision:** accepted.

The approved 0.1.0 scope exercises `VPNG-U001-R5.R2.C1`; the aggressive host-routing helper
remains outside the Release-1 runtime scope.

A.011 public control and periodic ownership do not depend on E.003. No automatic aggressive
trigger was added to the 0.1.0 commitment.

### F7 — component-model and traceability fit

**Decision:** accepted.

`protective_mode_manager.py` owns source-scoped Manager state and C.010 composition.
`protective_mode_control.py` is A.011's replaceable control/audit machinery.
`alpha_runtime.py` performs lifecycle composition and serialization with normal reconciliation.

The production trace manifest records all three roles without introducing a new semantic
component solely for the Unix transport.

## Evidence

Source-level/Linux evidence:

- `tests/integration_protective_mode_manager.py`;
- `tests/integration_protective_mode_runtime.py`;
- unit suite including stalled-control-client versus audit independence.

Observed Linux markers include:

- `A011_MULTI_SOURCE_ACTIVE=PASS`;
- `A011_SOURCE_ISOLATION=PASS`;
- `A011_ALL_IP_DIRECTIONS_BLOCKED=PASS`;
- `A011_RUNTIME_STATE_PRESERVED=PASS`;
- `A011_PERIODIC_REPAIR=PASS`;
- `A011_FAILED_LEAVE_RETAINS_BLOCK=PASS`;
- `A011_SAFE_LEAVE_RESTORES_TRAFFIC=PASS`;
- `A011_RUNTIME_INTEGRATION=PASS`.

Installed release-bundle QA on implementation head `73db9b4b...` reports:

- `RELEASE_QA_BUNDLE_INSTALL=PASS`;
- `RELEASE_QA_WIREGUARD_PAYLOAD=PASS`;
- `RELEASE_QA_PROTECTIVE_ENTER_BLOCK=PASS`;
- `RELEASE_QA_PROTECTIVE_PERIODIC_REPAIR=PASS`;
- `RELEASE_QA_PROTECTIVE_SAFE_LEAVE=PASS`;
- `RELEASE_QA_PROTECTIVE_FAILED_LEAVE_RETAINS_BLOCK=PASS`;
- `RELEASE_QA_PROTECTIVE_RECOVERY_RELEASE=PASS`;
- unchanged WireGuard/OpenConnect/L2TP lifecycle/payload PASS;
- `RELEASE_QA_RESULT=PASS`.

## Release-cycle consequence

The implementation blocker created by the approved 0.1.0 release scope is closed.

A future second 0.1.0 release-preparation attempt must still rebuild its project snapshot,
REQCOV, QA report and fulfillment review under the corrected release-cycle method. The failed
first attempt remains historical and must not be relabeled as successful.
