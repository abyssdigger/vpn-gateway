# NG3 — probe local/system materialization decision record

**Status:** SUPERSEDED RELEASE-1 GATE / retained evidence record  
**Originally created:** 2026-11-16  
**Superseding decision:** 2026-11-18  
**Applies to:** Linux ICMP availability implementation and probe-owned local/system policy

## Current decision

The former requirement to prove and deploy an explicit probe-generation conntrack cleanup
boundary is **not a Release-1 readiness gate**.

Release 1 does not require every ICMP probe after a physical interface replacement to obtain a
fresh kernel conntrack identity merely because the previous interface incarnation disappeared.
The product-relevant requirements are narrower:

- the observation belongs to the current availability subject = (Profile, logical path);
- it executes toward the current normalized target through the selected current probe path;
- stale/in-flight results from a preceding subject/target/path-binding context are rejected;
- probe-owned state must not select, migrate or otherwise change payload routing/return affinity;
- isolated observations are filtered by the accepted degradation/recovery confirmation logic.

## Evidence retained

### EXP-024

Target-confirmed on Debian 13. It proved selective shared-namespace ICMP probe isolation using:

```text
OUTPUT:
    probe process identity + exact current path + target/protocol
        -> dedicated probe conntrack mark
        -> accept

INPUT:
    exact current ingress path + expected source/reply protocol
    + dedicated probe conntrack mark
        -> accept
```

It also disproved INPUT `meta skuid` as a receiving-socket discriminator.

### EXP-025

Target-confirmed negative finding: a marked ICMP conntrack entry may survive interface
replacement and be reused by a later probe with the same tuple/ICMP identifier.

This proves:

```text
fresh interface/rules
    != necessarily
fresh lower conntrack-carried probe identity
```

It does **not** prove that the stale entry can synthesize an ICMP reply, move a payload flow to
another logical path, or change payload return-affinity ownership.

### EXP-026

Privileged CI proved a narrow cleanup mechanism:

```text
delete ICMP conntrack entries carrying the dedicated probe mark
```

The mechanism removed the probe class, preserved differently marked control state and forced a
reused probe tuple back through NEW + mark-set behavior.

Debian 13 target confirmation remains absent. The project deliberately does **not** pursue that
target confirmation for Release 1 because the cleanup itself is no longer required by the
accepted product semantics.

## Release-1 simplification

Production ICMP materialization may use the EXP-024-style selective local isolation without
adding probe-generation conntrack deletion, provided its implementation proves the following
non-interference boundary:

```text
probe-local conntrack/packet state
    cannot select a payload Profile/path

probe routing resources
    are disjoint from payload dispatch and managed-stack return-affinity resources

no generic probe ct-mark restoration
    can write a routing mark onto forwarded payload traffic
```

A namespace-wide conntrack flush remains prohibited.

A same logical path that disappears and later reappears is not promised lossless continuity of
in-flight traffic. Availability exists to preserve access through remaining usable allowed
paths, not to provide guaranteed delivery across path disappearance.

## Re-entry

EXP-026 or another generation cleanup mechanism becomes relevant again only if new evidence
shows a material observable failure, for example:

- stale probe state can route payload through the wrong logical path/Profile;
- stale probe state can make a probe escape through an unselected path;
- repeated stale observations can defeat the accepted confirmation accumulator in a practical
  supported scenario;
- a future release explicitly requires stronger per-generation probe identity semantics.

Until such evidence exists, EXP-026 is retained as useful technical evidence/optional
hardening, not production scope.

## Outbound per-flow blocker superseded

The later per-flow outbound-affinity gate is also no longer a Release-1 availability
prerequisite. The accepted sticky active-route policy avoids recovery-driven route migration
by keeping a healthy ordinary active path first; only an explicit Profile-local reserve
membership permits recovery failback.

Per-flow concrete-path affinity remains useful future mechanism evidence, but Release 1 does
not need it merely to make outbound multi-path availability safe. Remaining availability
readiness work is the ordinary implementation/integration of the accepted probe,
confirmation, sticky-active and reserve policy contracts.

## Requirement-state classification

This decision creates no `decomp`, `unreal`, `broken` or `[rejected_closure]` state.
EXP-025 remains valid evidence; EXP-026 remains a valid mechanism result whose Release-1
adoption is deliberately not selected.
