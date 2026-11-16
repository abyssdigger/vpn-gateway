# VPN-GATE NG3 — Primary-Requirement Migration / CD Cycle Integrity Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-primary-requirements-basis-40m`  
**Cycle start:** `56bb09107cb591e9ff8d086c2642c14bc70bb22b`

## Scope

This review checks the cycle as a coherent chain after:

1. general requirement-methodology migration;
2. NG3 primary-root migration and architecture/config reference migration;
3. full requirement-rationale review;
4. CD process synchronization;
5. immediate-GitHub project convention update;
6. bounded implementation/review of the pure-priority NetworkPolicyExecutor path.

## Requirement-model integrity

Current NG3 mechanical result:

```text
normative nodes:                     128
unique normative IDs:                128
primary project roots:                 7
Constraints:                           6
primary roots without Basis:           0
Constraints whose Reason is "Чтобы":   0
legacy VPNG-R... IDs in requirements:  0
```

The primary roots use externally sourced Basis records; derived nodes retain causal Purpose;
Constraints retain actual Reason.

The R3 actor ambiguity is removed: the user is explicitly the actor that allows multiple VPN
paths and establishes their configured order.

## Trace integrity

Current exact-ID checks:

```text
requirements absent from architecture: 0
architecture refs absent from requirements: 0
config refs absent from requirements: 0
legacy VPNG-R... in architecture: 0
legacy VPNG-R... in config-model:  0
```

Therefore the ID migration did not create broken current normative traceability.

## Process integrity

Verified current process artifacts:

- `design/requirements-model.md` contains the primary `Basis` model and explicit actor gate;
- `CONTINUOUS-DEVELOPMENT.md` distinguishes primary Basis, derived Purpose and Constraint
  Reason at the requirement gate;
- `CONTINUOUS-DEVELOPMENT.md` already requires every cycle commit to be present on GitHub
  immediately;
- `PROJECT-CONVENTIONS.md` now independently states the same rule for all project work:
  requirements, architecture, code, tests, evidence, review and process docs;
- `PROJECT-CONVENTIONS.md` now correctly identifies NG3 as the current normative
  generation.

No local-only commit chain is accepted as project state.

## CD implementation progression reviewed

The priority-only implementation path now has explicit, reviewed layers:

```text
clean-state planner
  -> partial-state convergence
  -> one-attempt Executor orchestration
  -> owned route-key inventory
  -> physical iproute2 route-key backend
  -> Profile multi-domain coordinator
```

Key safety properties preserved across the layers:

- route membership is unchanged by priority-only adaptation;
- make-before-break is represented as one semantic move, not replayable raw add/delete;
- partial failure discards stale plan tails;
- every later attempt starts from fresh authoritative state;
- physical route observation is bound to stable current `(ifname, ifindex)`;
- whole route-key state is checked around every physical mutation;
- Profile completion requires a second fresh final verification across all destination
  domains.

## Evidence

Latest accepted code/evidence baseline before this integrity review:

`e885188cebfc92cd048cee75eaea1d833b171146`

GitHub Actions run `43820419873`:

```text
unit: 144 tests, OK
linux-route-priority: PASS
overall: success
```

The Linux job uses a disposable network namespace and real iproute2 mutation.

## Findings

### F1 — project conventions still described NG2 as current

**Disposition:** accepted and fixed in `e4612aee80171f57ed6b2166faa6951c883b10f6`.

This was a process-document drift defect. It did not change the NG3 normative tree or code,
but leaving it would create an incorrect source-of-truth instruction.

No other material integrity defect was found.

## Residual implementation scope

The current pure-priority slice is not the complete Release 1 daemon.

Important next boundaries remain:

- generation/allocation of complete physical route-domain requests from normalized policy;
- guarded structural-policy convergence;
- RPDB/nft and Device NAT/envelope/publication materialization;
- availability probe execution;
- lifecycle/runtime assembly.

## Final verdict

**PASS AFTER PROCESS-DOC FIX.**

The methodology migration, NG3 requirement migration, rationale review, traceability,
process rules and implemented pure-priority CD slice are mutually consistent on the current
cycle branch.
