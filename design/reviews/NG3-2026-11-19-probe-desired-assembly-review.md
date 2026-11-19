# NG3 probe desired-state assembly review

**Date:** 2026-11-19  
**Scope:** pure composition from accepted Release-1 availability selection to shared lower
network-policy allocation and probe desired state.

## Reviewed contracts

- `VPNG0003-R3.R6`
- `VPNG0003-R3.R6.R1`
- `VPNG0003-R3.R6.R2`
- `VPNG0003-R3.R6.R3`
- `VPNG0003-R3.R6.R3.R1`
- `VPNG0003-R3.R6.R3.R1.C1.R1`
- `VPNG0003-R3.R6.R3.R2`
- shared lower ownership/allocation architecture in §8.2, §8.3 and §9.2.

No product requirement changed in this review unit.

## Resulting executable boundary

`probe_desired.py::build_probe_desired_assembly` now composes:

```text
Release1Config
+ current PayloadProfileRequest set
+ current RoutePriorityPathRoute set
        |
        v
AvailabilityDescriptionResolver
        |
        v
AvailabilityProbeIntent(owner = Profile + logical path)
        |
        v
ProbeRoutingDemand
        |
        +------------------------+
        | shared allocation      |
        | payload + probe owners |
        +------------------------+
        |
        v
ProbeNetworkPolicyDesiredState
```

The unit performs no I/O, scheduling, confirmation/hysteresis or probe execution.

## Findings and dispositions

### F1 — probe allocation must not become an independent allocator

Calling the probe allocation pools separately from payload allocation would create two
competing views of one lower Linux policy namespace and violate the accepted shared layout
boundary.

**Disposition:** fixed by construction. The assembly calls
`allocate_network_policy_layout(payload_profiles, probe_demands, platform)` once and then
passes that same layout to probe projection.

### F2 — Device default resolution must happen before lower allocation

Lower allocation owns numeric resources, not product configuration selection. Carrying
`default` or a Device/Profile inheritance marker into probe routing would leak user
configuration semantics below the normalization boundary.

**Disposition:** fixed by construction. Only concrete `AvailabilityProbeIntent` values reach
`ProbeRoutingDemand` and `probe_policy`.

### F3 — current payload path membership and physical path realization must agree

Without an explicit consistency check, a caller could supply a route realization for a path
that its current payload Profile projection does not contain, allowing the probe assembly to
produce owner state from inconsistent current inputs.

**Disposition:** accepted and fixed. The assembly rejects a mismatch between the union of
current `PayloadProfileRequest.ordered_paths` and the set of supplied
`RoutePriorityPathRoute.path_id` values.

### F4 — same-target multi-path must remain distinct after assembly

The new Device-default reuse makes same-target multi-path a normal case. Assembly must create
one probe owner/allocation per `(Profile, path)`, not deduplicate by target.

**Disposition:** verified by tests. Two paths with the same target receive distinct probe
tables/rule priorities and retain distinct concrete endpoints.

## Evidence

Unit coverage added for:

- shared payload + probe allocation;
- no availability -> no probe owner state;
- same target on two paths -> two distinct probe allocations/endpoints;
- mismatched payload/path realization -> fail closed;
- duplicate physical logical-path realization -> rejection.

The branch-level NG3 Python workflow is the execution authority for the full unit suite. The
known unrelated privileged failures in EXP-057/060/063 remain baseline failures from main and
are not used as positive evidence for this unit.

## Simplification review

No new Manager, scheduler, allocator, probe framework, runtime state store or Engine was
introduced. The unit is one pure orchestration function over already accepted Calculators and
lower projections.

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

**ACCEPT**, conditional only on the branch unit suite remaining green at this source state or
a descendant containing no semantic change to this unit. No new requirement closure is
needed because this is implementation of already closed contracts.
