# EXP-044 — Device firewall jump insertion before Profile gate

## Purpose

Prove the smallest Linux/nftables mutation primitive needed to preserve the accepted
Device-firewall ordering:

```text
Device firewall jump
    BEFORE
Profile NEW/RETURN accept rules
```

Appending a Device jump after an existing Profile accept is not equivalent and may bypass
the Device restriction.

## Requirements

- `VPNG0001-R1.R2.R4.R6.R2`;
- `VPNG0001-R1.R2.R4.R6.R2.R1`;
- `VPNG0004-R4.R1`;
- `VPNG0004-R4.R2`;
- `VPNG0004-R4.R3.R2`.

## Procedure

A disposable ordinary -> managed -> VPN forwarding topology uses the accepted
`payload_forward policy drop` base chain.

1. Install a Profile NEW allow rule.
2. Create an owned Device child chain whose matching rule drops the same packet.
3. Append the Device jump with `add rule`; verify nft order is Profile then Device and the
   packet passes.
4. Remove that test jump.
5. Insert the same Device jump with `insert rule`; verify nft order is Device then Profile
   and the packet is denied.
6. Record exact JSON ordering and handles.

## Decision

PASS establishes `insert rule` as a sufficient minimal primitive for adding a Device jump
ahead of existing Profile rules without rebuilding the whole `payload_forward` chain.

PASS does not yet authorize production mutation. The guarded Executor must still prove
ownership, stale-object deletion, barrier preservation and fresh postcondition.
