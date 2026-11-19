# NG3 host-boundary lane structural integration review

**Date:** 2026-11-19  
**Cycle:** `ng3-design-cycle-20261119-alpha-release-blockers-35m`

## Scope

Structural managed-stack integration required by the selected EXP-064 fixed behavior-lane
carrier, before host-side behavior-owner materialization.

This review unit covers:

- explicit semantic route identity for Profile-table behavior-lane defaults;
- authoritative Linux observation of that route identity;
- exact structural comparison/mutation compatibility;
- coupling of a current desired behavior-lane route to initial inbound Profile-table selection;
- preservation of the existing alpha path when no lane route is desired.

It does **not** yet implement the host-side lane behavior owner or remove the alpha `+snat`
fail-fast.

## Requirements / architecture

Implements or supports:

- `VPNG0001-R1.R2.R4.R4.R4`;
- `VPNG0001-R1.R2.R4.R4.R4.R1`;
- `VPNG0004-R4.R6.R1.R6`;
- `VPNG0004-R4.R6.R1.R6.R1`;
- the selected EXP-064 host-boundary behavior-lane architecture.

The lane remains lower infrastructure and does not become a user-visible path or
`LogicalPathId`.

## Implementation

### Structural route role

The managed routing model now distinguishes:

```text
GUARD
VPN_PATH
HOST_BOUNDARY_LANE
```

A `HOST_BOUNDARY_LANE` route:

- is unicast `0.0.0.0/0` in the owning Profile table;
- has no VPN `LogicalPathId`;
- uses the current verified inner lane endpoint and host-side lane gateway;
- uses dedicated owned Linux route protocol `204`;
- uses metric `terminal_guard_metric - 1`, outside the VPN path preference/scratch space;
- therefore outranks the terminal guard without participating in availability/path-priority
  permutation.

The Linux structural inventory recognizes protocol 204 only as a default unicast lane route
with a gateway. Other shapes in that reserved role are conflicts.

### Initial inbound table selection

Stack return-affinity still records the selected Profile in conntrack state for every current
inbound-capable Profile.

Copying that mark into the **initial NEW packet mark** is now an explicit desired classifier
property, not a global behavior. `PayloadNetworkPolicyDesiredState` derives that property from
the same current `HostBoundaryLaneRouteSpec` set supplied to the routing desired-state
builder.

Therefore:

```text
desired lane route for Profile
    <=> initial VPN-originated packet may select that Profile table
```

No desired lane route means no initial packet table selection, preserving current alpha
behavior until lane infrastructure is actually materialized.

Activation remains behind the existing ordering:

```text
ForwardingGate = DISABLED
    -> converge stack affinity
    -> converge structural routes
    -> verify exact complete structural state
    -> only then forwarding may reopen
```

## Review findings and dispositions

### F1 — mechanical platform-field placement defect

The first patch duplicated `host_boundary_lane_route_protocol` in
`NetworkPolicyPlatformSpace` and omitted it from `PayloadPolicyAllocation`.

**Disposition:** accepted and fixed before evidence.

### F2 — desired/observed route-role comparison was asymmetric

The desired route key included semantic role while the observed comparison key initially did
not, causing existing exact structural state to appear stale and breaking structural
postcondition progress.

**Disposition:** accepted and fixed. Desired and observed exact keys now include role
symmetrically.

### F3 — initial packet selection was enabled too early

The first affinity change copied conntrack mark to the initial packet for every inbound
Profile. Existing alpha has no behavior-lane default yet, so the packet selected its Profile
table and reached the terminal guard. `linux-alpha-smoke` correctly detected the regression.

**Disposition:** accepted and fixed. Initial selection is now an explicit per-Profile desired
property coupled to presence of a current desired behavior-lane route. Alpha without lanes is
unchanged and smoke is green again.

### F4 — one focused test used an unrelated two-Profile layout

The first new affinity test supplied a one-Profile semantic input with an existing
two-Profile test layout and correctly tripped the layout exact-set invariant.

**Disposition:** accepted and fixed with a matching one-Profile layout.

## Evidence

Final NG3 Python run on code head `a027993e61aa80099f4821ac8aab64c49c943907`:

- workflow run `44535634708`;
- `unit`: **PASS**;
- `linux-policy-platform`: **PASS**;
- `linux-structural-inventory-shape`: **PASS**;
- `linux-route-priority`: **PASS**;
- `linux-stack-return-affinity`: **PASS**;
- `linux-stack-return-affinity-owner`: **PASS**;
- `linux-host-boundary-behavior-lanes`: **PASS**;
- `linux-composite-host-boundary`: **PASS**;
- `linux-payload-forward`: **PASS**;
- `linux-alpha-smoke`: **PASS**;
- `linux-exp049-openvpn`: **PASS**.

The workflow overall remains red only because of pre-existing active-workflow items:

- `linux-nft-marked-host-bootstrap` — EXP-057 historical rejected mechanism;
- `linux-profile-gateway-nat-association` — EXP-063 historical rejected mechanism;
- `linux-selected-host-bootstrap-backend` — selected EXP-060 backend failure and a real
  remaining release blocker.

Those failures predate and are not regressions of this review unit.

## Simplification review

No behavior lane is represented as a VPN path. No new route-priority Manager, staging engine,
userspace packet proxy, generic mark carrier, or second Profile classifier was introduced.

The dedicated route protocol is required so authoritative observation can distinguish lane
defaults from VPN path routes without consulting desired state.

## Requirement-state inventory

### decomp

Resolved historical links remain:

- `VPNG0005-R5 -> VPNG0005-R5.R6`;
- `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`;
- `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`;
- `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`.

### unreal

none

### broken

none

### rejected_closure

none

## Verdict

**ACCEPT.**

The managed-stack side of the EXP-064 carrier is now structurally representable and
authoritatively observable without changing current alpha behavior when no lane is desired.
The next logical block is the authoritative host-side behavior-lane owner.
