# NG3 requirement/component gate — EXP-040 managed INPUT/OUTPUT DROP scaffold

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-config-format-35m`

## Review unit

Linux/nft evidence for the two managed-domain local filter base chains required to complete
the accepted `INPUT/FORWARD/OUTPUT = DROP/DROP/DROP` stack baseline.

This unit proves only fail-closed chain shape and terminal behavior. It does not design the
later explicit loopback/control/probe/publication/integration allow contributions.

## Requirements

**Implements:**

- `VPNG-U004-R4.R6.R1.R5`;
- `VPNG-U004-R4.R6.R1.R5.R1`;
- `VPNG-U004-R4.R4`;
- `VPNG-U004-R4.R2`.

The full ancestry remains closed. No new product semantic is selected here.

## Candidate lower shape

Inside owned `table ip vpn_gate`:

```text
chain stack_input
    type filter
    hook input
    priority 0
    policy drop
    comment "vpn-gate:ng3:stack-input-v1"

chain stack_output
    type filter
    hook output
    priority 0
    policy drop
    comment "vpn-gate:ng3:stack-output-v1"
```

Names/comments are lower owner-schema choices, not user configuration.

## Hypotheses

EXP-040 must prove:

1. exact nft JSON metadata for both chains;
2. empty `stack_input policy drop` blocks IPv4 local delivery into the namespace;
3. empty `stack_output policy drop` blocks IPv4 locally generated traffic out of the
   namespace;
4. foreign unconditional-accept base chains at earlier and later priorities cannot bypass
   either VPN-GATE drop chain;
5. adding an explicit ICMP allow contribution to both owned chains permits the tested local
   ICMP traffic, proving the chains are usable owner boundaries rather than a permanent
   all-local blackout.

## Components / interactions

- disposable privileged Linux network namespace: external environment;
- nftables: lower packet-filter mechanism;
- existing NetworkPolicyAdapter/lower nft boundary: future consumer of the proven shape.

No new Manager, Agent, retained state or user-facing configuration is introduced.

## Simplification

The experiment does not:

- select final system-exception policy;
- test publication/probe-specific local flows;
- implement an observer/mutator;
- change the existing payload `FORWARD`/postrouting contracts;
- claim Debian-target confirmation.

## Gate

Physical production use of `stack_input` / `stack_output` exact owner shapes remains
gated until EXP-040 passes and its result is incorporated into architecture.

## Requirement-state inventory

### `decomp`

Six current links; all resolved. No pending decomp.

### `unreal`

none

### `[rejected_closure]`

none
