# VPN-GATE NG3 — complete payload lower desired-state assembly review

**Date:** 2026-11-17  
**Cycle branch:** `ng3-design-cycle-20261117-policy-activation-35m`

## Scope

Review the pure composition boundary that combines all currently materialized payload
network-policy owner projections into the exact lower desired-state pair consumed by
`activate_network_policy(...)`.

The unit accepts already-normalized semantic/lower facts and performs no Linux observation or
mutation.

## Verdict

**PASS.**

The current Release-1 payload owner scopes can now be assembled deterministically into one
`PayloadNetworkPolicyDesiredState` containing:

- `PayloadRoutingDesiredState`;
- `CompositeNftDesiredState`.

No human decision is required.

## Implementation

New module:

`design/NG3/code/python/rou/payload_network_policy_desired.py`

Public contracts:

- `PayloadNetworkPolicyProjectionError`;
- `PayloadNetworkPolicyDesiredState`;
- `build_payload_network_policy_desired_state(...)`.

Inputs:

```text
PayloadProfileRequest set
NetworkPolicyLayout
current RoutePriorityPathRoute set
current host-boundary InterfaceIdentity
normalized DeviceNatPolicyIntent set
normalized DeviceFirewallPolicyIntent set
normalized PublicationLocalEndpointIntent set
```

Output:

```text
PayloadNetworkPolicyDesiredState:
    routing: PayloadRoutingDesiredState
    nft: CompositeNftDesiredState
```

## Finding F1 — composition must delegate owner semantics

A new aggregate compiler must not become a second policy language.

**Disposition:** the assembly delegates to the already reviewed owner-specific pure
projections:

- routing/RPDB -> `build_payload_routing_desired_state(...)`;
- Profile forwarding -> `compile_payload_forward_policy(...)`;
- Device NAT -> `build_payload_nat_desired_state(...)`;
- Device firewall -> `compile_device_firewall_policies(...)`;
- publication-local -> `build_local_publication_desired(...)`.

The resulting owner states are only packaged into `CompositeNftDesiredState`.

## Finding F2 — zero-path Profile must remain structurally present

A Profile with zero current paths must not disappear merely because no positive forwarding
rule or NAT/firewall path object exists.

**Disposition:** zero-path assembly still produces:

- Profile terminal blackhole guard;
- Profile RPDB dispatch;
- zero positive Profile forward rules;
- zero path NAT rules;
- zero Device firewall chains.

This preserves the existing fail-closed routing domain semantics.

## Finding F3 — “no NAT” and “omitted firewall” must be explicit normalized inputs

For a Device backing a current path, absent semantic data must not silently become an allow
default.

The current normalized no-op forms are:

```text
DeviceNatPolicyIntent(device_id, NatIntent.NONE)
DeviceFirewallPolicyIntent(device_id, rules=None)
```

**Disposition:** the assembly relies on the owner-specific compilers to reject missing
normalized NAT/firewall semantics for a current Device.

This keeps parser/semantic assembly bugs from widening policy.

## Finding F4 — publication must use the same current host-boundary generation

Publication-local rules are an independent local/system owner class but they share the
managed host boundary with payload routing and forward policy.

Supplying a publication intent bound to another generation of the host boundary would create
an internally split desired state.

**Disposition:** every publication intent supplied to this assembly must carry exactly the
same current `InterfaceIdentity` as the assembly host boundary.

Mismatch is a projection error before any actuation.

## Finding F5 — input iteration order is not semantic

The composition receives several iterable inputs whose caller order may differ between
reconciliation passes.

**Disposition:** owner-specific projections already canonicalize their semantic sets; the
aggregate state is therefore deterministic for equivalent input sets.

A regression test reverses Profile, path-route, NAT-policy and firewall-policy iteration
order and obtains the same complete desired state.

## Finding F6 — probe allocation remains outside this materialized payload scope

`NetworkPolicyLayout` is shared and may contain probe reservations, but production
probe-plane realization remains separately deferred.

This assembly consumes only payload allocation/dispatch fields and does not manufacture probe
routes, RPDB rules or nft contributions.

It therefore must be described as the **payload** lower desired-state assembly, not the
complete future network-policy model.

## Evidence

Behavior-bearing workflow for the assembly tests: **SUCCESS**.

```text
Ran 493 tests
OK
```

New tests cover:

- zero-path guard + dispatch with no positive nft permission;
- one current path with routing, Profile forward, NAT, Device firewall and publication-local
  all composed simultaneously;
- missing normalized NAT semantics rejected;
- missing normalized firewall semantics rejected;
- publication host-boundary generation mismatch rejected;
- deterministic output under reversed iterable order.

No new privileged experiment is required because this unit introduces no Linux primitive or
representation. Every physical owner class is already covered by its lower evidence and the
network-policy activation integration.

## Component-model review

This is a pure Calculator/composition boundary:

- no I/O;
- no mutable state;
- no retry;
- no lifecycle;
- no Driver;
- no readiness decision.

No new Manager, Agent or Engine is introduced.

## Simplification review

Not introduced:

- global policy AST;
- duplicate owner compilers;
- new allocation scheme;
- persistent desired-state registry;
- probe realization;
- user-facing grammar;
- runtime config singleton.

The aggregate dataclass exists only to make the exact activation input explicit.

## Remaining path toward full startup

The lower payload path is now contiguous:

```text
normalized semantic inputs
    -> PayloadProfileRequest/current path realization
    -> complete PayloadNetworkPolicyDesiredState
    -> activate_network_policy(...)
    -> verified READY / explicit contained failure
```

Full product startup still separately requires:

- instance ownership/exclusion;
- managed-domain/boundary construction;
- configuration load/validation sequencing;
- production collection of current path realization facts;
- runtime reconciliation scheduling;
- shutdown/cleanup;
- status publication/control surface.

Those concerns must compose the closed lower path rather than duplicate it.

## Accumulated requirement-state inventory

### `decomp`

All six accumulated links remain **resolved**. Pending: **none**.

### `unreal`

**none**

### `[rejected_closure]`

**none**

## Human decisions required

**none**

## Conclusion

**PASS.**

The currently implemented payload owner domains now have one deterministic pure desired-state
assembly directly consumable by the guarded activation subassembly, without introducing new
policy semantics or deferred probe/user-grammar behavior.
