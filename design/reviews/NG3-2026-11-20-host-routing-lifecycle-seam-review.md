# NG3 review — host-routing lifecycle seam specialization

**Date:** 2026-11-20  
**Branch:** `ng3-design-cycle-20261120-host-routing-lifecycle-cleanup-30m`  
**Base:** snapshot 143 `067a01befa1a644bf7b48dd51e08bf71064364b0`  
**Reviewed implementation head:** `89249b7551ba4288e66ba2d7a61704dc5a0bac67`  
**Verdict:** **ACCEPTED — DEVELOPMENT BLOCK COMPLETE**

## Scope

Resolve the still-open controller lifecycle cleanup findings F2–F4 from
`NG3-2026-11-20-rudiment-cleanup-finish-review.md` after the scoped peaceful helper became
the active Release-1 host-routing implementation.

No requirement, configuration or user-visible routing behavior changes.

## Requirement / architecture gate

The existing behavior is traced to:

- `VPNG-U001-R2.R2` — peaceful helper is lifecycle-scoped;
- `VPNG-U005-R5.R1`, `VPNG-U005-R5.R4`, `VPNG-U005-R5.R5`, `VPNG-U005-R5.R6` —
  startup/stop ownership and cleanup;
- `VPNG-U007-R7.R2`, `VPNG-U007-R7.R3.R1`, `VPNG-U007-R7.R6.R1` — localized,
  explicit and traceable implementation responsibilities.

The controller must be able to converge and later clean an optional host-routing contribution
without knowing the Linux lowering behind it. A generic host-*boundary* extension point is not
required.

## F2 — stale generalized controller naming

**Disposition:** **fixed for the live controller seam**.

The active internal contract is now:

```text
HostRoutingContribution:
    converge()
    cleanup()
```

The former `controller_boundary_contribution.py`,
`ControllerBoundaryContribution`, builder, session field and live controller argument
terminology are removed/specialized accordingly.

The enum wire strings `boundary_build_failed` and `boundary_convergence_failed` are
deliberately retained for this mechanical cleanup so an internal naming correction does not
create gratuitous diagnostic-output incompatibility.

The postponed aggressive prototype names `SelectedHostBoundary*` and
`release1_host_boundary.py` are deliberately not renamed. They are explicitly detached
historical/executable evidence for the postponed aggressive child, not the current Release-1
controller owner. Renaming that evidence path would add churn without simplifying the live
contract.

## F3 — lifecycle architecture omitted the helper ordering

**Disposition:** **fixed**.

The normative architecture now records the implemented startup order:

```text
validate candidate
-> ensure managed domain
-> build current payload desired state
-> build/converge optional HostRoutingContribution
-> activate managed payload policy
-> READY
```

and the stop/interrupted-start cleanup order:

```text
ForwardingGate=DISABLED attempt
-> active HostRoutingContribution cleanup attempt
-> managed-domain teardown attempt
-> release lifetime lock only after required cleanup succeeds
```

Host-routing cleanup failure does not suppress managed-domain teardown. Conversely, failure of
a required cleanup area keeps the lifetime lock retained.

This ordering is lifecycle-only. It does not reintroduce periodic peaceful-helper ownership:
after successful startup, administrator host-route changes remain outside core runtime
reconciliation until another explicit helper lifecycle operation.

## F4 — stale test wording

**Disposition:** **fixed**.

The synthetic `host bootstrap remains` diagnostic and generalized boundary event names in
the current controller tests are replaced with host-routing terminology.

## Simplification review

No callback registry, plugin lifecycle framework, generic host-boundary contribution
abstraction or new component is introduced. The retained Protocol is the minimum explicit
contract needed by startup and stop to operate on an optional helper independently of its
lower Linux implementation.

The detached aggressive prototype continues to implement the same narrow contribution
contract only as executable postponed-capability evidence.

## Evidence

`NG3 Python` workflow run `44778254697` on exact code head
`89249b7551ba4288e66ba2d7a61704dc5a0bac67` completed **SUCCESS**.

Relevant evidence includes:

- compile + unit — PASS;
- installed Debian 13 alpha smoke — PASS;
- host-managed-routing suite including EXP-074/078/079/080 — PASS;
- OpenVPN onboarding/lifecycle regression — PASS;
- Debian-12 routed-veth portability — PASS;
- remaining NG3 Python jobs — PASS.

The change is therefore accepted as a semantic-preserving specialization/documentation fix.

## Requirement-state inventory

No requirement-state transition occurred.

- existing `decomp` links remain resolved;
- active `unreal`: none;
- active `broken`: none;
- active `rejected_closure`: none;
- existing postponed `pending_closure` nodes are unchanged.

## Final verdict

**ACCEPTED — DEVELOPMENT BLOCK COMPLETE.**


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005-R5.R1` -> `VPNG-M001-R1.R1.R1`
- `VPNG-U005-R5.R4` -> `VPNG-M001-R1.R1.R4`
- `VPNG-U005-R5.R5` -> `VPNG-M001-R1.R1.R5`
- `VPNG-U005-R5.R6` -> `VPNG-M001-R1.R1.R6`
- `VPNG-U007-R7.R2` -> `VPNG-D001-R1.R1.R2`
- `VPNG-U007-R7.R3.R1` -> `VPNG-D001-R1.R1.R3.R1`
- `VPNG-U007-R7.R6.R1` -> `VPNG-D001-R1.R1.R6.R1`

The original IDs in the historical body are intentionally preserved.
