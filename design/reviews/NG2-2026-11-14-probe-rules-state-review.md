# NG2 — ProbeRulesStateCalculator initial review

**Date:** 2026-11-14  
**Type:** autonomous semantic review  
**Scope:** interpretation of desired/observed probe network rules after real LOCAL_PROCESS backend evidence

## Result

**PASS.**

The calculator is intentionally smaller than PayloadRulesStateCalculator.

## State model

```text
ProbeRulesState
    knowledge
        KNOWN | UNKNOWN
    convergence
        MATCHED | DIVERGED | UNKNOWN
    usability
        READY | INVALID | UNKNOWN
```

`usability` answers one question: may active probe success/failure be treated as
authoritative availability evidence under the currently observed network rules?

It does not describe remote endpoint reachability.

## Rules

- non-authoritative NetworkRules observation -> all axes UNKNOWN;
- authoritative semantic equality -> KNOWN + MATCHED + READY;
- authoritative semantic divergence -> KNOWN + DIVERGED + INVALID.

The divergence rule is deliberately symmetric:

- a restrictive difference can manufacture a false UNREACHABLE result;
- a widening/escape difference can manufacture a false REACHABLE result.

Therefore neither kind of divergence is valid availability evidence.

No predicate implication or SAFE/UNSAFE classifier is required for the initial probe
state model.

## Aggregate scope

The first state is owner-wide for the full desired probe rules snapshot.

A divergence in one physical plane temporarily invalidates evidence for the Manager's
current rules generation as a whole. This is conservative and avoids inventing a reverse
parser for synthetic routing-domain names.

If the executable AvailabilityProbeManager later demonstrates a requirement to preserve
independent evidence for unaffected planes during a partial projection, per-plane state can
be added as a separate review unit.

## Evidence boundary

This state model was intentionally deferred until a physical LOCAL_PROCESS backend existed.

That gate is now satisfied by:

- EXP-024 target PASS on Debian 13;
- production ProbeRules -> common Adapter -> Linux RPDB/nft apply PASS;
- fresh exact renew PASS;
- live bound/unbound/wrong-target dataplane assertions PASS;
- generation-drift detection PASS;
- shared-reconcile uid-guard preservation PASS.

The calculator itself is pure and performs no I/O.

## Final verdict

**PASS.**

The next mandatory unit is comparison with the already implemented PayloadRulesState.
