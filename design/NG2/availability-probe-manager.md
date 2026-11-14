# VPN-GATE NG2 — AvailabilityProbeManager

**Status:** active NG2 design  
**Date:** 2026-11-14  
**Scope:** active availability-probe managed domain

## 1. Responsibility

AvailabilityProbeManager owns the active probe subsystem.

It owns:

- the latest accepted `AvailabilityProbeSetRequest`;
- probe-specific NetworkRules ownership through the common NetworkRulesAdapter;
- interpretation of ProbeRulesState;
- probe-attempt lifecycle;
- current probe evidence for each logical `probe_id`;
- publication of AvailabilityProbeStateInfo.

It does not own:

- Profile binding decisions;
- payload routing/NAT/filtering;
- VPN process lifecycle;
- NetworkRules physical allocation;
- user-facing timing configuration parsing.

## 2. Network rules machinery

Pure machinery:

```text
AvailabilityProbeSetRequest
        |
        v
ProbeRulesCalculator
        |
        v
NetworkRulesSpec
```

The Manager uses itself as one opaque owner of the shared NetworkRulesAdapter.

Observed rules are interpreted through:

```text
ProbeRulesStateCalculator(
    desired NetworkRulesSpec,
    observed NetworkRulesState
)
    -> ProbeRulesState
```

ProbeRulesState is intentionally distinct from PayloadRulesState:

```text
knowledge
convergence
usability
```

Only `KNOWN + MATCHED + READY` permits active probe evidence to be authoritative.

## 3. Rules-before-execution invariant

A probe attempt may contribute current availability evidence only after fresh rules
observation proves the desired probe plane READY.

An Adapter action SUCCESS alone is insufficient.

If rules become UNKNOWN or DIVERGED/INVALID:

- current probe evidence for that rules generation is no longer authoritative;
- the Manager must not reinterpret an execution failure as remote UNREACHABLE;
- the Manager must reconcile/refresh rules before accepting new evidence.

This prevents both:

- false negative from a restrictive local plane;
- false positive from alternate-path escape or widened local policy.

## 4. Interface generation

Every request names a concrete `InterfaceIdentity(ifname, ifindex)`.

Same-name/new-ifindex is a new generation.

Probe execution independently rechecks the concrete generation immediately before the
attempt. NetworkRules observation and executor generation checking are complementary:
neither is replaced by the other.

Probe evidence must not survive a concrete-generation change.

## 5. Single-shot ICMP executor

The first executable worker is `LinuxIcmpProbeExecutor`.

It performs one bound attempt and returns:

```text
REPLY
NO_REPLY
ERROR
```

These are raw attempt outcomes.

`NO_REPLY` is not by itself the final availability state; cadence/retry/hysteresis policy
is applied above the executor.

Local failures such as generation mismatch, process prerequisite failure or ping execution
error return ERROR, not NO_REPLY.

## 6. Linux technical identity

Linux runtime assembly supplies one authoritative technical process identity.

Network policy receives:

```text
LinuxLocalProcessConfig
    uid
    ct_mark
```

Probe execution receives the same `LinuxLocalProcessConfig` plus process-only values such
as gid and executable path.

The semantic AvailabilityProbeSetRequest contains none of these Linux values.

The uid must not be independently duplicated in Adapter and executor configuration.

## 7. ping socket prerequisite

The first Linux executor uses capability-free ping sockets.

Before each single-shot attempt it idempotently writes and freshly verifies the
namespace-local `net.ipv4.ping_group_range` for its configured gid.

This prerequisite belongs to process execution, not NetworkRulesAdapter.

The current executor does not restore an unknown previous value after each attempt.
Shutdown ownership can be added when the complete Manager lifecycle is implemented.

## 8. Logical probes and physical planes

Logical identity:

```text
probe_id
```

Network plane identity used by ProbeRulesCalculator:

```text
(mechanism, InterfaceIdentity, target)
```

Several logical probes may therefore share one physical network plane.

This does not imply shared timing/hysteresis semantics. Execution deduplication is a future
optimization only if it preserves each logical probe contract.

## 9. Audit/reconcile skeleton

A deterministic rules audit pass is defined independently of scheduling cadence:

```text
renew NetworkRules
        |
        v
calculate ProbeRulesState
        |
        +-- READY ----------------------> rules usable
        |
        +-- UNKNOWN / INVALID
                |
                v
        apply current desired rules
                |
                v
        obtain fresh state again
```

Probe execution consumes only the READY branch.

The cadence that invokes rules audit is not fixed here.

## 10. Event publication

AvailabilityProbeStateInfo is current state per logical `probe_id`.

Until both conditions hold:

1. matching READY probe rules generation;
2. valid current probe evidence for that generation;

the published availability state is UNKNOWN rather than inferred failure.

A result collected under an older rules/interface generation is stale evidence.

## 11. Still intentionally open

Before scheduler/timing implementation, the remaining evidence gate is the stale conntrack-mark generation-lifetime experiment. Debian 13 confirmation with the intended `/usr/bin/ping` is complete.


The following require an explicit later contract:

- attempt interval;
- per-attempt timeout policy;
- retry count;
- success/failure thresholds;
- hysteresis;
- jitter;
- concurrency/serialization;
- cancellation on superseding request;
- exact observation-generation representation;
- shutdown cleanup of process runtime prerequisites;
- target-confirmed production ping executable.

These are not inferred from payload policy or from EXP-024.

## 12. Evidence

Current evidence:

- EXP-024: selective local-process routing/filter mechanism PASS on Debian 13;
- production LOCAL_PROCESS NetworkRules backend: apply/renew/dataplane PASS;
- generation-isolation proof still requires focused stale conntrack-mark lifetime verification across rules/interface generation replacement;
- projected generation loss retains dedicated uid guard across another owner's structural
  reconcile;
- ProbeRulesStateCalculator: unit PASS;
- LinuxIcmpProbeExecutor: unit + privileged CI integration PASS;
- LinuxIcmpProbeExecutor with `/usr/bin/ping`: Debian 13 target LP1..LP7 PASS.

The intended Debian 13 production executable remains a separate target-confirmation gate.
