# NG3 2026-11-22 — E.003 continuous aggressive host-routing Manager implementation review

**Scope:** production implementation of accepted E.003 `AggressiveHostRoutingManager` and
the A.011 concurrency hardening required by its periodic escalation source.

**Baseline:** main `02e30a90eefd3d35747cf60c200b4817b868fef3`  
**Reviewed implementation head:** `a1472ab5c8644de5032b83aa0e0e59a72d9b2324`

## Verdict

**PASS — E.003 IS MATERIALIZED AND THE AGGRESSIVE HOST-ROUTING IMPLEMENTATION BLOCK IS
COMPLETE.**

This verdict does not expand Release-1 configuration scope. The accepted
`VPNG-U001-R5.R2.C1` constraint still permits Release 1 to expose only peaceful host-routing
automation.

## Findings and dispositions

### F1 — continuous ownership is a real Manager lifecycle

**Decision:** accepted.  
**Resolution:** fixed.

E.003 is no longer represented by a callable one-shot helper. Successful `activate` first
requires E.004 to confirm the complete aggressive postcondition and only then starts a
finite-cadence audit thread.

Every audit invokes E.004 again from fresh observations. An unexpected audit exception is
published as explicit `PROBLEM` state rather than silently terminating the semantic owner.

The production integration uses a 100 ms test cadence and proves that an RPDB violation
introduced after successful activation is detected without another lifecycle call.

### F2 — E.003 depends on E.004 as a component, not on its lower Drivers

**Decision:** accepted.  
**Resolution:** fixed during review.

The first implementation passed E.004 routing/guard Drivers through the E.003 constructor,
which leaked the child Enforcer's lower mechanism across the component boundary.

The reviewed baseline introduces an `AggressiveHostRoutingEnforcer` facade. E.003 now owns
only the E.004 component dependency and invokes `converge_active` /
`converge_inactive`; the Linux routing and nft guard Drivers remain encapsulated by E.004.

The refactored E.003/E.004 integration is green.

### F3 — unrecoverable authority loss composes with A.011/C.010 fail-closed

**Decision:** accepted.  
**Resolution:** fixed.

When E.004 cannot confirm active authority, E.003 requests A.011 protection using the stable
source identity `aggressive`.

Projection classification is conservative:

- local E.004 containment + confirmed A.011 protection -> `DEGRADED`;
- inability to confirm either required layer -> `PROBLEM`.

The live integration inserts an earlier foreign RPDB rule after initial success. The periodic
Manager detects it, retains E.004 escape containment, activates A.011/C.010 and confirms that
managed traffic cannot escape.

### F4 — recovery clears only the aggressive protective request

**Decision:** accepted.  
**Resolution:** fixed.

After E.004 recovery, E.003 asks A.011 to remove only source `aggressive`. It does not clear
another operator/automation request.

Whether the final source may release C.010 is supplied through the
`normal_release_confirmed` callback; E.003 does not acquire STACK normal-readiness
ownership.

If its source cannot be cleanly released, E.003 remains `DEGRADED` instead of reporting a
clean active/inactive state.

The live integration proves foreign-RPDB removal -> periodic E.004 recovery -> aggressive
source removal -> A.011 inactive -> managed traffic restored.

### F5 — deactivation serializes against the periodic audit and preserves E.004 ordering

**Decision:** accepted.  
**Resolution:** fixed.

E.003 signals the audit thread to stop and serializes all E.004 operations through one
operation lock. Even if thread join reaches its bounded wait, deactivation cannot race a
still-running E.004 audit because it must acquire the same operation lock.

It then requires E.004 confirmed inactive before clearing the aggressive A.011 request.

The live integration confirms final E.003 `INACTIVE` state and ordinary-path restoration.

### F6 — A.011 source ownership is safe under the new concurrent caller

**Decision:** accepted.  
**Resolution:** fixed.

Introducing a periodic E.003 caller makes concurrent A.011 request sources a production
reality. A.011 public state/mutation operations are now serialized with an `RLock`.

The reentrant lock is required because `request_inactive` composes
`reconcile_once`. Source-scoped semantics, leave precondition and safety-reclose behavior
are unchanged.

The existing C.010/A.011 live integration remains green on the reviewed head.

### F7 — Release-1 scope remains unchanged

**Decision:** accepted.

The Release-1 parser still accepts only `helper_routing_policy = "peaceful"`. E.003/E.004
are production capabilities behind an accepted architecture/API boundary, but
`VPNG-U001-R5.R2.C1` does not require them to be exposed by Release 1.

No new user-facing aggressive configuration syntax was invented by implementation.

### F8 — traceability is complete

**Decision:** accepted.  
**Resolution:** fixed.

`aggressive_host_routing_manager.py` traces exactly to E.003. The Residents occurrence and
E.003 spec are no longer marked `<partial>`; the spec contains its concrete
`Implementation` block.

E.004 remains separately materialized and traced by its own production units.

## Evidence

NG3 Python workflow `45054829691` on the final reviewed baseline:

- compile/unit and architecture traceability: PASS;
- EXP-074 / EXP-081 / EXP-084 / EXP-085: PASS;
- E.004 production integration: PASS;
- E.003 continuous Manager integration: PASS;
- EXP-078 / EXP-079 / EXP-080 peaceful regressions: PASS;
- C.010 production integration: PASS;
- A.011 Manager-core integration after concurrency hardening: PASS;
- existing C.005 forwarding-gate integration: PASS.

No unresolved finding remains in the aggressive implementation scope.
