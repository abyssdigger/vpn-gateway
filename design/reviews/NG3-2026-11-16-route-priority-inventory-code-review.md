# VPN-GATE NG3 — Owned Route-Priority Inventory Code Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-primary-requirements-basis-40m`  
**Implementation commits reviewed:**  
- `dd19fbc28e530cae53da51042410801b5ae946b2`
- `f196bec14cf75cfd5b3eca041f840817b0a0d89d`
- `aab2bf678e709fb53e9a6f4a61ecec3048b3d09b`

## Scope

The unit implements authoritative normalization of one physical route-key domain into the
already accepted `RoutePrioritySnapshot` model.

Input is current iproute2 IPv4 route JSON plus:

- the selected destination;
- the internal owner protocol;
- current InterfaceIdentity inventory;
- exact expected non-metric path route identity:
  logical path, current endpoint, gateway and onlink semantics.

Rows outside the selected owner-protocol/destination domain are not part of this attempt.
Rows inside it must be representable and must match exactly one current logical path.

## Requirement / architecture gate

Relevant accepted nodes:

- `VPNG0004-R4.R2` — actual state must be confirmed, not assumed;
- `VPNG0004-R4.R3.R1` — every eligible path remains represented in pure-priority change;
- `VPNG0004-R4.R5` — partial failure requires authoritative re-observation;
- `VPNG0005-R5.R2` / `R5.R3` — recover from actual owned state;
- `VPNG0007-R7.R3` / `R7.R3.R1` — explicit adapter/executor contracts.

The preceding physical-domain design review resolved multi-destination aggregation by
scoping one snapshot to one independently observable route key.

## Accepted behavior

The parser:

- accepts numeric or numeric-string route protocol;
- normalizes `default` to `0.0.0.0/0`;
- requires owned-domain rows to be ordinary unicast single-path rows;
- resolves `dev` through the current InterfaceIdentity snapshot;
- requires exact current `(ifname, ifindex)` identity for each expected path;
- additionally matches expected gateway and onlink semantics;
- preserves multiple different metrics for one path, which is the expected partial
  make-before-break duplicate state;
- preserves absence as an empty metric set for the expected path rather than converting it
  to observation failure;
- rejects duplicate exact path/metric rows, ambiguous endpoint ownership and malformed JSON.

## Finding F1 — protocol-filtered iproute2 output can omit protocol

**Severity:** material observation correctness  
**Disposition:** accepted and fixed

Historical EXP-002/RC3 adapter evidence records that iproute2 output already filtered by
`proto N` may omit the protocol field.

The initial NG3 parser treated an omitted field as foreign protocol. In a filtered physical
query this could falsely project an actually present owned route as absent.

The parser now has an explicit `protocol_filtered` context:

- in an unfiltered inventory, omitted protocol remains foreign to the explicit NG3 owner
  protocol;
- in a query already filtered by that owner protocol, omission inherits the known query
  context;
- an explicitly contradictory protocol inside filtered output is rejected.

## Finding F2 — unrepresentable kernel route semantics must not be silently discarded

**Severity:** safety / authoritative-state fidelity  
**Disposition:** accepted and fixed

The initial parser rejected `nexthops` but did not explicitly reject all other route forms
that the current priority-domain model cannot represent.

It now fails selected owned-domain inventory on:

- `nexthops`;
- `nhid`;
- `multipath`;
- structured/cross-family `via`;
- flags other than the currently represented `onlink`.

This follows the existing project evidence rule: an authoritative snapshot must not simplify
unknown physical state into a state that would justify mutation.

## Finding F3 — RoutePriorityPathRoute trusted type annotations

**Severity:** local contract-hardening defect  
**Disposition:** accepted and fixed

The exported route-identity dataclass now validates its runtime contract:

- `path_id` is LogicalPathId;
- `endpoint` is InterfaceIdentity;
- `gateway` is IPv4Address or None;
- `onlink` is an actual bool.

This avoids the already-known Python pattern where annotations alone do not enforce
normalized invariants.

## Evidence

Final GitHub Actions evidence:

```text
workflow: NG3 Python
run:      43819415854
commit:   aab2bf678e709fb53e9a6f4a61ecec3048b3d09b
result:   success
tests:    126
summary:  Ran 126 tests ... OK
```

The workflow also runs package compilation.

## Residual boundary

The parser is pure normalization. Still required for the physical Executor:

- command construction/execution for one selected table/protocol/destination domain;
- exact add-new verification before delete-old;
- exact duplicate deletion;
- mutation failure re-observation using this inventory;
- final kernel postcondition verification;
- orchestration across all route-key domains of a Profile.

No route table number or owner-protocol constant is promoted to user configuration by this
unit.

## Final verdict

**PASS AFTER FIXES.**

The owned route-key snapshot is now sufficiently strict to serve as authoritative input to
the pure priority convergence/recovery algorithm without hiding same-name interface
replacement, filtered-protocol omission or unsupported kernel route structure.
