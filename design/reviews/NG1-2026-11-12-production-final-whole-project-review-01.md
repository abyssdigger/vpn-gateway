# NG1 production final whole-project review — pass 1

Date: 2026-11-12

Role: internal final expert review under CONTINUOUS-DEVELOPMENT.md.

## Scope

Reviewed the complete current production scope:

- schema/domain validation;
- Device/Traffic state and durable history;
- routing/RPDB projection and transition classification;
- nft filter/NAT generation, ownership and generation verification;
- Planner/runtime/event loop;
- namespace lifecycle and publication supervisor;
- status/CLI/systemd/deployment;
- privileged disposable production-cycle evidence;
- current deferred/future experiment boundaries.

## Finding F1 — read-only status did not verify exclusive nft ownership

Severity: medium/high operational correctness.

Planner treats any foreign nft table in the dedicated ROU namespace as structural drift and
repairs it behind the global barrier. Runtime status verified only the two owned nft tables,
so `rou show` could report `policy_verified=true` for a state the production Planner
considered structurally invalid.

### Disposition

Accepted and fixed.

`inspect_runtime_status()` now uses the same nft ruleset ownership verifier as Planner and
reports foreign nft tables as policy errors. A rootless regression test covers the case.

## Finding F2 — successful rou up meant systemd active, not verified appliance

Severity: high lifecycle contract.

Architecture §3.1 states that successful `rou up` means the appliance exists and its
internal safety invariants are verified. The CLI previously returned success after only
`systemctl is-active`.

This was especially wrong for an already-active service: no policy verification occurred.

### Disposition

Accepted and fixed.

`rou up` now waits for read-only status to prove all of:

- appliance_verified=true;
- durable state trustworthy;
- policy_verified=true;
- net.ipv4.ip_forward=1.

An already-active service is verified non-disruptively. A newly started service that never
reaches verified/open state is treated as failed up.

## Finding F3 — failed-up rollback could delete namespace without proving service stopped

Severity: high lifecycle/supervision safety.

The previous rollback path called `systemctl disable --now` with check disabled and then
immediately destroyed the instance. If the stop failed, the namespace could be deleted
under a still-running supervisor.

`rou down` already had the correct principle: destruction only after proven inactive.

### Disposition

Accepted and fixed.

A shared stop-proof helper now:

1. requests disable/stop;
2. checks systemd activity;
3. permits teardown only for known inactive/not-found states;
4. on active/indeterminate state, invokes containment and refuses namespace deletion.

If failed-up rollback cannot prove the service inactive, the original appliance is retained
and the combined rollback failure is surfaced. Regression coverage verifies
`destroy_instance` is not called.

## Finding F4 — EXP-018 still mentioned iptables as production operation

Severity: low documentation drift.

### Disposition

Accepted and fixed. EXP-018 now names nft operations.

## Evidence from preceding review units

The baseline already has:

- rootless NG1 and RC3 validation PASS;
- EXP-017 PASS;
- production nft round-trip PASS;
- full privileged production cycle PASS:
  initial reconcile -> same-name/new-ifindex -> metric promotion -> ordinary member
  disappearance -> structural foreign-nft barrier repair -> durable state verification.

## Rust-alignment assessment

The fixes reduce rather than add control-plane duplication:

- status and Planner share the same ownership semantics;
- lifecycle stop proof is centralized;
- `rou up` success is expressed as a typed/read-only status condition rather than hidden
  systemd timing;
- no new backend abstraction or legacy compatibility path was introduced.

## Verdict

All findings from this pass are accepted and fixed in source.

This pass is not yet the final clean verdict because the baseline changed. Required next
steps:

1. run rootless and privileged CI on the corrected baseline;
2. perform one repeat final whole-project review on that changed baseline;
3. if that review has no unresolved finding of minor severity or higher, close the current
   production implementation scope.
