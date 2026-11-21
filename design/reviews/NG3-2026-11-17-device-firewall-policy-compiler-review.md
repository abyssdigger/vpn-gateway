# VPN-GATE NG3 — multi-path Device firewall policy compiler review

**Date:** 2026-11-17  
**Cycle branch:** `ng3-design-cycle-20261117-policy-activation-35m`

## Scope

Review the pure composition layer that applies one normalized Device firewall policy to every
current payload path of that Device and assigns deterministic production child-chain names.

This unit closes the remaining caller-supplied child-chain naming gap above the already
evidence-backed one-path `compile_device_firewall_policy(...)`.

## Implements

- `VPNG0001-R1.R2.R4.R6.R2` and its ordinary Release-1 Device-firewall children;
- current path identity/binding safety from `VPNG0001-R1.R3.R2` / `R1.R3.R3`;
- minimal lower identity and explicit contract requirements from
  `VPNG0007-R7.R1` / `R7.R3.R1`.

External firewall grammar remains deferred and is not selected here.

## Verdict

**PASS.**

The compiler provides deterministic safe lower child-chain identity for current paths without
embedding user IDs, hashing semantic names or introducing persistent naming state.

No human decision is required.

## Implementation

New module:

`design/NG3/code/python/rou/device_firewall_policy_compiler.py`

Public contracts:

- `DeviceFirewallPolicyCompileError`;
- `compile_device_firewall_policies(...)`.

Inputs:

```text
normalized DeviceFirewallPolicyIntent set
+ current RoutePriorityPathRoute set
+ current host-boundary InterfaceIdentity
    ->
DeviceFirewallDesiredState
```

The existing one-path compiler remains the owner of ordered rule/predicate/action lowering.

## Finding F1 — chain names must not expose arbitrary user IDs

Embedding Device/Profile IDs directly into nft object names would make external identifiers a
lower ownership mechanism and require escaping/length/collision semantics not justified by
requirements.

**Disposition:** current logical paths are sorted by canonical `LogicalPathId`; their
zero-based current-policy ordinal becomes the only naming token:

```text
df_out_<8-digit lowercase hex ordinal>
df_in_<8-digit lowercase hex ordinal>
```

Examples:

```text
df_out_00000000
df_in_00000000
df_out_00000001
```

The names are safe lowercase nft identifiers and contain no user-supplied text.

## Finding F2 — persistent naming registry is unnecessary

A persistent logical-path -> chain-token registry would add state, recovery and ownership
semantics solely to reduce nft object churn.

No Release-1 requirement promises stable physical nft object names across structural path
membership changes.

**Disposition:** names are recomputed from the canonical current path set. A membership
change may renumber later paths; the guarded structural Executor safely treats old chains as
stale and replaces them while forwarding is closed.

This is simpler than a durable token allocator and changes no user-visible semantics.

## Finding F3 — input order must not affect lower identity

Discovery/assembly callers may supply current path routes in different iteration order.

**Disposition:** the compiler indexes by `LogicalPathId`, sorts canonical path IDs, then
assigns ordinals.

Tests prove reversed path-route and policy input order produces exactly the same desired
state and chain names.

## Finding F4 — same Device multi-path requires separate physical chains

One Device policy can apply to multiple current logical paths. Reusing one child chain/jump
identity would collapse exact ingress/egress ownership.

**Disposition:** each current logical path gets its own OUT and IN chain pair even when
several paths share the same Device policy.

The normalized policy is reused semantically; physical chain identity remains path-specific.

## Finding F5 — omitted policy is explicit, missing policy is not

Accepted semantics distinguish:

```text
DeviceFirewallPolicyIntent(device_id, rules=None)
    -> firewall omitted
    -> no Device-layer restriction
    -> no child chains

no DeviceFirewallPolicyIntent for a Device with a current payload path
    -> caller/assembly input is incomplete
    -> compile error
```

Treating missing policy as omission would turn an upstream omission/bug into implicit allow.

Extra normalized policies for Devices with no current path are harmless and do not create
physical state.

## Finding F6 — current endpoint identity remains strict

The compiler rejects:

- duplicate realization for one logical path;
- one current endpoint backing multiple logical paths;
- host boundary reused as a Device path endpoint.

It does not discover or infer interfaces.

Same-name/new-ifindex handling therefore remains in the established current binding and
structural observation boundaries.

## Finding F7 — one-path semantic compiler remains authoritative

For each explicit current Device/path, this composition layer calls:

`compile_device_firewall_policy(...)`

with the current host/path identities and allocated OUT/IN names.

It does not duplicate:

- first-match rule ordering;
- IN/OUT filtering;
- ALLOW -> return;
- DENY -> drop;
- REJECT realization;
- terminal explicit-policy fallthrough DROP.

Thus EXP-041..044-backed semantics remain centralized in the existing compiler.

## Evidence

Workflow `43967397218`: **SUCCESS**

```text
Ran 487 tests
OK
```

New rootless coverage proves:

- canonical one-path OUT/IN names;
- omitted firewall -> no chains;
- input-order-independent naming;
- same-Device multi-path distinct chain pairs;
- missing normalized policy rejected;
- unused extra policy ignored;
- duplicate policy rejected;
- duplicate path realization rejected;
- shared endpoint rejected;
- host-boundary endpoint rejected.

No new privileged experiment is required: this unit introduces no new nft primitive or JSON
representation. Generated chains use the already tested lower Device compiler and mutation
path.

## Component-model review

This is a pure Calculator/composition responsibility:

- no I/O;
- no mutable state;
- no retry;
- no lifecycle;
- no observer;
- no Driver.

No new Manager/Agent/Engine is introduced.

## Simplification review

Not introduced:

- user-ID encoding into nft names;
- hash/token collision protocol;
- persistent chain-name registry;
- historical generation counter;
- random UUIDs;
- alternate firewall compiler;
- per-Device runtime manager.

The current ordinal is sufficient because physical identity is internal and structural
changes are already guarded.

## Residual lower desired-state assembly gap

After this PASS the major pure owner projections now exist:

- payload routing desired state;
- semantic Profile forward desired state;
- Device NAT desired state;
- multi-path Device firewall desired state;
- publication-local desired state.

The next pure composition unit can combine these already-normalized projections into
`PayloadRoutingDesiredState + CompositeNftDesiredState` for
`activate_network_policy(...)`.

It must still accept normalized Device policy/publication inputs and must not invent the
deferred external grammar.

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

The Device firewall lower namespace now has deterministic multi-path production chain
identity and complete normalized-policy composition without persistent naming machinery or
user-ID leakage.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG0007-R7.R1` -> `VPNG9001-R1.R1.R1`

The original IDs in the historical body are intentionally preserved.
