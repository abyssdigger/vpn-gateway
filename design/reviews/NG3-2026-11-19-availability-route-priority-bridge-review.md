# NG3 availability effective-order to route-priority review

**Date:** 2026-11-19  
**Cycle:** `ng3-design-cycle-20261119-probe-continuous-availability-loop-35m`  
**Scope:** bridge from effective availability order to the already accepted make-before-break
route-priority convergence machinery.

## Reviewed contracts

- `VPNG0003-R3.R2`
- `VPNG0003-R3.R3`
- `VPNG0003-R3.R4`
- `VPNG0003-R3.R7`
- `VPNG0003-R3.R8`
- `VPNG0004-R4.R3.R1`
- architecture §10.1 pure priority permutation.

No product requirement or user-facing configuration changed.

## Implementation

`availability_route_priority.py` is intentionally a thin composition layer:

```text
effective PayloadProfileRequest order
+ existing NetworkPolicyLayout
+ current RoutePriorityPathRoute realization
        |
        v
existing RoutePriorityDomainRealization
        |
        v
existing RoutePriorityDomainRequest
        |
        v
converge_route_priority_profile_once
        |
        v
IproutePriorityBackend
```

The bridge exposes a pure plan builder and a one-call physical coordinator. It allocates no
new metrics/tables/rules and does not duplicate route mutation logic.

## Findings and dispositions

### F1 — availability must reuse the shared payload metric space

Introducing an availability-specific metric namespace would create a second owner of the same
route-key domain and invalidate the existing make-before-break proof.

**Disposition:** fixed by construction. The bridge consumes the existing
`PayloadPolicyAllocation.metric_space` from `NetworkPolicyLayout`.

### F2 — effective order must alter only metric assignment, not membership

Availability is allowed to permute preference only. Supplying a path realization outside the
effective Profile membership, or omitting one, must not fall through to the priority-only
Executor.

**Disposition:** fixed. The bridge requires the supplied physical path set to equal the union
of effective Profile path membership before creating any backend/request.

### F3 — every Profile destination must converge to the same effective path order

A Profile may own multiple destination route-key domains. Partial semantic ordering across
destinations would violate the Profile-level effective-order contract.

**Disposition:** verified. The existing domain builder emits one realization per destination,
all from the same effective `ordered_paths`. Focused tests assert identical metric preference
for every destination.

### F4 — zero-path Profiles must not create bogus priority I/O

A structurally valid zero-path Profile has no route-priority domain and should remain
fail-closed through its structural routing table/guard, not through a fabricated metric
transaction.

**Disposition:** fixed by composition. Zero-path plans contain no domain requests and are
reported confirmed without invoking the physical runner.

## Evidence

Focused tests cover:

- effective order `B,A` mapping to preference metrics `B=1, A=2`;
- shared scratch metric retained from existing allocation;
- multiple Profile destinations receive the same effective order;
- zero-path Profile creates no priority I/O;
- physical path membership mismatch is rejected;
- effective Profile/layout identity mismatch is rejected.

The lower make-before-break planner, partial-state recovery, physical backend and Profile-level
fresh final verification remain covered by their existing dedicated suites.

## Simplification review

No new route Manager, allocator, metric policy, backend, transaction or retry loop was added.
Availability only supplies the desired semantic permutation to the existing route-priority
Executor.

## Requirement-state inventory

### decomp

All existing occurrences remain resolved:

- `VPNG0005-R5 -> VPNG0005-R5.R6`
- `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`
- `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`
- `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`

### unreal

none

### broken

none

### rejected_closure

none

## Verdict

**ACCEPT**, subject to current branch unit evidence passing. This unit implements already
closed contracts and requires no requirement-state change.
