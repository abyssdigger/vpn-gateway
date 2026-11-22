# NG3 2026-11-22 — aggressive/protective research review

**Scope:** review the re-entry, requirement refinement, Linux research and EXP-081..084
evidence for the aggressive host-routing helper and administrative protective mode.

**Research:** `design/NG3/research/NG3-2026-11-22-aggressive-protective-research.md`

## Verdict

**PASS — RESEARCH BLOCK ACCEPTED; NO ARCHITECTURE CLOSURE CLAIMED.**

## Findings and dispositions

### F1 — re-entry status is correct

**Decision:** accepted.  
**Resolution:** fixed.

The user explicitly re-entered both postponed capabilities by starting this CDC. Nodes without
a new accepted architecture candidate correctly moved to `open`. Existing Release-1
constraints remain `closed` and still state only that Release 1 is not obliged to provide
these capabilities.

### F2 — the previous aggressive authoritative-routing closure was invalid

**Decision:** accepted.  
**Resolution:** fixed.

EXP-081 demonstrates a concrete earlier-RPDB bypass while the old owner still reports its own
state exact. The old EXP-074 candidate therefore does not satisfy the full
`VPNG-U001-R5.R2.R1` Statement.

The change `closed -> rejected_closure` is correct. EXP-074 remains valid evidence for
precedence over routes inside `main`; its result is not rewritten.

### F3 — continuous aggressive observation must include effective competing policy

**Decision:** accepted.  
**Resolution:** fixed.

The refinement of `VPNG-U001-R5.R2.R2` is required by the parent guarantee rather than new
scope. Observing only helper-owned objects cannot detect the EXP-081 failure mode.

The revised requirement correctly requires fresh observation of both owned state and relevant
ordinary-host policy capable of invalidating the effective guarantee.

Linux netlink notifications may be useful wakeups, but the platform contract does not make
kernel-to-userspace notifications reliable. Finite-cadence fresh resynchronization therefore
remains necessary.

### F4 — aggressive local containment and global escalation are distinct obligations

**Decision:** accepted.  
**Resolution:** fixed.

The new `VPNG-U001-R5.R2.R3.R1` and `.R2` decomposition makes the existing parent promise
testable:

- helper-local fail-closed containment must protect the delegated scope independently from the
  routing decision under suspicion;
- broader protective mode remains a separate escalation target.

EXP-084 validates the key lower feasibility fact: an always-active nft guard can allow correct
managed egress, block an RPDB-induced ordinary escape immediately, and allow traffic again
after route recovery without removing the guard.

This does not yet close the requirements because long-lived Manager ownership/recovery remains
an architecture decision.

### F5 — protective-mode decomposition is complete enough for architecture work

**Decision:** accepted.  
**Resolution:** fixed.

The four new children of `VPNG-U004-R5` cover the distinct promises already contained in the
parent:

1. explicit enter/leave control and truthful completion result;
2. full traffic postcondition;
3. preservation of diagnosis/recovery state rather than teardown-as-containment;
4. continuous confirmation and safe release only after normal desired state is freshly
   validated.

No new public capability is introduced beyond the already accepted protective-mode parent.

### F6 — EXP-082 is valid but not the preferred lower design

**Decision:** accepted.  
**Resolution:** fixed as research disposition `not_selected`.

EXP-082 proves that a host-side boundary gate plus Private-network `ForwardingGate` can
compose to block the three original transit classes.

However, two independently owned barriers create avoidable release-order complexity because
neither one alone covers the complete protective postcondition.

The technical PASS remains valid; the mechanism is not selected as the current architecture
direction.

### F7 — EXP-083 is the selected protective lower candidate

**Decision:** accepted.  
**Resolution:** fixed as research disposition `selected`.

EXP-083 proves that one dedicated Private-network nft table covers boundary INPUT, boundary
OUTPUT and all IPv4 FORWARD traffic as one owned gate while leaving routes, interfaces and
`ip_forward` intact.

The nftables transaction model also allows the table to be loaded as a single ruleset
transaction. This substantially simplifies enter/leave safety compared with EXP-082.

The existing C.005 `ForwardingGate` should therefore retain its current structural-policy
role rather than being overloaded with public protective-mode semantics.

### F8 — component roles are sufficiently constrained, but not yet normative architecture

**Decision:** accepted.  
**Resolution:** deferred to the next architecture unit.

The research supports these component-role conclusions:

- aggressive continuous ownership belongs in an Engine/Manager in
  `VPN-GATE-managed host state`, separate from peaceful E.002 Machinery;
- its lower state is a composition of managed routing plus an independent escape guard;
- public protective state belongs to a separate STACK Manager;
- the protective traffic primitive belongs to a dedicated Private-network Enforcer.

These are accepted inputs for architecture design, not current component specs. Therefore the
re-entered requirements remain `open` and `VPNG-U001-R5.R2.R1` remains
`rejected_closure` until the authoritative architecture contains a replacement candidate.

## Evidence disposition summary

- EXP-074 — retain selected narrow lower evidence; remove the obsolete claim that it is exact
  closure for `VPNG-U001-R5.R2.R1`;
- EXP-081 — selected negative evidence rejecting the old closure candidate;
- EXP-082 — PASS / `not_selected` two-barrier protective composition;
- EXP-083 — PASS / `selected` lower protective-gate candidate;
- EXP-084 — PASS / `selected` aggressive escape-guard candidate.

## Next unit

Materialize the accepted research direction in the authoritative architecture:

1. define aggressive Manager + lower routing/guard contracts;
2. define protective Manager + Private-network protective gate contract;
3. define enter/leave/recovery interaction ordering;
4. only then move affected `open` / `rejected_closure` nodes to
   `pending_closure` or `closed` according to acceptance evidence.

No implementation is required merely to complete this research block.
