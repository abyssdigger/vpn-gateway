# NG3 D.002 recoverable-group endpoint review — 2026-11-25

**Review unit:** D.002 endpoint-bearing recoverable-group candidate state machine  
**Reviewed implementation head:** `7e9cc424ef2d23f00eb49465eb3a96ee4ea03ae6`  
**Requirement:** `VPNG-U001-R1.R3.R8.R3.R1`  
**Architecture:** C.001, C.008, D.002, D.003  
**Evidence:** `EV-00180`

## Verdict

**PASS — D.002 now accepts an endpoint-bearing group only after the candidate peer and the
group endpoint are both freshly confirmed in the required order.**

The unit closes the D.002 component-local contribution to R8.R3.R1. It does not claim that
alpha/runtime composition of the shared probe plane is complete.

## Findings and dispositions

### F1 — endpoint evidence must follow exact candidate ownership

**Decision:** accepted.

For every candidate, D.002 first requires fresh technical peer `REPLY`, then converges one
complete D.003 `AllowedIPs` state and requires its fresh exact postcondition, and only then
invokes the group endpoint port. No group `REPLY` obtained before that D.003 confirmation can
accept the candidate.

### F2 — confirmed group failure has group-local scope

**Decision:** accepted.

A group endpoint `NO_REPLY` rejects only that candidate for that group in the current
reconciliation. The next D.003 desired state changes only the affected group ownership while
preserving sibling group owners.

### F3 — execution uncertainty is not remote unavailability

**Decision:** accepted.

A group endpoint `LOCAL_ERROR`, exception or invalid port result becomes an explicit D.002
problem and clears current generation evidence. It does not cause automatic selection of a
different peer.

### F4 — candidate retry is bounded

**Decision:** accepted.

Each confirmed group-level `NO_REPLY` adds one previously eligible peer to the group's
in-memory rejected set for the current reconciliation. Selection never returns a rejected peer,
so the number of retry transfers is bounded by the finite configured membership count. The set
is not persisted as historical policy.

### F5 — final evidence corresponds to the final ownership map

**Decision:** accepted.

Any owner-map change breaks the current verification pass and returns to full D.003
convergence. Endpoint checks therefore restart against the new exact state; successful
publication occurs only after a pass with no ownership changes and positive checks for every
endpoint-bearing owned group.

### F6 — reserve semantics survive endpoint validation

**Decision:** accepted.

A current reserve owner may still be challenged by a recovered preferred ordinary peer, but
technical `REPLY` alone does not complete failback. If the preferred candidate fails the
group endpoint, the candidate is rejected and the still-technically-valid reserve peer can be
restored through a new exact D.003 state and fresh endpoint check.

### F7 — endpoint policy participates in generation identity

**Decision:** accepted.

The normalized availability mechanism/target is part of the D.002 generation facts. Changing
the endpoint policy therefore invalidates prior D.002 realization even when peer ownership,
`LogicalPathId`, interface name and ifindex remain unchanged.

## Evidence

- implementation: `c7491ed6554bc0e7441d7ea3523f7dea31f9985f`;
- reserve/generation regression coverage:
  `7e9cc424ef2d23f00eb49465eb3a96ee4ea03ae6`;
- final run `45576973824`, unit `139077314434`: **PASS**;
- actual-main lineage run `45576973837`: **PASS**.

## Remaining boundary

The remaining generalized R8 work is outside this state-machine unit: combine A.007, peer and
group probe demand into the alpha/runtime C.001 convergence union; provide periodic/explicit
D.002 reconciliation and status publication; invalidate dependent A.007 availability evidence
after D.002 generation changes; and obtain focused D.003 kernel acceptance for simultaneous
split-group ownership.
