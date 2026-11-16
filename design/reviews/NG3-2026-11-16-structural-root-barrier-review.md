# VPN-GATE NG3 — Structural Root Barrier Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-structural-barrier-40m`

## Trigger

The previous checkpoint named an nft barrier as the next lower safety unit.

Reviewing the actual recovery precondition exposes a circular dependency if nft is the only
root barrier:

```text
nft state is UNKNOWN/conflicted
        ->
need a trusted barrier before repairing nft
        ->
cannot prove safety using that same untrusted nft state
```

The checkpoint boundary therefore needs refinement before implementation.

## Requirement gate

The relevant accepted requirements are:

- `VPNG0004-R4.R2`: unconfirmed critical lower state is not treated as active;
- `VPNG0004-R4.R3.R2`: structural transitions may interrupt forwarding but may not open a
  state forbidden by old/new policy;
- `VPNG0004-R4.R4`: startup does not declare forwarding ready before a safe boundary is
  confirmed;
- `VPNG0004-R4.R5`: partial failure must re-establish authoritative state or remain
  restricted;
- `VPNG0004-R4.R6.R1`: managed network state belongs to an isolated managed domain.

No requirement promises uninterrupted forwarding during a structural change.

## Decision

Use the managed network namespace's own `net.ipv4.ip_forward` as the first-release root
structural barrier.

The barrier exists only after a fresh reread proves:

```text
ip_forward == 0
```

Command success alone is insufficient.

The sysctl is lower implementation state and is never exposed as user policy.

## Why global rather than per-Profile

A per-Profile deny barrier is possible later, but it adds policy/classification complexity
exactly where the first-release safety proof does not need it.

A global managed-netns forwarding barrier safely covers:

- overlapping Profile prefixes;
- path membership replacement;
- same-name/new-ifindex binding changes;
- RPDB reallocation;
- incomplete/unknown nft state;
- unresolved final Device envelope/NAT grammar.

The cost is a temporary interruption of all managed IPv4 forwarding during a structural
transition.

That cost is allowed by the current requirement tree. Priority-only reordering remains on
the already accepted non-disruptive fast path.

## Failure semantics

### Previously verified state

If the requested structural transition cannot establish and verify the barrier, abort the
transition and preserve the previously verified state. Do not begin allowing mutation.

### Startup / UNKNOWN recovery

If `ip_forward=0` cannot be established and verified, structural recovery cannot claim a
safe barrier. No new allowing state is materialized and startup/recovery fails hard with an
observable diagnostic.

The design does not pretend that software can guarantee packet safety after loss of the
privilege/control needed to enforce any lower barrier.

## nft role after this decision

nft remains the owner of final filtering/NAT policy.

It is rebuilt and verified **behind** the root forwarding barrier.

This removes the circular requirement that the nft namespace be trusted before it can be
repaired.

The unresolved human-facing traffic-envelope/publication grammar therefore does not block
this barrier unit. It may still gate the later complete nft desired-policy unit.

## Evidence gate

Before the barrier is executable, a privileged Linux experiment must prove on the current
target:

1. `net.ipv4.ip_forward` is independently controllable inside a disposable network
   namespace;
2. changing it in that namespace does not change the host namespace value;
3. `0` blocks IPv4 forwarding through that namespace;
4. `1` restores forwarding when routes/interfaces permit it;
5. reread observes the effective value used for the safety decision.

## Verdict

**PASS — checkpoint refined: root structural barrier is verified managed-netns
`ip_forward=0`; nft policy is repaired behind it.**
