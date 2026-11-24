# VPN-GATE NG3 — managed local/system allow policy design review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-local-system-allow-35m`

## Scope

Review the smallest architecture boundary above the accepted `stack_input` /
`stack_output` terminal-DROP scaffold. The unit covers only VPN-GATE-owned local/system
exceptions required by already accepted Release-1 functions. It does not define Device
firewall policy and does not select new user-facing configuration syntax.

## Requirement trace

**Implements:**

- `VPNG-U004-R4.R6.R1.R5`;
- `VPNG-U004-R4.R6.R1.R5.R1`;
- `VPNG-U001-R1.R2.R4.R6.R3` where publication requires local transport traffic;
- `VPNG-U001-R1.R3.C1.R1` for explicit supported-integration local control needs.

The full relevant requirement statements already require terminal DROP defaults, explicit
owned exceptions, VPN-GATE ownership of control/probe/publication/integration exceptions,
and separation from user Device firewall policy.

## Findings and dispositions

### F1 — a fixed broad exception list would invent scope

A static rule set such as "allow loopback + established/related + ICMP + listener ports"
would broaden local acceptance beyond the concrete function that needs each packet.

**Disposition:** fixed in architecture. Desired local/system policy is compiled only from
typed `LocalSystemAllowIntent` contributions with an explicit `owner_function` and the
selectors needed to prevent scope broadening.

### F2 — generic conntrack acceptance is not a safe default

A blanket local `ct state established,related accept` would admit return traffic for
unrelated local connections and would therefore weaken the accepted terminal-DROP boundary.

**Disposition:** explicitly forbidden as an implicit default. A state match may be used only
inside a bounded contribution whose complete selector set is justified by its owner
function.

### F3 — Device firewall must not leak into local hooks

The user Device firewall constrains managed payload forwarding. Copying its ALLOW rules into
`stack_input` / `stack_output` would create host/control-plane permissions the user never
requested and would conflate two accepted policy domains.

**Disposition:** explicitly forbidden. Device firewall remains a payload-forwarding input
only.

### F4 — probe contribution cannot yet be materialized honestly

NG3 already defines the first-release probe semantic contract: one concrete ICMP target per
availability subject and exact current-path execution. The Linux probe-plane section,
however, intentionally has not selected its final shared-namespace isolation mechanism.
EXP-024 is reusable evidence, EXP-025 exposes generation-reuse risk, and EXP-026 remains the
narrow remediation candidate without final Debian 13 confirmation.

Selecting exact nft local rules now would therefore choose an implementation mechanism
before its existing evidence gate is satisfied.

**Disposition:** no guessed probe rule is added. The new architecture boundary can receive a
probe-owned contribution once the bounded probe-plane implementation unit selects and proves
its mechanism.

### F5 — publication/integration contributions remain source-owned

Publication and supported-integration traffic may require local exceptions, but their exact
selectors belong to the normalized Device publication intent or the accepted per-integration
contract. They must not be inferred from ambient sockets, interface names or historical
examples.

**Disposition:** architecture requires source-owned normalized contributions and stale-rule
removal when the source intent disappears.

## Component-model review

The split is consistent with the component model:

- policy derivation is a pure Calculator projection from accepted semantic intents plus
  current verified lower identities;
- the existing network-policy realization boundary remains Executor/Adapter machinery that
  observes, compares, converges and verifies supplied desired state;
- lower nft machinery does not choose product policy;
- no new Manager, Agent, event loop or persistent state is introduced.

## Simplification review

Not introduced:

- a universal host firewall;
- a second Device firewall compiler for INPUT/OUTPUT;
- a permanent exception registry independent of source intents;
- a durable local-rule journal;
- a new Adapter only for local exceptions;
- blanket conntrack/ICMP/listener allow defaults.

## Evidence / implementation gate

This unit is architecture-only. No executable rule shape is claimed by it.

A concrete local/system contribution may enter implementation only when its source function
can provide a complete normalized selector set and any mechanism-specific Linux evidence has
passed. Existing EXP-040 evidence remains sufficient only for the terminal-DROP base-chain
shape.

## Accumulated requirement-state inventory

### `decomp`

All six current links are resolved:

1. `VPNG-U001-R1.R2`: `VPNG-U005-R5 -> VPNG-U005-R5.R6`.
2. `VPNG-U001-R1.R3.C1.R1`: `VPNG-U004-R4.R6 -> VPNG-U004-R4.R6.R1`.
3. `VPNG-U001-R1.R3.C1.R1`: `VPNG-U001-R1.R3 -> VPNG-U001-R1.R3.R2`.
4. `VPNG-U001-R1.R3.C1.R1`: `VPNG-U001-R1.R2 -> VPNG-U001-R1.R2.R2`.
5. `VPNG-U001-R1.R3.C2.R1`: `VPNG-U004-R4.R6 -> VPNG-U004-R4.R6.R1`.
6. `VPNG-U004-R4.R6.R1.R6.R1`: `VPNG-U001-R1.R3 -> VPNG-U001-R1.R3.R2`.

Pending `decomp`: **none**.

### `unreal`

**none**

### `[rejected_closure]`

**none**

## Verdict

**PASS.** The architecture now has a bounded fail-closed local/system exception boundary
without inventing a permissive default. The next implementation-capable unit must be chosen
per source function; probe realization remains behind its already existing Linux evidence
gate rather than being guessed here.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005-R5` -> `VPNG-M001-R1.R1`
- `VPNG-U005-R5.R6` -> `VPNG-M001-R1.R1.R6`

The original IDs in the historical body are intentionally preserved.
