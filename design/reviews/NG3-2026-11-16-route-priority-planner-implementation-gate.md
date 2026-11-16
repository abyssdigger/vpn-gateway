# VPN-GATE NG3 — Pure route-priority move planner implementation gate

**Cycle:** `ng3-design-cycle-20261116-post-closure-implementation-readiness-40m`  
**Review unit:** deterministic make-before-break planner for pure priority assignment changes

## Scope

Implement pure planning for the already-selected transition class:

```text
same eligible logical path set
current path -> metric assignment
desired path -> metric assignment
owned ordinary working metric set
    ->
immutable ordered RoutePriorityMove[]
```

One move means:

```text
add path at currently free metric
delete its old metric copy
```

Linux execution/verification remains outside this unit.

## Requirements/evidence

Primary:

- `VPNG-R4.R3.R1`;
- `VPNG-R3.R2`;
- `VPNG-R3.R3`;
- `VPNG-R3.R4`;
- `VPNG-R7.R1`.

Evidence: EXP-027.

## Preconditions

Pure-priority planner accepts only:

- identical current and desired path membership;
- one unique current metric per path;
- one unique desired metric per path;
- non-negative ordinary metrics;
- every current/desired metric inside the caller-owned working metric set.

Membership change belongs to structural fail-closed convergence and is rejected here.

## Working-space rule

At every move the destination metric must be currently free.

The planner may use any free metric in the caller-provided owned set.

No semantic/config `hole` object is stored.

All-live current assignment may use every desired metric; one extra currently unused owned
ordinary metric is sufficient to break a permutation cycle, matching EXP-027.

## Deterministic algorithm

1. If a currently free metric is a desired target for a misplaced path, move that path into
   the free metric.
2. Otherwise, when a permutation cycle remains, move the occupant of the lowest desired
   metric that is occupied by the wrong path into the lowest available scratch metric.
3. Continue until current assignment equals desired assignment.

Each simulated move updates which metric is free.

## Safety property

The plan contains only make-before-break move primitives.

No plan step intentionally removes an eligible path before its replacement route copy exists.

The planner never introduces a path outside the accepted membership set.

## Simplification

Not included:

- Linux route syntax;
- execution;
- final observation verification;
- transaction concurrency/coalescing;
- availability policy;
- metric allocation policy;
- structural membership change.

## Evidence plan

Rootless tests:

- simple direct move into already-free desired metric;
- two-path swap uses next unused scratch metric;
- three-path cycle;
- final simulated assignment equals desired;
- path membership mismatch rejected;
- duplicate current/desired metric rejected;
- metric outside owned set rejected;
- cycle without free scratch rejected;
- deterministic plan for same inputs.

## Verdict

**PASS — pure route-priority move planner may be implemented.**
