# NG3 2026-11-22 — aggressive candidate simplification review

**Scope:** review the accepted simplification of architecture candidate §2.11.1 and the
corresponding requirement wording.

**Baseline:** main snapshot `5730e896483b7cfe526d823208cb18f2b5b43742`  
**Requirements:** `VPNG-U001-R5.R2*`, wording of the newly introduced
`VPNG-U004-R5.R1..R4` descendants  
**Architecture:** `design/NG3/architecture-ng.md` §2.11.1

## Verdict

**PASS — THE SIMPLIFIED CANDIDATE IS PREFERRED.**

The earlier architecture-candidate review remains historical evidence for the research step.
This review supersedes only its three-component aggressive decomposition and the requirement
wording that encoded one Linux failure mechanism too directly.

## Findings and dispositions

### F1 — a separate AggressiveEscapeGuard component is not justified

**Decision:** accepted.  
**Resolution:** fixed.

The component model explicitly permits one Enforcer to use multiple lower mechanisms inside a
single bounded convergence contract when extracting each mechanism as a separate component
does not create a useful reusable/API boundary.

The escape guard:

- has no independent product client;
- has no independent product lifecycle;
- exists only as part of the aggressive-routing safety postcondition;
- must be ordered with routing activation/deactivation by the same bounded convergence unit.

Therefore the candidate now contains:

- `AggressiveHostRoutingManager` — continuous semantic owner;
- `AggressiveHostRoutingEnforcer` — bounded composite convergence/verification boundary.

The routing state and escape-guard state remain independently verifiable owned Artifacts of
the Enforcer. EXP-084 evidence is unchanged.

### F2 — the Manager must own the semantic postcondition, not Linux failure taxonomy

**Decision:** accepted.  
**Resolution:** fixed.

EXP-081 proves that observing only VPN-GATE-owned route/rule objects is insufficient. It does
not imply that the semantic Manager must enumerate and classify all competing RPDB policy.

The revised candidate requires the Manager to periodically re-confirm the effective aggressive
postcondition from fresh observation. The lower verification implementation may inspect RPDB,
perform effective lookups, or use another equivalent Linux mechanism.

This avoids introducing a generic ordinary-host routing-policy analyzer without a requirement
for one.

### F3 — safe operation ordering belongs to the Enforcer

**Decision:** accepted.  
**Resolution:** fixed.

The Manager selects active/inactive aggressive intent. The Enforcer owns the bounded safe
transition:

- activation: establish/verify escape protection before claiming managed routing active;
- deactivation: remove/verify routing capture before releasing escape protection.

This preserves the EXP-084 safety property while reducing Manager knowledge of lower
operations.

### F4 — requirement R2.R2 is now mechanism-independent

**Decision:** accepted.  
**Resolution:** fixed.

`VPNG-U001-R5.R2.R2` now states the observable obligation: while aggressive mode is active,
VPN-GATE periodically re-confirms the authoritative delivery guarantee and repairs a detected
violation from new observation when safe repair is possible.

The requirement no longer mandates explicit observation of "competing ordinary-host policy".
That mechanism remains implementation evidence/context, not product semantics.

### F5 — newly introduced requirement wording should prefer Russian

**Decision:** accepted.  
**Resolution:** fixed.

The current aggressive/protective requirement block was edited to remove avoidable English
phrases introduced during the previous CDC, including wording such as `fresh observation`,
`effective delivery`, `scope`, `egress`, `protective postcondition` and
`normal desired state`.

Established identifiers, requirement IDs, Profile/Device names and unavoidable technical
names remain unchanged. This is a targeted correction of the recently introduced wording, not
a repository-wide terminology migration.

### F6 — closure state does not change

**Decision:** accepted.

All affected aggressive/protective nodes remain `pending_closure`. The candidate is still
explicitly pending; this simplification does not by itself accept §2.11 into current
Residents/Annex component architecture.

## Result

The preferred aggressive candidate is now the minimal two-level architecture:

```text
AggressiveHostRoutingManager
    -> AggressiveHostRoutingEnforcer
         -> routing lower operations
         -> escape-protection lower operations
```

The safety property and Linux evidence are retained without promoting lower mechanism
separation into unnecessary component boundaries.
