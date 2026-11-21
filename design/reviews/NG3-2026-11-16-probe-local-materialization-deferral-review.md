# VPN-GATE NG3 — probe local/system materialization deferral review

**Date:** 2026-11-16  
**Cycle branch:** `ng3-design-cycle-20261116-local-publication-cont-35m`

## Scope

Review whether NG3 can honestly materialize the remaining probe-owned local/system policy
after closing Device transport publication.

This review covers only the Linux physical implementation/evidence boundary for the
first-release ICMP availability mechanism. Product semantics, availability subject identity,
target normalization and effective-priority behavior are already closed elsewhere.

## Verdict

**PASS — implementation path postponed behind an explicit evidence gate.**

NG3 must not materialize EXP-024-style probe INPUT/OUTPUT rules plus EXP-026 cleanup as
production state yet. The repository has target-confirmed positive evidence for EXP-024,
target-confirmed negative evidence for EXP-025, but only privileged-CI evidence for the
EXP-026 remediation.

This is not a product deferral and not permission to omit first-release ICMP availability.

## Evidence review

### EXP-024 — target-confirmed mechanism viability

EXP-024 proves on Debian 13 that selective probe-process isolation inside the shared managed
namespace is technically viable when process identity is captured on OUTPUT and carried to
reverse INPUT through a dedicated conntrack mark.

It also rejects INPUT `meta skuid` as the receiving-socket discriminator.

### EXP-025 — target-confirmed generation failure

EXP-025 proves on Debian 13 that the marked ICMP conntrack entry can survive interface
replacement and be inherited by a later probe that reuses the same tuple/identifier.

Therefore exact current `(ifname, ifindex)` nft/RPDB regeneration does not by itself
establish fresh probe-flow identity.

### EXP-026 — remediation candidate still lacks target confirmation

EXP-026 proves in privileged CI that mark-filtered ICMP conntrack deletion can:

- remove the dedicated probe conntrack class;
- preserve differently marked control state;
- force reused probe traffic back through NEW + mark-set.

The project contains no Debian 13 target-result artifact for EXP-026. Multiple NG2/NG3
artifacts explicitly retain that target confirmation as open.

## Findings

### F1 — the ICMP requirement itself cannot be postponed

`VPNG-U003-R3.R6.R3.R1.C1` requires ICMP echo as the first-release availability mechanism.

**Disposition:** keep the requirement/architecture closure unchanged. The new deferral applies
only to one physical Linux implementation path.

### F2 — EXP-024 alone is insufficient for production generation safety

The EXP-024 mechanism is viable but generation-sensitive; EXP-025 proves stale inheritance.

**Disposition:** do not implement probe-owned local rules using only EXP-024 semantics.

### F3 — CI-only EXP-026 evidence must not be silently promoted to target proof

The accepted evidence discipline distinguishes privileged-CI mechanism evidence from
target-system confirmation where the architecture explicitly requires the latter.

**Disposition:** the current candidate remains blocked until Debian 13 confirmation or an
explicitly reviewed alternative implementation removes the dependency.

### F4 — no broad fallback is allowed

A broad local INPUT/OUTPUT exception, namespace-wide conntrack flush, or unbound ICMP probe
would weaken the accepted safety/path-specificity semantics.

**Disposition:** no fallback materialization is introduced.

### F5 — re-entry has two valid paths

The implementation can re-enter through either:

1. target-confirmed EXP-026 plus explicit acceptance of probe-class-wide generation
   invalidation; or
2. another evidenced Linux ICMP mechanism that preserves path binding, local isolation,
   generation freshness and unrelated traffic without relying on the stale conntrack identity.

The architecture does not preselect which path must win.

## Requirement-state classification

This gate does **not** create:

- `decomp` — product semantics are already concrete;
- `unreal` — the requirements remain satisfiable;
- `[rejected_closure]` — the architecture closure remains accepted.

It is an implementation/evidence deferral beneath the closed architecture.

## Artifact

The normative implementation deferral is:

`design/deferrals/NG3-probe-local-system-materialization.md`

The architecture now links directly to that artifact from the Linux probe evidence gate.

## Accumulated requirement-state inventory

### `decomp`

All six accumulated links remain resolved. Pending: **none**.

### `unreal`

**none**

### `[rejected_closure]`

**none**

## Human decisions required

**none at the current gate.**

If Path A is used after target confirmation, re-entry review must explicitly accept or reject
probe-class-wide ephemeral conntrack invalidation as the production generation-boundary
policy.

## Conclusion

**PASS.** Probe-owned local/system materialization is now explicitly postponed at the correct
layer. The next implementation cycle must not reopen the same candidate without satisfying a
documented re-entry condition.
