# NG2 review — full-instance network-policy runtime composition

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-runtime-assembly-40m`  
**Scope:** existing Linux instance -> protective bootstrap -> shared-Adapter runtime

## Verdict

**PASS.**

## Implemented

`bootstrap_linux_network_policy_runtime_for_instance(...)` composes:

```text
ensure_linux_instance(spec)
    -> protective close + exact infrastructure verification

bootstrap_linux_network_rules_adapter_for_instance(spec)
    -> independent protective close + fresh verification

build_linux_network_policy_runtime(adapter)
    -> PayloadTrafficManager + AvailabilityProbeManager + ProbeExecutionAgent
```

The runtime is exposed only after both instance verification and the independent Adapter
bootstrap gate succeed.

## F1 — instance helper must preserve the deliberate double-close

**Classification:** satisfied and tested.

The helper delegates to the existing instance bootstrap path rather than attempting to
optimize away the second forwarding close.

Rootless existing-instance simulation verifies two IPv4 forwarding-close writes:

1. one from `ensure_linux_instance()`;
2. one from the independent Adapter bootstrap immediately before runtime exposure.

The redundancy is intentional across lifecycle/bootstrap boundaries.

## F2 — no duplicate namespace lifecycle implementation

**Classification:** satisfied.

The new helper contains no netns/veth/address/route commands.

All infrastructure creation/verification remains in `linux_instance.py`.
All forwarding-close/readback semantics remain in `runtime_bootstrap.py`.

## F3 — no runtime exposure on infrastructure/bootstrap failure

**Classification:** satisfied by composition contract.

`bootstrap_linux_network_rules_adapter_for_instance()` already converts infrastructure
or protective-bootstrap failure into a failed result with no Adapter.

The outer helper maps that directly to a failed
`LinuxNetworkPolicyRuntimeBootstrapResult` with no runtime.

## Evidence

Final code head for this unit:

`56875fef269b355e7e98e2d0e592b90afc0df9c3`

GitHub Actions `NG2 Python` run **660**:

- compile: PASS;
- **297 rootless unit tests PASS**;
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

## Remaining work

- whole-assembly structure review/refactor if justified;
- diagnostics/status model;
- structural config/binding projection;
- periodic audit scheduling policy.

No unresolved finding remains in this unit.
