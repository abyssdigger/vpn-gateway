# NG3 deferral — probe local/system materialization

**Status:** POSTPONED IMPLEMENTATION PATH / RELEASE-1 READINESS GATE  
**Created:** 2026-11-16  
**Applies to:** Linux ICMP availability implementation and probe-owned local/system policy

## Why this is a deferral, not an open product requirement

The NG3 requirement tree already closes the first-release availability semantics:

- ICMP echo is the supported first-release active-check mechanism;
- every availability result belongs to one `(Profile, logical path)` subject;
- an enabled probe has one concrete normalized IPv4 target;
- stale evidence must not affect a replacement path generation;
- the probe must not silently escape through another path.

Those product obligations remain mandatory.

What is not yet accepted is one complete **Linux physical implementation path** for
probe-local INPUT/OUTPUT isolation across interface-generation changes.

## Existing evidence

### EXP-024 — target-confirmed selective probe isolation

EXP-024 passed privileged CI and Debian 13.

It proves that the shared managed namespace can isolate a probe without imposing a blanket
local default-DROP on unrelated processes by:

```text
OUTPUT:
    probe process identity
    + exact current output path
    + exact target/protocol
        -> dedicated conntrack mark
        -> accept

INPUT:
    exact current ingress path
    + exact remote source/reply protocol
    + dedicated conntrack mark
        -> accept
```

It also proves that `meta skuid` at INPUT is not a usable receiving-socket discriminator.

### EXP-025 — target-confirmed stale-generation failure

EXP-025 passed on Debian 13 with the negative finding
`STALE-INHERITANCE`.

A marked ICMP conntrack entry can survive concrete interface replacement and be reused by a
later probe with the same tuple/identifier.

Therefore:

```text
fresh (ifname, ifindex)
    + rebuilt RPDB/nft
        !=
fresh conntrack-carried probe identity
```

Any production implementation that uses the EXP-024 mechanism needs an explicit
generation-invalidation boundary.

### EXP-026 — narrow remediation candidate, target proof still open

Privileged CI proves that:

```text
conntrack -D -p icmp -m <dedicated-probe-mark>
```

can remove the probe conntrack class, preserve differently marked control state and force a
reused probe tuple back through NEW + mark-set behavior.

However the repository still records:

```text
privileged CI: PASS
Debian 13 target confirmation: OPEN
```

No target result artifact was found during the 2026-11-16 NG3 review.

## Deferred implementation path

The following must **not** yet be materialized as production NG3 state:

- probe-owned `stack_output` allow/mark rules based on EXP-024;
- probe-owned reverse `stack_input` allow rules based on the carried conntrack mark;
- production conntrack cleanup by dedicated probe mark;
- composite-owner mutation code that assumes EXP-026 is accepted target behavior.

This prohibition is intentionally narrower than the availability feature itself.

## Re-entry conditions

This deferral is reopened when either path A or path B becomes true.

### Path A — confirm the current candidate

1. run the unmodified EXP-026 mechanism on the supported Debian 13 target;
2. retain an explicit target result artifact;
3. confirm that probe-mark cleanup removes only the intended probe class and preserves
   unrelated conntrack state;
4. explicitly accept probe-class-wide invalidation as the generation-boundary policy;
5. then design/implement exact probe owner desired/observation/mutation inside the shared
   network-policy convergence boundary.

### Path B — replace the mechanism

Provide evidence for another Linux ICMP implementation that:

- binds the observation to the exact current logical path;
- cannot escape through an alternate Device;
- does not require unsafe broad INPUT/OUTPUT permission;
- does not inherit stale process/flow identity across path generation replacement;
- preserves unrelated local traffic;
- has an exact observable postcondition suitable for guarded convergence.

A replacement mechanism is not required to use uid, conntrack mark or the EXP-024 topology.

## Release-1 consequence

This deferral is **not** permission to ship a first release without the accepted ICMP
availability capability.

Before production readiness, one implementation path must satisfy the accepted ICMP
requirements. Release 1 may ignore EXP-026 only if the selected production mechanism does
not depend on the EXP-024-style conntrack-carried identity that requires this remediation.

## Blocking scope

This deferral blocks:

- production probe-local INPUT/OUTPUT materialization;
- production probe conntrack-generation cleanup;
- claiming the Linux ICMP Driver path is physically complete.

It does not block:

- publication-local rules already closed by EXP-046/047;
- normalized availability configuration/target semantics;
- pure availability subject/effective-priority logic;
- payload Profile/Device/NAT convergence;
- experiments or alternative implementation evidence.

## Requirement-state inventory

- active `decomp`: none pending; the six accumulated links remain resolved;
- active `unreal`: none;
- `[rejected_closure]`: none.

The architecture closure remains accepted. This artifact records an implementation/evidence
gate, not a failed requirement/architecture closure.
