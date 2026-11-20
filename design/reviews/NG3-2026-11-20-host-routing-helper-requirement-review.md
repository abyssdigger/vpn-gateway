# VPN-GATE NG3 — host-routing helper requirement review

> **Supersession note (2026-11-20):** this review captured the first accepted helper split
> while the new requirements were temporarily placed under `VPNG0001-R1`. A subsequent
> immediate-parent review moved the host-network non-interference/helper subtree under
> `VPNG0001-R2` and added the explicit Release-1 reload requirement. The old IDs below are
> retained as historical review facts, not current requirement links.

**Date:** 2026-11-20  
**Branch:** `ng3-design-cycle-20261120-rudiment-cleanup-finish-35m`  
**Reviewed range:** `be459411b2145aaa217f0df4be5c103b38968075..25723652abfc7645aad16a6c1997a3226ae43824`

## Verdict

**PASS for the requirement/evidence correction.**

The former direction-derived unconditional host-routing ownership has been replaced by three
separate product concepts with honest ancestry:

- simple lifecycle host-routing assistance;
- opt-in aggressive authoritative host-routing assistance;
- independent administrative payload containment.

No runtime behavior was changed in this review unit.

## Requirement-tree result

### Simple helper — `VPNG0001-R1.R4`

The requirement now promises lifecycle assistance only:

- install identifiable host-routing contributions at start / supported re-application;
- remove still-owned contributions at stop;
- after successful application, ordinary host routing returns to administrator control;
- no continuous drift-repair guarantee exists between lifecycle operations;
- administrator replacement of a helper-created route is not by itself a core VPN-GATE
  fail-closed condition.

The node remains `[pending_closure]` because the Release-1 Linux lowering has not yet been
selected.

This is intentional. The former authoritative dedicated-table implementation is too strong to
close this requirement.

### Aggressive helper — `VPNG0001-R1.R5`

The parent remains `[pending_closure]` and is constrained out of Release 1 by
`VPNG0001-R1.R5.C1`.

Its decomposition is now explicit:

- `VPNG0001-R1.R5.R1` — authoritative managed-destination routing;
- `VPNG0001-R1.R5.R2` — continuous observation/recovery of helper-owned drift;
- `VPNG0001-R1.R5.R3` — unrecoverable-alarm fail-closed escalation.

The first child is `[closed]`. The latter two remain `[pending_closure]`.

### Administrative payload containment — `VPNG0004-R4.R7`

This is an independent safety capability rather than an internal helper mechanism.

The semantic contract is:

- preserve managed runtime for diagnosis/recovery;
- block IP payload across the ordinary-side managed boundary in both directions;
- prevent IP transit between VPN paths;
- expose explicit administrative enter/leave operations;
- permit an external add-on such as the aggressive helper to invoke the same public control
  operation.

The node remains `[pending_closure]`; `VPNG0004-R4.R7.C1` explicitly removes it from the
Release-1 obligation.

## Lifecycle/recovery consistency

The first formulation of the simple helper exposed a real cross-tree conflict:
`VPNG0005-R5.R2/R2.R1` requires continuous recovery of state retained under authoritative
VPN-GATE ownership, while the agreed simple helper is deliberately non-authoritative between
lifecycle operations.

The correction is now explicit:

- `VPNG0005-R5.R2` applies only while a function retains state under authoritative
  VPN-GATE ownership;
- simple-helper route contributions return to administrator control after successful
  lifecycle application;
- `VPNG0005-R5.C1` therefore does not classify later administrator changes to those routes
  as out-of-band mutation of an authoritative VPN-GATE artifact.

The existing `[closed]` state of `VPNG0005-R5.R2`, `R5.R2.R1`, `R5.C1` and
`R5.C1.R1` remains valid after this narrowing. Their architecture references were
revalidated.

## EXP-074 closure

`EXP-074` now has one exact current job:

> acceptance evidence for `VPNG0001-R1.R5.R1`.

The experiment proves all differentiating parts of that child:

- managed destinations remain authoritative over competing non-local host `main` routes;
- a runtime-added more-specific competing route does not create an escape;
- local delivery remains local;
- traffic already emitted from STACK is not recaptured;
- unrelated host `main` state survives cleanup.

The requirement does not prescribe dedicated tables, RPDB priorities, `vpng0` naming or
other Linux lowering details.

Therefore the `[closed]` status of `VPNG0001-R1.R5.R1` is justified without reviving the
deleted direction-derived host-routing requirements.

## EXP-075 / EXP-076 correction

Profile SNAT remains a core managed-domain capability only up to the managed boundary.

- `EXP-075` retains the lower fact that an SNAT identity on the addressless routed boundary
  is reachable with the stack-service address as onlink next hop where the device-only /32
  is not.
- `EXP-076` remains core Profile-SNAT dataplane evidence for translation ordering,
  isolation, shared identity and return association inside STACK.
- Their tested host route is ancillary integration evidence. It may be supplied by a helper
  or by administrator routing and no longer implies core host-routing ownership.

## Administrative containment evidence

`EXP-030` is sufficient lower evidence that the current managed-domain
`net.ipv4.ip_forward=0` primitive blocks routed transit while preserving the namespace.

It is not sufficient closure for `VPNG0004-R4.R7` because the full future capability also
requires:

- ordinary-side boundary blocking in both directions;
- a public enter/leave control contract;
- composed acceptance proving the required postcondition.

No unproven closure claim was made.

## Current implementation finding

The Python alpha still actively wires the EXP-074-style authoritative host-routing owner and
periodically reconciles it; on drift it can close the internal ForwardingGate.

After this requirement correction that behavior is **not Release-1 simple-helper
conformance**. Current code/docstrings/deployment documentation now identify it as executable
prototype/evidence for the postponed aggressive child.

Before a future Release-1 snapshot can claim `VPNG0001-R1.R4` closure, the alpha/runtime path
must either:

- be replaced by a selected simple-helper lowering; or
- stop wiring the authoritative aggressive owner as the default host-routing contribution.

The exact lower realization is a design/implementation task, not an unresolved product
semantic question.

## Static trace review

All new `[pending_closure]` nodes have exact architecture references.

The closed nodes introduced or revalidated in this unit have exact architecture references:

- `VPNG0001-R1.R5.R1`;
- `VPNG0001-R1.R5.C1`;
- `VPNG0004-R4.R7.C1`;
- revalidated `VPNG0005-R5.R2` subtree and `VPNG0005-R5.C1` subtree.

Current normative architecture/registry text no longer claims that EXP-074 is unconditional
core or simple-helper host-routing acceptance evidence.

## Next requirement review

Return to the previously queued suspicious requirement:

`VPNG0004-R4.R1.R1`

Its safety intent may still be valid, but its current Purpose/Statement must be reviewed
against the corrected boundary because the wording still speaks in terms of Profile
destinations escaping through ambient/main routing.
