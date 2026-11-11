# NG1 blocker — production payload NAT policy

Status: **OPEN DESIGN BLOCKER; isolated behind runtime provider**

Architecture baseline: NG1 Draft 4.

## Why this is blocked

Draft 4 assigns payload NAT ownership to TrafficEngine only "where configured/required".
The human-facing configuration contract does not yet define:

- whether NAT is absent by default or mandatory for any Profile/Device class;
- whether policy is Profile-scoped, Device-scoped, binding-scoped or destination-scoped;
- whether the first supported action is only MASQUERADE or also explicit SNAT;
- whether inbound-capable Profiles change NAT behavior;
- how NAT policy composes with a shared Device used by multiple Profiles.

ROU v0 used per-binding MASQUERADE, but that is executable evidence for the lab topology,
not sufficient authority to make MASQUERADE a universal production semantic.

This is a policy/configuration decision, not a kernel uncertainty. No live experiment can
choose the correct administrator-facing semantics.

## Development rule

Production config must not silently infer NAT.

The runtime uses an injected normalized NAT provider:

- tests may inject explicit no-NAT behavior;
- experiments may inject a temporary MASQUERADE provider;
- production configuration remains blocked from selecting NAT until the grammar/scope is
  agreed.

All routing, firewall, observation, verification and PlannerEngine work may proceed around
this gate.

## Resolution required

A future design pass must fix:

1. normalized NAT policy scope;
2. TOML grammar;
3. interaction with shared Devices and Profile direction;
4. supported actions;
5. verification representation.

After that, the provider becomes a normal TrafficEngine projection rather than a gate.
