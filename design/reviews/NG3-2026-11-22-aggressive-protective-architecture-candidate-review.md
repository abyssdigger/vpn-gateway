# NG3 2026-11-22 — aggressive/protective architecture-candidate review

**Scope:** review §2.11 pending closure candidate created from the accepted aggressive/protective
research block.

**Requirements:** `VPNG-U001-R5.R2*`, `VPNG-U004-R5*`  
**Evidence:** EXP-081, EXP-083, EXP-084; EXP-074 retained narrow evidence; EXP-082 retained
non-selected feasibility evidence.

## Verdict

**PASS — VALID PENDING CLOSURE CANDIDATE; NOT YET ACCEPTED AS CURRENT COMPONENT ARCHITECTURE.**

## Findings and dispositions

### F1 — candidate component roles match the component model

**Decision:** accepted.  
**Resolution:** fixed.

Continuous aggressive ownership is assigned to a future Manager rather than being hidden
inside peaceful E.002 lifecycle Machinery. Public protective state likewise has its own
Manager, while the Linux traffic gate is a bounded lower Enforcer.

This preserves the Engine/Machinery distinction and prevents either continuous responsibility
from being smuggled into an existing Direct component.

### F2 — the replacement aggressive candidate addresses the EXP-081 gap

**Decision:** accepted.  
**Resolution:** fixed as candidate.

The candidate no longer equates exact owned table/rule state with semantic authority.
Confirmed aggressive state requires:

- exact current managed-boundary generation;
- exact managed routing postcondition;
- exact independent escape-guard postcondition.

EXP-084 proves that the guard removes silent ordinary-path leakage during the observation /
repair window even when an earlier foreign RPDB rule wins route lookup.

The candidate additionally requires fresh observation of relevant competing policy and
finite-cadence resynchronization, so the Manager can distinguish healthy routing from
fail-closed degraded routing.

### F3 — activation/deactivation ordering is fail-closed

**Decision:** accepted.  
**Resolution:** fixed as candidate.

Aggressive activation installs/verifies the escape guard before routing is claimed active.
Deactivation removes routing capture before releasing the guard.

Therefore incomplete transition may deny traffic but cannot silently expose managed traffic to
an ordinary route solely because one half of the aggressive state changed first.

### F4 — protective lower ownership is simpler than the two-barrier prototype

**Decision:** accepted.  
**Resolution:** fixed as candidate.

EXP-083 supports one dedicated Private-network nft gate covering ordinary-boundary INPUT,
ordinary-boundary OUTPUT and all IP FORWARD classes. This is a better owner boundary than
composing public protective semantics from C.005 plus a host-side gate.

C.005 remains the structural forwarding barrier.

### F5 — safe leave has an explicit semantic precondition

**Decision:** accepted.  
**Resolution:** fixed as candidate.

Protective leave does not begin by deleting the gate. The Manager first obtains fresh
confirmation that the applicable normal desired/binding/policy state is ready to be exposed;
only then is the dedicated gate removed as its one owned operation.

A failed leave remains fail-closed and does not falsely report the mode inactive.

### F6 — pending status is correct

**Decision:** accepted.

All 11 affected nodes have an exact reference in authoritative architecture §2.11 and now use
`pending_closure`.

They are deliberately not `closed`: §2.11 is explicitly a candidate and has not yet been
promoted into current Residents/Component Annex specs. No fictitious implementation trace was
created.

Current normative inventory after the candidate transition:

- 189 `closed`;
- 11 `pending_closure`;
- 10 `postponed`;
- 3 `permanent`;
- 0 `open`;
- 0 `rejected_closure`.

## Next acceptance boundary

A later acceptance unit should decide whether §2.11 becomes current architecture. If accepted,
it should:

1. materialize the Manager/Enforcer roles in the appropriate Space Residents and Annex specs;
2. assign stable component IDs;
3. preserve the research-proven lower invariants;
4. close only those R/C whose architecture acceptance evidence is sufficient;
5. leave implementation work separately traceable rather than treating architecture closure
   as implementation completion.
