# NG3 2026-11-18 — Linux VPNPathAdapter runtime collection gate

## Scope

Close the executable-reference gap between the already accepted `VPNPathAdapter` architecture
and the alpha/controller code that currently performs raw `ip -j link show` parsing inline.

## Requirements

**Implements:**

- `VPNG0001-R1.R3.R1`;
- `VPNG0001-R1.R3.R2`;
- `VPNG0001-R1.R3.R3`;
- `VPNG0001-R1.R3.R4`;
- `VPNG0001-R1.R3.R4.R1`;
- `VPNG0001-R1.R3.R4.R2`;
- `VPNG0001-R1.R3.R4.R3`;
- `VPNG0001-R1.R3.R4.R3.R1`;
- `VPNG0001-R1.R3.R4.R4`;
- `VPNG0004-R4.R6.R1.R4`;
- `VPNG0007-R7.R3`;
- `VPNG0007-R7.R5`.

All governing nodes are already closed in the current architecture.

## Selected boundary

The Linux Adapter is stateless and direct:

```text
poll/event wakeup
    ->
fresh full managed-netns interface inventory
    ->
strict InterfaceIdentity parsing
    ->
exact verified host-boundary generation check
    ->
existing stable-slot Device binding projection
    ->
current DeviceBindingProjection
```

The caller retains `DeviceBindingState`; the Adapter does not own path history.

## Non-goals

This unit does not add:

- Netlink event state as authority;
- caches or interface history;
- a process registry;
- VPN provisioning;
- transport-endpoint provenance;
- availability target inference;
- path preference/health decisions;
- retry queues or background workers.

The alpha's existing periodic timer remains only a wakeup cadence. Every decision uses a new
authoritative snapshot.

## Error semantics

Failure to execute or parse the current interface inventory is an observation failure. It must
not be converted to an empty endpoint set.

A verified managed-domain host-boundary generation missing from the fresh inventory is an
observation failure, not a reason to proceed with a different same-name interface.

Binding ambiguity/selector errors remain the existing binding projector's explicit failure.

## Evidence plan

Rootless tests prove:

1. full current inventory is parsed and projected through the Adapter;
2. exact host-boundary identity is required when supplied;
3. same-name/new-ifindex endpoint replacement is observed as a new concrete generation;
4. lower observation failure is propagated and never treated as an empty inventory;
5. the Adapter retains no mutable current-state cache.

The alpha/controller startup and periodic reconcile paths must then consume this Adapter rather
than issuing their own raw interface inventory command.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG0007-R7.R3` -> `VPNG9001-R1.R1.R3`
- `VPNG0007-R7.R5` -> `VPNG9001-R1.R1.R5`

The original IDs in the historical body are intentionally preserved.
