# NG2 — AvailabilityProbeManager executable boundary review

**Date:** 2026-11-14  
**Type:** autonomous architecture boundary review  
**Scope:** next consumer above ProbeRulesCalculator / ProbeRulesStateCalculator

## Result

**PASS for the boundary; do not implement scheduler/timing policy yet.**

The lower network-rules machinery is now executable. The next Manager must preserve a
strict dependency from network-plane readiness to active probe evidence.

## Existing inputs and outputs

The upper event model already defines:

```text
AvailabilityProbeSetRequest
    full desired probe snapshot
    probe_id
    mechanism
    concrete InterfaceIdentity
    target

AvailabilityProbeStateInfo
    subject = probe_id
    current result
    reason/details
    observation generation
```

Timing, retry cadence and hysteresis are deliberately not defined by that first normalized
machinery contract.

## Required internal decomposition

The Manager needs at least three distinct responsibilities:

```text
AvailabilityProbeSetRequest
        |
        v
ProbeRulesCalculator
        |
        v
NetworkRulesAdapter (owner = Manager)
        |
        v
ProbeRulesStateCalculator
        |
        +---- usability != READY ---> probe evidence is UNKNOWN / unusable
        |
        v
probe execution machinery
        |
        v
result interpretation / future hysteresis
        |
        v
AvailabilityProbeStateInfo
```

The rules calculator and rules-state calculator remain pure Machinery.

The NetworkRulesAdapter remains the single physical policy reconciler shared with other
owners.

Probe execution is a separate process-runtime responsibility.

## Ordering invariant

A probe attempt may contribute availability evidence only while the Manager has a fresh
rules observation with:

```text
knowledge   = KNOWN
convergence = MATCHED
usability   = READY
```

This is stronger than checking whether the last Adapter apply call returned SUCCESS.

Reasons:

- failed first apply may leave no dedicated uid guard installed yet;
- generation drift can invalidate a previously successful plane;
- restrictive drift can manufacture a false UNREACHABLE result;
- alternate-path/widened drift can manufacture a false REACHABLE result.

When rules state becomes UNKNOWN or INVALID, previously collected probe evidence for that
rules generation is not current authoritative evidence.

## Generation coupling

Probe evidence must be correlated with the network-rules generation under which it was
obtained.

A same-name/new-ifindex interface replacement is a new concrete generation even if the
string interface name is unchanged.

The Manager must not carry a success/failure result from an old concrete generation into a
new one.

The exact representation of the Manager's observation-generation token remains an
AvailabilityProbeManager concern; it must not be encoded into NetworkRulesSpec or Linux
uid/mark values.

## Shared physical planes vs logical probe ids

ProbeRulesCalculator deduplicates network policy by:

```text
(mechanism, InterfaceIdentity, target)
```

Logical `probe_id` remains an upper-domain correlation identity.

The Manager must not infer that two logical probe ids have the same timing/hysteresis
policy merely because their current physical network plane is shared.

Execution deduplication, if later useful, is an optimization that must preserve per-probe
result semantics.

## Linux process-runtime boundary

The NetworkRules Adapter now accepts LinuxLocalProcessConfig containing:

```text
uid
ct_mark
```

Only the uid is also relevant to process execution. The conntrack mark remains purely
network-policy machinery.

The future Linux probe launcher/executor will additionally need process/runtime choices
such as:

- gid;
- ping socket prerequisite or equivalent ICMP socket mechanism;
- capability / NoNewPrivileges policy;
- executable or in-process socket implementation;
- process lifecycle and cancellation.

These must not be added to NetworkRulesSpec.

Runtime assembly must provide one authoritative technical identity source so the launcher
uid cannot drift from the Adapter uid. Do not maintain independent duplicated uid
configuration in two components.

## ping_group_range

EXP-024 used namespace-local `net.ipv4.ping_group_range` to prove capability-free ICMP
execution.

That sysctl is **not** part of NetworkRulesAdapter ownership.

If the production executor uses the same ping-socket mechanism, its launcher/runtime
assembly must own and freshly verify the required process prerequisite before execution.
If a different ICMP execution primitive is chosen, that primitive requires its own focused
review.

## Audit/reconcile behavior

The Manager requires a deterministic rules audit path analogous in shape, but not semantics,
to PayloadTrafficManager:

1. renew NetworkRules state;
2. calculate ProbeRulesState;
3. if not MATCHED/READY, attempt current desired rules reconcile;
4. obtain fresh observation again;
5. only READY rules permit current probe evidence.

This does not define scheduling cadence. The runtime may call audit according to a later
scheduler policy.

## What is intentionally not implemented by this review

No speculative code is added for:

- probe interval;
- timeout;
- retry count;
- success/failure threshold;
- hysteresis;
- jitter;
- parallelism limits;
- cancellation semantics;
- external `ping` vs in-process ICMP socket choice.

Those are real execution/product contracts and should be fixed together with the first
executable probe worker rather than guessed from the NetworkRules layer.

## Next implementation unit

The next concrete unit should define and exercise **one single-shot ICMP probe executor**
on Debian 13, including the authoritative technical uid coordination with runtime
assembly.

Only after that mechanism is explicit should AvailabilityProbeManager scheduling and
hysteresis be implemented around it.

## Final verdict

The rules side of AvailabilityProbeManager is no longer blocked.

The process-execution side is the next real boundary. No second network reconciler and no
Linux process details are allowed into the semantic AvailabilityProbeSetRequest.
