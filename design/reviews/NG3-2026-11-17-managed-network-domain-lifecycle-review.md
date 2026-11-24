# VPN-GATE NG3 — managed network-domain lifecycle review

**Date:** 2026-11-17  
**Cycle branch:** `ng3-design-cycle-20261117-direct-device-bootstrap-35m`

## Scope

Review the executable Linux infrastructure lifecycle for the NG3 managed network domain:

- named network namespace;
- explicit host/inner veth boundary;
- exact IPv4 addressing;
- namespace loopback;
- namespace main-table default route;
- protective IPv4 forwarding closure;
- fresh verification and teardown.

This unit owns infrastructure only. It does not own payload routes/RPDB, nft policy,
publication sockets, VPN path interfaces or user-facing configuration grammar.

## Verdict

**PASS.**

The NG3 implementation safely reuses the already live-proven NG2 namespace/veth lifecycle
facts while adapting the boundary to the current NG3 ForwardingGate and keeping all concrete
instance fields as normalized internal inputs.

No human product decision is required.

## Implementation

New module:

`design/NG3/code/python/rou/managed_network_domain.py`

Public contracts:

- `ManagedNetworkDomainSpec`;
- `ManagedNetworkDomainVerification`;
- `ManagedNetworkDomainEnsureResult`;
- `ManagedNetworkDomainError`;
- `verify_managed_network_domain(...)`;
- `ensure_managed_network_domain(...)`;
- `destroy_managed_network_domain(...)`.

The normalized infrastructure spec is:

```text
namespace
host_interface
inner_interface
host_address: IPv4Interface
inner_address: IPv4Interface
```

No external TOML spelling is selected by this unit.

## Finding F1 — managed-domain infrastructure and network policy must remain separate owners

Historical lifecycle code that also materializes nft/payload state would violate the current
exclusive structural policy boundary.

**Disposition:** the lifecycle owns only:

- namespace;
- boundary veth pair;
- exact boundary IPv4 addresses;
- namespace loopback UP;
- namespace default route.

Fresh creation creates no nft table and no payload route/RPDB state.

The first network-policy materialization remains the separate activation subassembly.

## Finding F2 — existing namespace must be contained before structural verification

A stale existing namespace may still have forwarding enabled.

Inspecting/reconciling it first would create a startup window in which unknown old state can
forward traffic.

**Disposition:** whenever the configured namespace already exists,
`ensure_managed_network_domain(...)` first converges/rereads
`ForwardingGate=DISABLED`, then evaluates presence/structure.

The same ordering applies to namespace-only partial state before failure is returned.

## Finding F3 — only two initial presence shapes are accepted

Allowed:

```text
namespace absent + host boundary absent
    -> create fresh

namespace present + host boundary present
    -> contain + exact verify
```

Rejected:

```text
namespace present XOR host boundary present
```

Partial state is not adopted and not auto-repaired.

This preserves the previously accepted NG2 ownership rule and avoids guessing which half of
a topology belongs to VPN-GATE.

## Finding F4 — existing divergent infrastructure is not repaired in place

For an already present domain, the lifecycle is verification-only after protective
containment.

Failures include:

- wrong/missing veth;
- interface DOWN;
- wrong/missing boundary address;
- extra IPv4 address on an owned boundary;
- loopback not UP;
- wrong/missing default route;
- non-reciprocal veth peer identity.

**Disposition:** return failure with forwarding closed. Replacement requires an explicit
teardown/recreate path rather than silent adoption.

## Finding F5 — veth names/types/addresses are insufficient ownership evidence

Two unrelated veth interfaces could coincidentally have the configured names and addresses.

Current iproute2 JSON exposes cross-namespace peer identity through `link_index`.

**Disposition:** verification requires reciprocal current kernel identity:

```text
host.link_index  == inner.ifindex
inner.link_index == host.ifindex
```

No persistent peer registry is introduced.

The verified namespace-side endpoint is returned as the current
`InterfaceIdentity(ifname, ifindex)` for downstream payload assembly.

## Finding F6 — fresh creation closes forwarding before creating the boundary

Fresh sequence:

```text
create namespace
 -> immediately confirm ForwardingGate=DISABLED
 -> create veth pair
 -> move inner endpoint
 -> assign exact IPv4 addresses
 -> bring host, lo and inner links UP
 -> install default route
 -> fresh exact verification
```

