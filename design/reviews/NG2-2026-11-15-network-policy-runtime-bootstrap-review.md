# NG2 review — network-policy runtime protective bootstrap

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-runtime-assembly-40m`  
**Scope:** publish LinuxNetworkPolicyRuntime only after verified protective close

## Verdict

**PASS.**

## Implemented

`bootstrap_linux_network_policy_runtime(...)` composes the existing protective
`LinuxRuntimeBootstrapBackend` gate with the already-reviewed shared-Adapter runtime.

Flow:

```text
LinuxRuntimeBootstrapBackend
    |
    | close_forwarding_verified()
    v
bootstrap_linux_network_rules_adapter
    |
    | success(adapter)
    v
build_linux_network_policy_runtime
    |
    v
LinuxNetworkPolicyRuntime
```

On bootstrap failure no runtime is exposed.

## F1 — no bypass around protective bootstrap

**Classification:** satisfied.

The composition helper does not construct the runtime until
`bootstrap_linux_network_rules_adapter()` returns success with a verified Adapter.

A failed/unverified close returns:

```text
LinuxNetworkPolicyRuntimeBootstrapResult(
    success=False,
    runtime=None,
    diagnostic=...
)
```

## F2 — bootstrap result must not allow contradictory exposure

**Classification:** satisfied and tested.

The result type rejects:

- success without a runtime;
- failure with a runtime.

This mirrors the existing Adapter bootstrap result contract.

## F3 — bootstrap must not duplicate policy

**Classification:** satisfied.

The helper performs no payload/Profile interpretation and no probe configuration.

It only gates construction of the already-defined runtime object graph behind the lower
protective bootstrap.

## F4 — lower bootstrap remains authoritative

**Classification:** satisfied.

Forwarding-close semantics, readback verification and lower startup safety remain entirely
inside `runtime_bootstrap.py` / Linux Executor.

No second sysctl implementation or duplicated verification logic was introduced.

## Evidence

Final code head for this unit:

`c859d4d7ed46528c0200b481664bab73e3e7ae95`

GitHub Actions `NG2 Python` run **655**:

- compile: PASS;
- **296 rootless unit tests PASS**;
- selective probe-process isolation: PASS;
- EXP-025: PASS;
- EXP-026: PASS;
- EXP-027: PASS;
- nft ICMP selector: PASS;
- Linux instance lifecycle: PASS;
- Linux Adapter: PASS;
- Linux LOCAL_PROCESS: PASS;
- Linux dataplane: PASS.

No new external experiment is required.

## Remaining runtime work

- periodic audit/retry trigger;
- probe diagnostic/status projection;
- structural config/binding -> PayloadTrafficStateRequest projection;
- outer ProfileState/status model;
- optional full-instance convenience composition above existing instance bootstrap.

No unresolved finding remains in this unit.
