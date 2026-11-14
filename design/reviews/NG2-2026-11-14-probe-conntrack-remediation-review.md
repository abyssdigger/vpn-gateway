# NG2 — LOCAL_PROCESS conntrack generation remediation review

**Date:** 2026-11-14
**Status:** preliminary pending EXP-026 Debian 13 target confirmation
**Evidence:** EXP-025 target-confirmed STALE-INHERITANCE; EXP-026 privileged-CI PASS

## Problem

EXP-025 proved that conntrack-carried probe identity is not interface-generation-scoped.

A marked ICMP entry survived replacement of `vpn0` with a different ifindex. Deliberate
reuse of the same ICMP tuple/identifier in the new interface generation hit the old
ESTABLISHED marked entry.

Therefore exact RPDB/nft generation verification is insufficient by itself.

## Candidate mechanisms

### A. Rotate conntrack mark per physical generation

The new nft generation would accept only a new mark, making old entries unusable.

Rejected as the first remediation candidate because it creates new technical allocation and
lifetime problems:

- generation-mark allocation;
- wrap/reuse semantics;
- restart persistence questions;
- more physical state to observe/verify;
- no immediate value if the old entries can simply be removed.

### B. Conntrack zones per probe generation

Potentially strong isolation, but substantially more Linux mechanism and policy:

- zone assignment before conntrack lookup;
- generation-zone allocation;
- observation and cleanup;
- interaction with all local probe flows.

No evidence currently requires this complexity.

### C. Delete exact ICMP tuple / identifier

Technically narrow, but the NetworkRules lower domain does not own the ping ICMP identifier.

Pulling executor-generated identifiers into NetworkRules/Adapter would invert the current
semantic boundary and couple network policy to one probe implementation.

Rejected for the current architecture.

### D. Delete the dedicated probe conntrack class by mark

```text
conntrack -D -p icmp -m <dedicated probe mark>
```

EXP-026 CI proves:

- all entries with the probe mark are removed;
- an entry with another mark is preserved;
- after interface generation replacement, the cleaned fixed tuple uses NEW+mark-set;
- preserved different-mark state remains usable.

This requires no semantic probe identifiers and no generation allocator.

## Recommended physical generation boundary

If EXP-026 passes on Debian 13, treat all conntrack entries carrying the configured
LOCAL_PROCESS ct mark as ephemeral state owned by the current physical
NetworkRulesAdapter generation.

On every structural materialization while LinuxLocalProcessConfig exists:

1. close forwarding as today;
2. materialize routing/RPDB and nft desired state;
3. once the new nft policy is installed, delete ICMP conntrack entries carrying the
   dedicated LOCAL_PROCESS mark;
4. perform the existing fresh closed-state exact verification;
5. reopen forwarding only if required;
6. perform final verification;
7. only then publish the new physical generation as committed/READY.

The cleanup belongs inside the physical structural transition, not in
AvailabilityProbeManager and not in the ICMP probe process driver.

## Why cleanup after new nft policy

IPv4 forwarding closure does not block local OUTPUT/INPUT probes.

Deleting conntrack before policy replacement would leave a race in which the old local
policy could create another old-generation marked entry before the new filter is installed.

Deleting after the new nft policy is installed means:

- stale old-generation entries are removed;
- an entry created after cleanup necessarily belongs to packets admitted by the new
  physical policy;
- a probe that races before cleanup is simply invalidated as part of the structural
  generation transition.

The cleanup still occurs before exact verification and commit.

## Scope of invalidation

Mark-only cleanup invalidates all in-flight LOCAL_PROCESS probe flows sharing the Adapter's
dedicated ct mark, even if only one physical probe interface changed.

This is broader than one probe path, but still narrow relative to namespace conntrack:

- payload flows are not marked with the probe mark;
- unrelated control state with another/no mark is preserved;
- probe attempts are single-shot ephemeral observations;
- rules/evidence are already generation-scoped and must be reacquired after structural
  transition.

This breadth is likely acceptable and avoids per-plane mark/tuple allocation, but remains
an explicit architecture decision rather than an automatic consequence of EXP-026.

## Alignment with current ProbeRulesState scope

The current ProbeRulesStateCalculator is deliberately owner-wide: any authoritative
divergence invalidates availability evidence for the Manager's current rules generation as
a whole.

Therefore probe-class-wide conntrack cleanup is not broader than the current semantic
evidence boundary:

- a structural generation transition already makes current probe evidence non-authoritative;
- in-flight probe attempts from that old generation may be discarded;
- all probe-class conntrack entries are ephemeral measurement state, not payload service
  state;
- per-plane conntrack preservation would add allocation and transition complexity without
  preserving any evidence that the current Manager is allowed to trust.

If future AvailabilityProbeManager semantics become per-plane, cleanup granularity can be
revisited together with that state-model change. It should not be introduced preemptively.

## Transition concurrency boundary

The initial remediation assumes the current synchronous control model:

- one structural NetworkRules transition is executed to completion before another managed
  operation runs in that control path;
- LinuxIcmpProbeDriver is a single-shot blocking operation;
- AvailabilityProbeManager does not start a new probe while its rules transition is in
  progress / not READY.

Under that model no probe packet can race between stale-state cleanup and physical commit.

Do not add a temporary nft transition barrier solely for hypothetical parallel probe
execution. Parallelism/cancellation is already an intentionally open AvailabilityProbeManager
policy.

If future runtime permits concurrent probe execution with NetworkRules mutation, that
change must add an explicit cancellation/barrier contract before enabling concurrency.

Cleanup failure remains a structural transition failure; rules state is not published READY.

## Ownership requirement

For mark-filtered cleanup to be safe, LinuxLocalProcessConfig.ct_mark must be exclusive to
the managed LOCAL_PROCESS probe class within the ROU namespace.

External/foreign components in that namespace must not use the configured mark for their
own conntrack state.

This is a lower-domain ownership requirement, not NetworkRulesSpec semantics.

## Component-model note

The cleanup operation is driver-level external interaction.

The component responsible for the full structural convergence may execute it directly or
through a reusable conntrack Driver primitive; no one-line Driver wrapper is required.

The agreed distinction is:

- Driver performs direct command/state interaction without owning convergence;
- Executor owns transition to a desired postcondition and may use Drivers or perform
  driver-level operations directly when separate Driver abstraction adds no value;
- Manager chooses desired state/lifecycle.

Under that terminology the current class named `LinuxNetworkDriver`, which performs a
full materialize+verify convergence transaction, should be reviewed for possible
reclassification as an Executor. This naming cleanup is orthogonal to EXP-026 and must not
change the conntrack mechanism evidence.

## Cleanup idempotence

Production cleanup must be idempotent.

A structural generation may have no matching probe conntrack entries at all. The
conntrack-tools CLI may report `0 flow entries have been deleted` with a non-zero status
for that no-match case.

The production implementation must distinguish that benign no-op from command/selector/
kernel failure. Re-running the same cleanup on an already-clean probe class must succeed.

This is an implementation/error-classification invariant; EXP-026 does not need to create
an artificial missing-entry failure because its purpose is to prove selective deletion and
state isolation.

## Gate

Do not implement remediation until EXP-026 is confirmed on Debian 13.

After target PASS, decide explicitly whether probe-class-wide invalidation on structural
materialization is accepted. If accepted, implementation should preserve exact verification
and add regression proving stale inheritance is impossible across the production
Adapter transition.
