# NG3 2026-11-22 — A.011 protective-mode Manager core implementation review

**Scope:** source-scoped A.011 Manager core composed with production C.010.

**Architecture baseline:** main `0b681cb41913c71245036279f9a95099ac167e32`  
**Implementation head:** `662f701d6fe9d8253ff3a215681b9fc665494a83`

## Verdict

**PASS — THE A.011 MANAGER CORE IS MATERIALIZED; A.011 REMAINS `<partial>`.**

The remaining partial scope is periodic runtime scheduling and supported operator/control
wiring. The current block does not pretend that a callable core is already an always-running
public mode.

## Findings and dispositions

### F1 — request ownership is source-scoped

**Decision:** accepted.  
**Resolution:** fixed.

The Manager stores an explicit request-source set. Clearing one source does not clear another;
while any source remains, C.010 is freshly reconfirmed active.

The live integration exercised independent `operator` and `aggressive` requests and proved
that removing the operator request left the aggressive request and gate active.

### F2 — final-source leave is guarded by normal-state confirmation

**Decision:** accepted.  
**Resolution:** fixed.

Removing the final request creates a pending release rather than immediately opening traffic.
Without `normal_release_confirmed`, the Manager reconfirms C.010 ENABLED and reports
`LEAVE_BLOCKED`.

The live integration confirms that the table remains exact while leave is blocked.

### F3 — successful leave requires C.010 confirmation

**Decision:** accepted.  
**Resolution:** fixed.

After the normal release precondition is supplied, the Manager converges C.010 DISABLED and
reports inactive only after the bounded Enforcer confirms absence.

The production live integration passed the complete multi-source -> blocked leave -> confirmed
release sequence.

### F4 — uncertain/failed leave attempts safety re-containment

**Decision:** accepted.  
**Resolution:** fixed.

If C.010 disable does not confirm, the Manager immediately attempts to re-establish ENABLED:

- confirmed re-containment -> `LEAVE_FAILED_RECONTAINED`, mode remains active;
- inability to confirm re-containment -> `SAFETY_RECLOSE_FAILED` and explicit problem state.

This follows the established NG3 structural-transition pattern: mutation command success is
not confirmation, and failed release is followed by an explicit safety re-close attempt.

### F5 — continuous/public wiring remains an explicit implementation gap

**Decision:** accepted.  
**Resolution:** deferred.

A.011 stays `<partial>` until:

1. a runtime owner invokes `reconcile_once` at a finite cadence while protection or release
   is pending;
2. an authorized supported operator/control surface maps stable request-source identities into
   the Manager;
3. process restart semantics for outstanding protective requests are explicitly selected.

No fictitious runtime trace is added for these missing parts.

## Evidence

NG3 Python workflow for the implementation head:

- compile/unit: PASS;
- `linux-forwarding-barrier`: PASS;
- EXP-083: PASS;
- C.010 production integration: PASS;
- A.011 Manager-core live integration: PASS;
- existing C.005 integration: PASS.
