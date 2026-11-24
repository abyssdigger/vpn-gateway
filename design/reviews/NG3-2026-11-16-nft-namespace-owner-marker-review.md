# VPN-GATE NG3 — nft Namespace Ownership Marker Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-structural-barrier-40m`

## Trigger

With the root forwarding barrier closed independently by managed-netns
`ip_forward=0`, the structural Executor can inspect/repair nft state without first trusting
that nft state.

The next question is ownership: a fixed table name alone does not prove that a pre-existing
table is safe to adopt or delete.

## Requirement gate

Relevant accepted requirements:

- `VPNG-U004-R4.R2` — unknown critical lower state is not accepted as active;
- `VPNG-U004-R4.R5` — recovery begins from authoritative actual state;
- `VPNG-U004-R4.R6.R1.R1` — product mutable network state has explicit ownership boundaries;
- `VPNG-U007-R7.R3.R2` — Linux implementation identity remains below product policy.

## Decision

Reserve:

```text
table ip vpn_gate
comment "vpn-gate:ng3:owner-v1"
```

The exact comment is a lower schema-versioned ownership marker.

Observation states are:

- `ABSENT`;
- `OWNED` with exact marker;
- `CONFLICT` for same-name table without the exact marker.

## Why table comment

The marker belongs to the resource whose ownership is being asserted and does not consume
user-facing IDs or Profile/Device names.

A versioned marker also prevents a future incompatible nft layout from being silently
adopted as if it were the same lower schema.

## Important limit

The marker does **not** authorize:

```text
delete table ip vpn_gate
```

by itself.

A foreign/unknown chain or rule may have been inserted into a previously owned table.
Therefore contained objects must still be strictly inventoried before mutation or cleanup.

The table marker proves only the first layer:

```text
this table was created under the NG3 owner namespace
```

not:

```text
every object currently inside it is safe to delete
```

## Observation command

Use full ruleset JSON:

```text
nft -j list ruleset
```

Do not infer `ABSENT` from an arbitrary non-zero `nft list table` result, because command
failure, permission failure and table absence are not the same semantic state.

## Evidence gate

EXP-031 must prove on the current nftables target:

1. table comments are accepted for `table ip vpn_gate`;
2. the exact comment round-trips through `nft -j list ruleset`;
3. an unmarked same-name table is observably distinct;
4. foreign tables can coexist and remain distinguishable;
5. deleting the experiment namespace removes all test state without host nft mutation.

## Verdict

**PASS — versioned table marker selected; live representation remains evidence-gated.**


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U007-R7.R3.R2` -> `VPNG-D001-R1.R1.R3.R2`

The original IDs in the historical body are intentionally preserved.