Thus no forwarding-capable managed topology is built before containment is established.

## Finding F7 — failed fresh creation rolls back only resources created by that attempt

The implementation tracks whether namespace/veth creation physically succeeded.

On failure after namespace creation it best-effort deletes the created namespace and the
created surviving host-side veth when present, then propagates the original failure.

It does not perform a generic cleanup/adoption pass over arbitrary pre-existing partial
state.

## Finding F8 — address contract remains normalized lower input

NG3 does not restore NG2 schema-v1 as an external product contract.

The lifecycle validates only the lower requirements needed by Linux:

- both addresses are IPv4;
- distinct;
- same subnet;
- usable for prefixes <= /30;
- /31 is allowed;
- interface names are Linux-safe and distinct.

Address choice and final external instance grammar remain outside this unit.

## Finding F9 — teardown is infrastructure cleanup, not semantic policy cleanup

Destroy performs:

1. best-effort forwarding containment when namespace exists;
2. best-effort namespace deletion;
3. best-effort deletion of any surviving configured host boundary;
4. fresh verification that namespace and host boundary are absent.

Normal product shutdown should release higher policy owners first when possible, but crash
containment does not require semantic cleanup to precede infrastructure removal.

## Evidence

### Rootless

Final code/export baseline before documentation:

`43990320445` — **SUCCESS**

```text
Ran 502 tests
OK
```

New unit coverage includes:

- /31 validation and unsafe spec rejection;
- exact existing-domain containment + verification;
- namespace-only partial-state fail-closed rejection;
- host-only partial-state refusal without adoption;
- reciprocal peer mismatch;
- extra owned IPv4 address drift;
- fresh create ordering;
- failed-create rollback;
- teardown.

### Privileged Linux

Workflow `43990422086`, `linux-payload-forward`: **SUCCESS**

Observed markers:

```text
MANAGED_DOMAIN_FRESH_CREATE_NO_POLICY=PASS
MANAGED_DOMAIN_RESTART_CONTAINMENT=PASS
MANAGED_DOMAIN_DRIFT_REFUSED_FAIL_CLOSED=PASS
MANAGED_DOMAIN_DESTROY=PASS
MANAGED_DOMAIN_PARTIAL_STATE_REFUSED=PASS
NG3 managed network domain lifecycle integration: PASS
```

The disposable kernel test proves:

- real namespace/veth creation;
- reciprocal cross-namespace peer metadata;
- exact addressing/default route;
- lifecycle creates no nft policy;
- restart from `ip_forward=1` is contained before verification;
- deleted default route is refused rather than repaired while forwarding remains closed;
- verified destroy;
- namespace-only partial state is refused after containment.

## Evidence continuity

This unit intentionally reuses accepted facts from the reviewed NG2 lifecycle rather than
copying NG2 architecture wholesale:

Retained:

- explicit namespace/veth isolation topology;
- partial-state refusal;
- reciprocal veth peer verification;
- no policy ownership in infrastructure lifecycle;
- protective restart containment.

Not retained:

- NG2 external schema-v1 as an NG3 user contract;
- NG2 network-policy Adapter/runtime architecture;
- dual-stack policy machinery not present in the current IPv4 NG3 policy contract;
- fixed inner interface name as user-visible semantics.

## Component-model review

The lifecycle functions are procedural Executor responsibilities.

No separate NamespaceManager is justified:

- command runner transports commands;
- managed-domain lifecycle owns one concrete infrastructure domain;
- network-policy activation owns policy materialization.

No long-lived autonomous behavior is added.

## Simplification review

Not introduced:

- namespace ownership database;
- persisted peer ifindex registry;
- automatic partial-state adoption;
- generic topology repair engine;
- nft/bootstrap policy inside instance creation;
- external config grammar;
- background Agent.

## Next lifecycle boundary

With this PASS, the lower startup path can now establish:

```text
managed network domain
    -> current host-boundary InterfaceIdentity
    -> current binding/path realization
    -> complete payload desired state
    -> activate_network_policy(...)
```

The next cross-process startup prerequisite is instance/process exclusion and ownership of
one active controller instance, followed by orchestration of config/fact collection around
these already closed lower boundaries.

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

The managed Linux network-domain infrastructure boundary is now executable, fail-closed,
exactly verified and independent from payload network-policy ownership.
