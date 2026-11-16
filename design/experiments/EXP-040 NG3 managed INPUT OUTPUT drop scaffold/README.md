# EXP-040 — managed INPUT/OUTPUT DROP scaffold

## Purpose

Prove the exact Linux/nftables lower shape and terminal behavior for the managed-domain
`INPUT=DROP` and `OUTPUT=DROP` base chains required by NG3.

This experiment is limited to the invariant fail-closed scaffold. System/local exceptions
remain a later policy unit.

## Requirements

- `VPNG0004-R4.R6.R1.R5`;
- `VPNG0004-R4.R6.R1.R5.R1`;
- `VPNG0004-R4.R4`;
- `VPNG0004-R4.R2`.

## Candidate chains

```text
stack_input:
    family ip
    type filter
    hook input
    priority 0
    policy drop
    comment "vpn-gate:ng3:stack-input-v1"

stack_output:
    family ip
    type filter
    hook output
    priority 0
    policy drop
    comment "vpn-gate:ng3:stack-output-v1"
```

## Procedure

A disposable network namespace is connected to the runner through a veth pair.

Inside the namespace:

1. create marked `table ip vpn_gate`;
2. create `stack_input` and `stack_output` with the exact candidate metadata;
3. create foreign unconditional-accept base chains at priorities before and after the owned
   chains for both hooks;
4. verify host -> namespace ICMP fails with empty `stack_input`;
5. verify namespace -> host ICMP fails with empty `stack_output`;
6. inspect nft JSON for exact owned-chain metadata;
7. add explicit ICMP accept rules to both owned chains;
8. verify ICMP succeeds in both directions.

## Decision

PASS establishes that the two exact base-chain shapes are valid fail-closed owner boundaries
and that foreign ACCEPT base chains do not bypass their DROP policy.

PASS does not define the later local/system allow policy.
