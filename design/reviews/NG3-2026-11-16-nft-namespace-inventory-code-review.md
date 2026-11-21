# VPN-GATE NG3 — nft Namespace Inventory Code Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-structural-barrier-40m`  
**Reviewed commit:** `6e1d3f28779e612c51ab30116d02b7bb843883eb`  
**Live evidence:** EXP-031

## Scope

This unit implements the read-only first layer of nft ownership observation.

Input:

```text
nft -j list ruleset
```

Output:

```text
ABSENT
OWNED
CONFLICT
+
canonical contained-object snapshot
```

It performs no nft mutation and does not authorize cleanup.

## Requirement / ownership gate

PASS.

The observer implements the accepted distinction between:

- reserved table identity;
- exact versioned owner marker;
- the still-unclassified contents of that table.

This directly supports `VPNG0004-R4.R2`, `VPNG0004-R4.R5`,
`VPNG0004-R4.R6.R1.R1` and the lower-detail containment rule
`VPNG0007-R7.R3.R2`.

## Table-level states

### ABSENT

No `table ip vpn_gate` declaration and no object referring to that reserved table exists.

ABSENT is a valid observed state, not an error.

### OWNED

Exactly one reserved table declaration exists and its exact comment is:

```text
vpn-gate:ng3:owner-v1
```

The nft handle is deliberately ignored as ownership identity.

### CONFLICT

The reserved table exists but:

- the marker is missing/different; or
- the table declaration carries unsupported semantic fields.

The observer does not silently adopt that table.

## Contained objects

PASS.

Every nft JSON row whose payload names:

```text
family = ip
table  = vpn_gate
```

is preserved as a canonical JSON record regardless of its object kind.

This is important: a new/unknown nft object type inside the owned table does not disappear
merely because the first-layer observer does not yet understand it.

The next object-shape layer must classify every captured record before mutation/cleanup.

## Failure semantics

PASS.

Malformed JSON, malformed row structure, duplicate reserved table declarations or impossible
"object without table declaration" state raise `NftNamespaceInventoryError`.

These are observation failures, not `ABSENT`.

Foreign tables/families are ignored because they are outside the reserved nft identity.

## Linux backend

PASS.

`LinuxNftNamespaceBackend` uses one full-ruleset command:

```text
ip netns exec <managed-ns> nft -j list ruleset
```

It does not infer absence from a failed `list table` command.

## Evidence

GitHub Actions run:

```text
run:      43838417799
commit:   6e1d3f28779e612c51ab30116d02b7bb843883eb
unit:     238 tests, OK
EXP-031 owner marker: PASS
NG3 nft namespace inventory Linux integration: PASS
EXP-030 forwarding barrier: PASS
linux-route-priority: PASS
EXP-028 platform: PASS
EXP-029 structural routing inventory: PASS
overall:  success
```

## Residual boundary

`OWNED` is intentionally not enough for mutation.

The next bounded layer may define and verify the invariant nft scaffold that is independent
of final user envelope/NAT grammar:

- one payload FORWARD base chain with terminal fail-closed policy;
- one payload postrouting NAT base chain, initially empty;
- exact lower owner/version markers for those chains.

Concrete allow/drop envelope rules and masquerade rules remain gated by normalized
DevicePolicyIntent semantics and the unresolved final human-facing grammar.

## Final verdict

**PASS.**


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG0007-R7.R3.R2` -> `VPNG9001-R1.R1.R3.R2`

The original IDs in the historical body are intentionally preserved.
