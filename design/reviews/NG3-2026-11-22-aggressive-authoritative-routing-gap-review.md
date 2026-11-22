# NG3 2026-11-22 — aggressive authoritative-routing closure gap review

**Scope:** re-evaluate `VPNG-U001-R5.R2.R1` after EXP-081 tested host policy outside
the EXP-074 evidence envelope.

**Evidence:**

- EXP-074 — authoritative managed table defeats competing routes in host table `main`;
- EXP-081 — a foreign earlier RPDB rule bypasses the current VPN-GATE dispatch while the
  current owner still reports its own state exact.

## Finding F1 — the current closure claim is broader than its evidence

**Decision:** accepted.  
**Resolution:** fixed by reopening the requirement as a rejected closure candidate.

`VPNG-U001-R5.R2.R1` says that competing ordinary host routing policy must not override
delivery of an aggressively managed destination to VPN-GATE.

The accepted EXP-074 realization places VPN-GATE dispatch before the default `main` lookup,
which correctly defeats more-specific routes inside `main`. But Linux RPDB is itself an
ordered policy surface. EXP-081 demonstrates that a foreign rule with earlier priority can
select `main` before the VPN-GATE dispatch and therefore bypass the managed boundary.

This is not merely missing evidence for an otherwise complete candidate: the current lower
postcondition also fails to observe that foreign policy as a conflict. The candidate is
therefore insufficient for the full current Statement.

## Status decision

Change:

- `VPNG-U001-R5.R2.R1`: `closed -> rejected_closure`.

The requirement Statement is unchanged. The EXP-074 result is not invalidated; its valid
scope is narrowed to evidence for one useful mechanism property.

The node should leave the current closed-requirement architecture coverage index until a new
candidate covers the complete applicable host-policy surface and receives acceptance.

## Consequence for adjacent research

The finding strengthens the need for an explicit aggressive-host Manager boundary:

- continuous authority cannot be defined only as exact ownership of VPN-GATE's own table/rules;
- observation must include policy capable of preceding or bypassing the delegated scope;
- event-driven routing notifications may be used as wakeups, but not as the only truth source;
- repair/escalation must start from fresh authoritative observation;
- if authority cannot be re-established, helper-local fail-closed containment must not depend
  on the routing state that is already untrusted.

## Verdict

**PASS — CURRENT CLOSURE REJECTED, REQUIREMENT SEMANTICS RETAINED.**
