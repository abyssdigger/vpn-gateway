# NG2 — LOCAL_PROCESS / ProbeRules / executor whole-slice audit

**Date:** 2026-11-14  
**Type:** autonomous whole-code / architecture audit  
**Scope:** LOCAL_PROCESS Linux backend, ProbeRulesState, common-state comparison and
single-shot ICMP executor

## Result

**PASS for implemented/tested behavior, with two evidence gates remaining: Debian 13
production executable confirmation and conntrack-mark generation-lifetime verification.**

No unresolved code/architecture defect currently justifies additional lower-domain
implementation before that target run.

## Audit criteria

Checked:

- unused concepts/modules/tests;
- accidental NG1/RC code continuation rather than reference use;
- unnecessary generic abstraction;
- contradictions with EXP-021/022/023/024;
- owner-composition and generation fail-close behavior;
- exact observe/verify claims;
- process/network identity leakage across semantic boundaries;
- premature common state abstraction;
- process-executor vs scheduler/product-policy separation;
- documentation drift.

## A1 — NG1/RC remain evidence, not implementation source

**PASS.**

All implementation changes are under NG2.

Recovered evidence includes:

- isolated bound probe RPDB behavior;
- same-name/new-ifindex generation semantics;
- selective process isolation;
- capability-free ICMP execution.

No NG1 planner/device-engine/network-state implementation was ported into NG2.

## A2 — LOCAL_PROCESS remained semantic and Linux-independent

**PASS.**

NetworkRulesSpec carries:

- LOCAL_PROCESS endpoint class;
- semantic target/protocol;
- concrete bound InterfaceIdentity.

It does not carry:

- uid/gid;
- conntrack mark;
- ping executable;
- ping_group_range;
- capability policy.

Linux-only identity is explicit LinuxLocalProcessConfig.

## A3 — experiment values initially leaked into production defaults

**Found and fixed.**

The first physical implementation temporarily treated EXP-024 uid 65534 and mark 0x24 as
implicit production constants.

They are now explicit lower-domain configuration. Harnesses may use those values; semantic
rules do not.

## A4 — root uid would widen the dedicated guard

**Found and fixed.**

A uid 0 guard would capture unrelated root traffic and violate EXP-024's coexistence
property.

LinuxLocalProcessConfig now requires a non-root uid. The internal Linux RPDB dispatch
spec/compiler enforces the same invariant even when called directly, so the lower-domain
contract cannot be bypassed outside the normal Adapter path.

## A5 — actual iproute2 rule observation differed from assumed JSON

**Found and fixed from live CI evidence.**

The initial parser expected a synthetic uidrange field.

Real JSON exposes:

```text
uid_start
uid_end
ipproto
oif
```

Exact verification now uses those fields and separately verifies current bound-output
ifindex generation.

## A6 — nft readback canonicalization differed from generated text

**Found and fixed from live CI evidence.**

Equivalent kernel/nft rendering differences covered explicitly:

- numeric interface references may render by name;
- conntrack mark may render zero-padded;
- redundant positive `ip protocol icmp` may disappear around ICMP type;
- host `/32` may render without the suffix.

Normalization is limited to those proven equivalences. Exact canonical policy plus owned
marker multiset remain required.

## A7 — projected generation loss could reopen ordinary routing for probe uid

**Critical finding; fixed and kernel-regressed.**

Post-projection rules can legitimately lose all concrete LOCAL_PROCESS dispatch/allow
objects when the bound generation disappears.

If uid-guard presence were inferred only from that realizable projection, another owner's
structural reconcile could remove the final uid OUTPUT drop and let the probe process use
main routing.

Guard lifetime now derives from pre-projection registered LOCAL_PROCESS owner intent.

LP7 proves:

1. committed probe generation disappears;
2. another owner triggers structural reconcile;
3. projected probe permissions disappear;
4. dedicated uid guard remains;
5. unbound probe still cannot escape through live alternate routing.

## A8 — generic LOCAL_PROCESS support would exceed evidence

**Rejected.**

The physical backend is deliberately limited to the target-proven shape:

- ICMP only;
- exact /32 target;
- echo-request outbound;
- echo-reply inbound;
- concrete bound interface;
- matching owner-scoped isolated dispatch plane.

TCP/UDP, broad predicates and unrelated LOCAL_PROCESS endpoint shapes fail closed.

The extra validation code is therefore justified evidence enforcement, not speculative
feature generalization.

## A9 — ProbeRulesState must not copy payload state semantics

**Reviewed and fixed by independent model.**

ProbeRulesState uses:

```text
knowledge
convergence
usability
```

Any authoritative divergence makes probe evidence INVALID.

PayloadRulesState retains independent safety/service semantics because restrictive payload
divergence can still be SAFE and may represent DEGRADED/ISOLATED service.

Mandatory comparison therefore rejected a common RulesState.

Only generic NetworkRules semantic equality was extracted as genuinely common machinery.

## A10 — probe rules state is intentionally owner-wide initially

**Retained.**

The current calculator invalidates the full Manager rules generation on any divergence.

This is conservative: it may temporarily suppress valid evidence from another unaffected
probe plane, but it cannot manufacture a false availability result.

Per-plane rules state is deferred until the executable AvailabilityProbeManager
demonstrates a real requirement. Synthetic routing-domain-name reverse parsing was not
introduced speculatively.

