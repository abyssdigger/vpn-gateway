# VPN-GATE NG3 — structural route/RPDB mutation and activation-order review

**Date:** 2026-11-16  
**Cycle branch:** `ng3-design-cycle-20261116-local-publication-cont-35m`

## Scope

Review the lower Linux mutation primitives and activation ordering required before implementing
the complete cross-domain structural NetworkPolicyExecutor.

This unit covers:

- terminal payload blackhole guard add/delete;
- ordinary payload path-route add/delete;
- host-boundary payload RPDB dispatch add/delete;
- real activation/fallback behavior;
- exact cleanup isolation;
- authoritative RPDB `/32` JSON normalization;
- refinement of the structural transaction to exact-before-release ordering.

It does **not** yet implement the cross-domain Executor.

## Verdict

**PASS.**

EXP-048 opens the required route/RPDB mutation primitives. The architecture is refined so the
first-release Executor must reach exact payload routing + nft desired state while the global
ForwardingGate is still closed, before forwarding is released.

## Evidence

### EXP-029 baseline

EXP-029 already established the numeric JSON representation and add forms for:

- high payload tables;
- ordinary path routes;
- terminal blackhole route;
- payload host-boundary RPDB rule.

### EXP-048 mutation/activation evidence

Workflow `43944795308`: **SUCCESS**.

Observed markers:

```text
EXP048_TABLE_PREP_UNREACHABLE=1
EXP048_RPDB_ACTIVATES_PREPARED_TABLE=1
EXP048_TERMINAL_GUARD_BLOCKS_FALLBACK=1
EXP048_EXACT_RULE_DELETE_RESTORES_MAIN=1
EXP048_EXACT_CLEANUP_PRESERVES_UNRELATED=1
```

The disposable topology used two peers exposing the same destination but returning distinct
UDP payloads. Managed main routing selected ALT; the reserved payload table selected VPN.

Confirmed sequence:

1. baseline host traffic reached ALT;
2. adding only the terminal guard changed nothing because no RPDB rule reached the table;
3. adding the VPN path route also changed nothing;
4. adding payload RPDB dispatch switched real traffic to VPN;
5. deleting the path route while dispatch remained active caused failure through the
   blackhole guard rather than fallback to ALT;
6. restoring the path route restored VPN traffic;
7. deleting exact RPDB dispatch restored ALT/main routing;
8. exact route cleanup preserved unrelated route/RPDB state.

## Finding F1 — authoritative payload RPDB observer rejected a real /32 form

**Severity:** material lower-observation defect  
**Disposition:** fixed.

EXP-048 showed that current `ip -j -N -4 rule show` renders a host destination as:

```json
{"dst":"203.0.113.48", ...}
```

without `dstlen`.

The existing parser required `dstlen` for every payload rule and would therefore classify a
rule created by the accepted command as conflict.

The parser now accepts omitted `dstlen` **only** for a bare IPv4 host destination and
normalizes it as `/32`. Prefix text without `dstlen` remains rejected.

Unit coverage proves both the accepted host form and the rejected broader form.

## Finding F2 — the earlier stale-cleanup ordering conflicted with exact confirmation

**Severity:** structural safety/implementability ambiguity  
**Disposition:** architecture refined.

The earlier architecture sketch ended:

```text
verify desired routing+nft
 -> release ForwardingGate
 -> final verify
 -> cleanup stale state
```

But the accepted `PayloadRoutingComparison.confirmed` is exact and rejects stale payload
routes/rules. More importantly, a stale payload RPDB rule or stale route may still be
reachable and may represent behavior forbidden by the new policy.

Release 1 explicitly allows forwarding interruption during structural transition, so there
is no requirement benefit in releasing the barrier before exact state exists.

The accepted first-release ordering is now:

```text
observe
 -> close/reread ForwardingGate
 -> add/verify missing desired terminal guards
 -> delete/verify stale payload RPDB dispatch
 -> delete/verify stale payload routes
 -> add/verify desired ordinary routes
 -> converge/verify nft state
 -> add/verify missing desired RPDB dispatch
 -> verify exact routing+nft desired state
 -> enable/reread ForwardingGate
 -> fresh final exact verify
 -> confirmed
```

No delayed stale cleanup is part of the first-release Executor.

## Finding F3 — terminal guard must precede route membership rewrite

A desired Profile table can otherwise temporarily have no terminal route, and a later table
lookup could fall through to a lower RPDB rule/main routing.

**Disposition:** terminal guards are installed and verified before stale route retirement or
ordinary route preparation.

## Finding F4 — RPDB is activation, not preparation

EXP-048 gives direct live evidence: route-table preparation alone did not affect traffic;
adding the RPDB rule immediately switched real traffic.

**Disposition:** missing desired RPDB rules may be installed only after guarded routes and the
required nft state are exact.

## Finding F5 — exact delete primitives are sufficiently narrow

Exact path-route deletion preserved the guard. Exact payload-rule deletion restored ambient
routing without deleting unrelated state. Final managed cleanup preserved an unrelated table
and unrelated RPDB rule.

**Disposition:** these argv-based operations are acceptable lower Driver primitives, subject
to fresh whole-scope observation and postcondition verification in the forthcoming Executor.

## Component-model impact

No new semantic component is required by this unit.

The next implementation should use:

- pure structural step planning as Calculator behavior;
- one guarded NetworkPolicyExecutor for orchestration;
- a narrow Linux route/RPDB Driver using EXP-048-backed commands;
- the existing composite nft Calculator/Driver contracts;
- the existing ForwardingGate Driver.

Do not create a parallel routing Manager or standalone RPDB activator.

## Simplification review

Not introduced:

- standalone RPDB reconciliation outside the structural barrier;
- rollback journal;
- persistent route/rule handle database;
- shell-script transaction engine;
- delayed stale cleanup optimization;
- a second nft policy model;
- user-visible routing table/priority configuration.

## Accumulated requirement-state inventory

### `decomp`

All six accumulated links remain **resolved**. Pending: **none**.

### `unreal`

**none**

### `[rejected_closure]`

**none**

## Human decisions required

**none**

The ordering refinement is an implementation-safety choice within already accepted
requirements and the explicit Release-1 allowance for structural-transition interruption.

## Next logical block

Implement the complete guarded cross-domain structural convergence boundary:

1. fresh link-bracketed route/RPDB+nft observation;
2. pure step planner implementing the exact-before-release phases;
3. EXP-048-backed Linux route/RPDB Driver;
4. reuse existing composite nft convergence primitives;
5. ForwardingGate remains closed through every mixed state;
6. enable forwarding only after exact routing+nft confirmation;
7. final fresh exact verification after enable;
8. privileged coexistence/recovery integration.

## Conclusion

**PASS.** Structural route/RPDB write primitives and activation ordering are closed. The
remaining work is Executor implementation, not lower-mechanism discovery.
