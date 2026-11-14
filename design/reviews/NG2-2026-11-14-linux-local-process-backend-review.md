# NG2 — Linux LOCAL_PROCESS backend review

**Date:** 2026-11-14  
**Type:** autonomous implementation / architecture review  
**Scope:** target-proven LOCAL_PROCESS materialization inside the common Linux NetworkRulesAdapter

## Result

**PASS.**

The backend now has real physical apply, exact renew and kernel dataplane evidence for the
ICMP ProbeRules plane. No second physical reconciler was introduced.

NG1 and RC* were used only as historical evidence/reference. No implementation was ported
or modified from those code lines; all executable changes are in NG2.

## Proven implementation boundary

The semantic contract remains Linux-independent:

- `LOCAL_PROCESS` carries no uid/gid/cgroup/mark;
- dispatch carries semantic destination, protocol and concrete bound output generation;
- ProbeRulesCalculator still emits exact ICMP echo-request / echo-reply semantics.

Linux lower-domain configuration supplies one dedicated process class:

```text
LinuxLocalProcessConfig
    uid       non-root dedicated uid
    ct_mark   non-zero conntrack mark
```

The configuration belongs to one Adapter/runtime instance. It is not a per-probe or
per-owner identity allocator.

Payload-only deployments require no LOCAL_PROCESS configuration.

## Routing

The physical selector is exact:

```text
uidrange UID-UID
+ ipproto icmp
+ target /32
+ bound output interface
    -> owner-scoped routing table
```

The table contains the exact path plus the existing terminal blackhole default.

Observation uses the actual iproute2 JSON fields `uid_start`, `uid_end`, `ipproto`
and `oif`.

Verification also compares the current ifindex for the bound output name. A
same-name/new-ifindex replacement therefore invalidates the old physical generation.

## Filtering

The existing forwarded payload chains remain unchanged.

LOCAL_PROCESS adds selective local hooks only when required:

- OUTPUT observes the configured uid;
- exact admitted NEW request sets the configured conntrack mark;
- admitted established OUTPUT requires that mark;
- reverse INPUT requires the mark plus exact input generation and exact reply predicate;
- the same candidate reply without the mark is dropped;
- all other OUTPUT from the dedicated uid is dropped;
- unrelated local processes retain ordinary namespace-local networking.

LOCAL_PROCESS-only policy does not enable `net.ipv4.ip_forward`.

nft verification remains exact after normalizing kernel/nft serialization differences:
numeric interface references rendered by name, zero-padded conntrack marks, redundant
`ip protocol icmp` around ICMP type matches, and host `/32` rendering.

## Conservative support boundary

The executable backend intentionally supports only the target-proven initial shape:

- ICMP;
- exact target `/32`;
- echo-request outbound;
- echo-reply inbound;
- LOCAL_PROCESS paired with one concrete INTERFACE;
- matching owner-scoped isolated dispatch plane.

A LOCAL_PROCESS traffic allow or flow-initiation rule without that isolated dispatch is
rejected. Broader predicates, TCP/UDP and other local-process traffic shapes fail closed.

A dispatch-only plane is allowed because it is strictly more restrictive: the process uid
guard remains closed without any accept rule.

## Findings closed during review

### R1 — experiment constants leaking into production

Initial implementation temporarily treated uid 65534 and mark 0x24 as implicit backend
constants.

**Fixed.** They are now explicit Linux-only runtime configuration. The values remain in
experiments/integration harnesses only.

### R2 — root uid would widen the guard domain

Using uid 0 would make the final OUTPUT guard capture all root traffic in the namespace and
violate the unrelated-process property proven by EXP-024.

**Fixed.** LinuxLocalProcessConfig requires a non-root uid.

### R3 — incomplete interface-generation projection

LOCAL_PROCESS itself has no interface identity, but its dispatch has a concrete
`bound_output`.

**Fixed.** Projection and Linux generation validation include bound_output. Stale
same-name/new-ifindex generations are projected away/fail exact renew.

### R4 — RPDB JSON assumption

The initial parser expected a synthetic `uidrange` field.

**Fixed from live kernel evidence.** iproute2 JSON exposes `uid_start` and `uid_end`.

### R5 — nft textual serialization mismatch

Live nft readback canonicalized ICMP protocol, /32 and conntrack mark syntax differently.

**Fixed.** Canonical verification now normalizes only proven equivalent renderings while
retaining exact rule-marker/generation verification.

### R6 — unnecessary compiler state mutation

A redundant local-process-presence assignment remained after the explicit pre-scan.

**Fixed.** Removed.

### R7 — projected generation loss could remove the uid guard during another owner reconcile

The first projection implementation correctly removed stale bound-output dispatch/allow
rules, but the nft compiler inferred whether the uid guard was needed only from the
post-projection realizable rules.

If the probe generation disappeared and another owner triggered a structural reconcile,
the projected probe rules could contain no LOCAL_PROCESS endpoint at all. That could remove
the final uid OUTPUT guard and let the dedicated probe uid fall through to ordinary main
routing.

**Fixed.** Guard lifetime is derived from registered LOCAL_PROCESS owner intent before
interface projection and is passed separately to physical compilation. Projection may
remove every realizable probe permission while the dedicated uid guard remains closed.

Privileged regression LP7 deletes the committed generation, triggers a different owner's
structural reconcile and proves that the probe uid still cannot escape through the live
alternate route.

## Deliberately outside this Adapter

The NetworkRules Adapter does not own:

- `ping_group_range`;
- process gid;
- capabilities / NoNewPrivileges;
- probe executable lifecycle;
- probe scheduling or hysteresis.

Those are process-runtime/AvailabilityProbeManager concerns. Moving them into
NetworkRules would mix process execution with network-policy materialization.

## Evidence

EXP-024 passed unchanged on Debian 13 target.

The production integration then exercised:

```text
ProbeRulesCalculator
    -> common NetworkRulesAdapter
    -> Linux RPDB/nft materialization
    -> fresh exact renew
    -> real kernel dataplane
```

Observed PASS markers:

```text
PASS LP1: production ProbeRules apply and exact renew succeed
PASS LP2: LOCAL_PROCESS-only policy leaves forwarding closed
PASS LP3: unrelated local process retains ordinary alt0 path
PASS LP4: bound capability-free probe uses production probe plane
PASS LP5: UID guard blocks unbound escape and target widening
PASS LP6: bound-output same-name/new-ifindex drift fails exact renew
PASS LP7: projected generation loss retains uid guard across other-owner structural reconcile
NG2_LINUX_LOCAL_PROCESS_INTEGRATION=PASS
```

Post-cleanup NG2 workflow at code commit `fadad395a25e55c85f0dd743f0eb3978eb8010cf`:
unit PASS and full privileged Linux integration PASS. NG1 validation also PASS.

## Next required boundary

The earlier state-model evidence gate is now satisfied.

Next:

1. implement `ProbeRulesStateCalculator` from real NetworkRulesAdapter state;
2. review its semantics independently;
3. compare concrete `PayloadRulesState` and `ProbeRulesState`;
4. introduce a common RulesState type only if that comparison proves equivalence.
