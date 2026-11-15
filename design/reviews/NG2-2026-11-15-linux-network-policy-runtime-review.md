# NG2 review — shared-Adapter Linux network policy runtime

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-runtime-assembly-40m`  
**Scope:** outer ownership of PayloadTrafficManager plus availability runtime on one Adapter

## Verdict

**PASS.**

## Implemented

`runtime_assembly.py` now provides:

```text
build_linux_network_policy_runtime(...)
    -> LinuxNetworkPolicyRuntime
```

The object graph is:

```text
                    one NetworkRulesAdapter
                      /               \
                     /                 \
        PayloadTrafficManager   AvailabilityProbeManager
                                      |
                               ProbeExecutionAgent
                                      |
                         good-news/tick -> PayloadTrafficManager
```

The two Managers remain distinct Adapter owners because both pass `owner=self`.

## F1 — one physical Adapter must not collapse logical ownership

**Classification:** satisfied and tested.

The outer builder passes the same Adapter instance to both Managers but does not create a
shared owner token.

Regression verifies two distinct Manager objects appear as distinct Adapter owners.

This matches the existing owner-composition contract of NetworkRulesAdapter.

## F2 — audit must stay owner-local

**Classification:** satisfied and tested.

`LinuxNetworkPolicyRuntime.audit()` performs:

```text
AvailabilityProbeManager.audit()
PayloadTrafficManager.audit()
```

Each Manager refreshes/repairs only its own Adapter scope.

No global merged desired state is constructed above the Adapter.

## F3 — stop must clean both owners independently

**Classification:** accepted and covered.

Shutdown order:

1. availability runtime stops/quiesces probe demand and cleans probe owner;
2. payload owner cleanup runs in `finally`;
3. `NetworkPolicyRuntimeStopResult` preserves the two ActionResults separately.

Regression covers:

- both cleanups succeed;
- probe cleanup returns FAILURE while payload cleanup still runs and succeeds;
- unexpected probe cleanup exception still attempts payload cleanup.

The outer runtime therefore does not turn one owner's failure into skipped cleanup for the
other owner.

## F4 — aggregate stop result must not erase diagnostics

**Classification:** satisfied.

`NetworkPolicyRuntimeStopResult.success` is only a convenience conjunction.

The original `probe_cleanup` and `payload_cleanup` ActionResults remain available with
their own diagnostics.

## F5 — no new global runtime state

**Classification:** satisfied.

`LinuxNetworkPolicyRuntime` contains only component ownership and synchronous delegation:

- structural payload request forwarding;
- availability config forwarding;
- start;
- audit;
- stop.

It does not cache payload/probe state, compute Profile verdicts or duplicate Manager
desired state.

## Evidence

Final code head for this review unit:

`7aac5bc568190c8e9c33a788e923280c7020b0d8`

GitHub Actions `NG2 Python` run **650**:

- compile: PASS;
- **293 rootless unit tests PASS**;
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

Unresolved runtime work is now above/beside the network-policy object graph:

- startup composition from bootstrap result into this runtime;
- periodic audit/retry scheduling;
- probe diagnostic/status projection;
- structural config/binding -> PayloadTrafficStateRequest projection;
- outer ProfileState/status model.

No unresolved finding remains in this review unit.