## A11 — process prerequisite belongs outside NetworkRulesAdapter

**PASS.**

ping_group_range, gid, executable and process privilege setup are owned by probe execution,
not network-policy materialization.

LinuxIcmpProbeExecutor sets and freshly verifies its ping_group_range prerequisite before
each attempt.

The Adapter and executor share the same LinuxLocalProcessConfig object so uid need not be
duplicated.

## A12 — sysctl textual readback was too strict

**Found and fixed from privileged CI.**

Linux rendered ping_group_range with a tab. The executor now compares two whitespace-
normalized fields rather than a literal string.

## A13 — executor separates local machinery failure from no reply

**PASS.**

Single-attempt outcomes are:

- REPLY;
- NO_REPLY;
- ERROR.

Generation mismatch, prerequisite failure and process execution failure are ERROR, not
remote NO_REPLY.

The executor chooses no cadence/retry/hysteresis policy.

## A14 — rules readiness must gate execution evidence

**Architecture invariant fixed.**

AvailabilityProbeManager may treat a probe result as current evidence only under fresh:

```text
KNOWN + MATCHED + READY
```

Adapter action SUCCESS alone is insufficient.

A result from an old rules/interface generation is stale and cannot be carried forward.

## A15 — documentation contained closed gates as current state

**Found and fixed.**

Updated:

- network-rules-adapter.md;
- payload-traffic-manager.md;
- runtime-event-model.md;
- code README;
- ProbeRules boundary/calculator/audit reviews;
- LOCAL_PROCESS backend review.

A normative availability-probe-manager.md now records the current executable boundary
without inventing scheduler policy.

## A16 — owner projection and uid-guard decision used separate snapshots

**Found and fixed as maintainability/safety cleanup.**

renew/rejected-candidate reconcile now derive both projection and guard lifetime from one
owner snapshot.

## Unused / unjustified artifacts review

Retained and justified:

- LinuxLocalProcessConfig — consumed by Adapter and executor;
- ProbeRulesStateCalculator — required to gate measurement evidence;
- LinuxIcmpProbeExecutor — first real process-runtime consumer;
- common network_rules_semantically_equal — used by both independent state calculators.

Not introduced:

- second physical network reconciler;
- common RulesState;
- per-probe uid/mark allocator;
- generic local-process policy lattice;
- speculative scheduler;
- timing/hysteresis configuration;
- reverse parser for synthetic probe routing-domain names.

## Green implementation baseline

Earlier full-slice baseline:

```text
70ebd870b22b41782c0c6bef55ce18adfc0f25ef
```

Latest code/test baseline after executor fail-close and RPDB uid-invariant audit fixes:

```text
9a95384b7b43121b2914e1df7b903c6da5e20518
```

GitHub gates on the latest code baseline:

- NG2 rootless unit/compile: PASS;
- NG2 privileged Linux integration: PASS;
- production LOCAL_PROCESS integration including LP1..LP7: PASS;
- existing NG2 payload dataplane integration: PASS;
- NG1 Python validation/regression: PASS.

## A17 — conntrack mark lifetime across probe generation changes is not yet proven

**New mechanism ambiguity; unresolved at this checkpoint.**

The selected reverse-path mechanism carries process identity in conntrack state. nft/RPDB
generation verification is exact, but conntrack entries can outlive one single-shot ping
process and interface/rules replacement does not obviously prove destruction of that flow
state.

A stale marked ICMP entry could matter if a later probe reuses the same conntrack tuple
(including ICMP identifier) after a rules/interface generation transition. Interface
identity is not part of the ordinary conntrack tuple.

The current Manager design correctly invalidates *userspace probe evidence* across rules
and interface generations, but that does not by itself prove that stale kernel conntrack
identity cannot be inherited by a later packet.

Do not guess a fix such as global conntrack flushing. The next kernel-mechanism experiment
must determine:

1. whether the marked ICMP conntrack entry survives the relevant interface/rules
   generation transition;
2. whether a later ping can deliberately reuse the tuple/identifier;
3. whether a delayed or synthetic reply can then satisfy the new INPUT rule through the
   stale mark;
4. if yes, what narrow owner-scoped generation mechanism is viable without flushing
   unrelated conntrack state.

Until this is resolved, the LOCAL_PROCESS backend remains functionally green for all
current tests but its generation-isolation proof is incomplete.

## Remaining evidence/product gates

### External evidence gate

Confirm LinuxIcmpProbeExecutor on Debian 13 using the intended production executable:

```bash
sudo env VPNG_NG2_PROBE_PING_PATH=/usr/bin/ping \
  python3 design/NG2/code/python/rou/tests/integration_linux_local_process.py
```

Required: LP1..LP7 and `NG2_LINUX_LOCAL_PROCESS_INTEGRATION=PASS`.

### Deliberately unresolved product/runtime policy

Still not chosen:

- probe interval;
- timeout policy supplied to attempts;
- retry count;
- success/failure threshold;
- hysteresis;
- jitter;
- parallelism/cancellation;
- exact Manager observation-generation representation;
- shutdown cleanup policy for process prerequisites.

These belong to the first executable AvailabilityProbeManager scheduling contract, not the
lower network/executor layer.

## Current verdict

Lower network-rules + single-shot execution architecture is coherent.

Do not start scheduler/hysteresis implementation until the target executor gate is closed
and the execution policy contract is explicitly chosen.
