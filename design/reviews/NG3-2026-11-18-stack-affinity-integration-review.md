# NG3 2026-11-18 — stack return-affinity production integration — cycle review

> **Historical requirement trace note (2026-11-20):** this review records the requirement
> tree that was current when the review was performed. `VPNG-U002-R2.R3.R1.R1`
> was later removed from the current requirement tree when the old direction-derived host-routing
> ownership decomposition was rejected. References below to that ID are historical facts about
> what this review evaluated, not current requirement links; the review conclusions are not rewritten retroactively.

## Verdict

**PASS for the bounded cycle scope.**

The Release-1 managed-stack established-flow return-affinity owner is no longer a lower-only
prototype. This cycle adds authoritative ownership observation, guarded convergence, production
activation ordering and alpha-runtime reconciliation while preserving the accepted Release-1
single-path inbound/bidirectional product boundary.

No multi-path functionality was activated by this cycle.

## Accepted boundary entering the cycle

The cycle started from these already accepted facts:

- `VPNG-U002-R2.R6` requires related replies to return through the VPN channel that accepted
  the original managed inbound traffic;
- `VPNG-U007-R7.R3.R4` requires semantic continuity across material implementation boundaries;
- EXP-061 proved Release-1 Profile-routing-domain return affinity;
- `VPNG-U002-R2.R3.C1` keeps inbound/bidirectional Profiles at no more than one eligible
  logical path in the current product;
- EXP-062 subsequently proved concrete-path multi-path affinity technically feasible, but its
  registry disposition is **deferred**: it is a possible future functional extension, not part
  of the current baseline.

Therefore this cycle deliberately integrates only the simpler Release-1 Profile-level owner.

## What was missing before this cycle

The previous stack-return-affinity cycle had produced:

- pure deterministic affinity allocation/projection;
- Linux lower create/delete primitives;
- EXP-061 differentiating evidence.

It had intentionally not yet proved that the controller could safely adopt the owner in normal
activation. The remaining safety gap was:

```text
desired affinity
    -> ?
authoritative current owner state
    -> ?
safe convergence while forwarding is contained
    -> ?
exact verified affinity state
    -> only then structural activation / forwarding
```

Blind creation/replacement around an already active structural transaction was explicitly
rejected.

## Owner state model added

The stack return-affinity owner now has an explicit authoritative classification:

- `ABSENT` — no reserved owner state exists;
- `EXACT` — all reserved affinity state exactly matches desired state;
- `STALE` — existing state is proven to belong to the VPN-GATE affinity owner but differs
  from current desired state;
- `CONFLICT` — reserved state cannot be safely attributed to/reconciled by this owner.

The Linux observer covers both halves of the owner:

- the dedicated affinity nft owner;
- the reserved affinity RPDB priority/mark space.

Foreign or unrepresentable use of those reserved keys is a conflict. It is not adopted,
renumbered around, or overwritten.

## Guarded convergence

New `stack_return_affinity_convergence.py` provides one bounded convergence attempt.

The convergence contract is:

```text
observe owner
    -> EXACT: no mutation
    -> CONFLICT: stop
    -> ABSENT/STALE:
         freshly confirm ForwardingGate=DISABLED
         mutate only reserved proven-owned state
         re-observe owner
         re-observe ForwardingGate
         require exact owner + still-disabled barrier
```

A failed mutation is not treated as proof of failure by itself: a fresh exact postcondition may
still confirm success if the lower operation completed before reporting an error. Conversely,
a successful command is never enough without the final authoritative observation.

## Activation ordering

`network_policy_activation.py` now orders the lower domains as:

```text
ForwardingGate=DISABLED
    -> invariant nft scaffold
    -> stack return-affinity owner
    -> structural policy transaction
    -> forwarding may become enabled only from confirmed exact structural state
```

Affinity convergence failure therefore blocks structural activation entirely. Existing
failure-containment logic independently re-confirms the disabled forwarding barrier.

This closes the previous cycle's explicit activation gate.

## Desired-state and controller composition

`PayloadNetworkPolicyDesiredState` now optionally carries
`StackReturnAffinityDesired`.

The pure payload desired-state builder constructs that owner from the same current:

- Profile semantics;
- network-policy layout;
- realized current path routes;
- verified host-boundary identity.

The alpha runtime enables this projection with the accepted Linux affinity platform space.

Controller startup passes the desired affinity state and authoritative Linux owner backend into
the guarded activation path. There is no separate reply reclassification model in the
controller.

## Reconciliation / drift

The alpha runtime's fast no-op audit now requires both:

- exact ordinary structural policy;
- exact stack return-affinity owner.

If routing/nft structural state is exact but affinity state has drifted, the audit may not
declare the payload domain exact and skip guarded activation. It falls back into the contained
activation/convergence path.

Thus return-affinity state is now part of the production-shaped current-state contract rather
than a startup-only side effect.

## Stop and restart ownership

The affinity owner lives wholly inside the VPN-GATE-owned managed network namespace.

Normal stop/restart therefore does not require a second independent host cleanup callback for
this owner: successful managed-domain teardown removes the affinity owner together with the
rest of the managed namespace.

If managed-domain teardown cannot be confirmed, the existing stop contract already retains
controller ownership/lifetime lock and reports incomplete cleanup. This cycle does not weaken
that fail-closed behavior.

The ordinary-host boundary owners remain separate because they live outside the managed
namespace.

## Privileged production-backend evidence

A new production-shaped privileged integration runs the actual
`LinuxStackReturnAffinityBackend`, its authoritative observers and the guarded convergence
function.

It confirms:

1. absent reserved state can be materialized and independently observed as exact;
2. proven-owned stale state can be repaired back to exact;
3. a foreign reserved owner is classified as conflict and is not adopted or overwritten.

During development this evidence exposed real representation mismatches between the pure
model and authoritative Linux JSON output. The parser was corrected to normalize the actual
kernel/userspace representation rather than weakening the exact-state contract.

Final-head evidence on `dd29cec2279735660ab18cb2fa768f882bce10e8`:

- push workflow `44292897387`:
  - unit `134762349191` — success;
  - linux-alpha-smoke `134762349198` — success;
  - linux-stack-return-affinity `134762349647` — success;
  - linux-stack-return-affinity-owner `134762349748` — success;
- pull-request workflow `44292906422`:
  - unit `134762397342` — success;
  - linux-stack-return-affinity `134762397722` — success;
  - linux-stack-return-affinity-owner `134762397888` — success;
  - linux-alpha-smoke `134762397962` — success.

The inherited `linux-nft-marked-host-bootstrap` job remains red in both workflows because
EXP-057 is an intentionally failed/rejected bootstrap alternative. It is not a regression of
this cycle.

## EXP-062 / multi-path disposition

This cycle does not consume EXP-062 as current product functionality.

Current record remains:

```text
EXP-062
Result:      PASS
Disposition: deferred
```

Meaning:

- concrete-path affinity for inbound multi-path is technically feasible;
- it remains a possible future functional extension;
- the current Release-1 single-path inbound/bidirectional constraint remains in force;
- re-entry requires a separate explicit product decision and requirement revision.

Historical EXP-014 remains the superseded predecessor, not the current evidence gate.

## Requirements impact

No new product Requirement or Constraint was introduced in this cycle.

The implementation closes the previously identified architecture/activation gap under already
accepted:

- `VPNG-U002-R2.R6`;
- `VPNG-U007-R7.R3.R4`;
- `VPNG-U007-R7.R3.R4.R1`;
- constrained by `VPNG-U002-R2.R3.C1`.

No new suspicious reverse-engineered requirement was introduced by this implementation cycle.

## Suspicious reverse-engineered requirements still requiring human discussion

The previous review's suspect list remains open for later requirements-tree cleanup. This
cycle did not silently rewrite any of them.

### Semantic suspects

1. **`VPNG-U002-R2.R1.R2`** — exact symmetric NEW-flow classification:
   ordinary side by remote destination; VPN side by remote source restricted by actual ingress
   Device/path. The mechanism is useful, but the exact Profile/source-prefix formulation may
   have been reconstructed from implementation.
2. **`VPNG-U002-R2.R2.R2`** — Profile intent at Device level with concrete paths arising only
   from bindings. The "do not guess a path" safety property is strong, while the particular
   Profile/Device/binding formulation may belong at a lower architectural level.

### Placement / Purpose suspects

1. `VPNG-U002-R2.R1.R1` — Purpose first introduces Profile.
2. `VPNG-U002-R2.R1.R2` — Purpose depends on Profile destination semantics introduced by a
   sibling rather than an ancestor.
3. `VPNG-U002-R2.R2.R1` — Purpose first introduces Profile/user-described VPN resources.
4. `VPNG-U002-R2.R2.R2` — Purpose introduces Profile/Device/binding vocabulary.
5. `VPNG-U002-R2.R3.R3` — Purpose introduces Profile below a generic direction branch.
6. `VPNG-U002-R2.R3.R3.R1` — Purpose introduces host routing/Linux/managed-boundary vocabulary
   below a user-direction branch.
7. `VPNG-U002-R2.R3.R1.R1` — Purpose introduces isolated routing-domain/host-boundary
   mechanism below the ordinary-to-VPN direction requirement.
8. `VPNG-U002-R2.R5.R1` — Purpose first introduces Profiles below the generic
   deterministic-overlap requirement.

This list concerns requirement ancestry/abstraction quality. It does not revoke the separately
discussed and accepted semantics of host bootstrap, host stateful return, `+route-return`,
most-specific routing, or the current Release-1 single-path constraint.

`VPNG-U002-R2.R6` is not suspect; its user-level wording was explicitly corrected and
accepted before EXP-061.

## Requirement-state inventory

No requirement-state transitions were made in this implementation cycle.

The normative tree therefore retains the previous inventory:

- six `decomp` link occurrences, all resolved:
  - `VPNG-U005-R5 -> VPNG-U005-R5.R6`;
  - `VPNG-U004-R4.R6 -> VPNG-U004-R4.R6.R1` twice;
  - `VPNG-U001-R1.R3 -> VPNG-U001-R1.R3.R2` twice;
  - `VPNG-U001-R1.R2 -> VPNG-U001-R1.R2.R2`;
- pending `decomp`: **none**;
- active `unreal`: **none**;
- active `[rejected_closure]`: **none**.

## Remaining gates after this cycle

For the accepted single-path return-affinity scope, the previous controller-activation gate is
closed.

Remaining broader Release-1 work is outside this owner, including already known runtime
boundaries such as:

- full physical materialization of Profile ordinary-side `+snat`;
- availability-probe execution/runtime assembly;
- remaining host-boundary capabilities not yet assembled into the executable alpha where
  canonical syntax is currently rejected rather than ignored;
- event/runtime collection and production packaging/status work.

Future inbound/bidirectional multi-path is explicitly not among current baseline gates because
EXP-062 has disposition `deferred`.

## Cycle conclusion

The cycle converts stack return affinity from an experimentally proven lower mechanism into a
guarded production-shaped managed owner.

The important closure is not merely that the rules can be created. The controller now has an
authoritative answer to "is the affinity owner exactly ours and exactly current?", refuses
foreign state, repairs only proven-owned drift while forwarding is contained, verifies the
postcondition, and only then permits the ordinary structural activation path to proceed.

Draft PR #26 remains unmerged and is stacked on
`ng3-exp-062-inbound-multipath-affinity`.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005-R5` -> `VPNG-M001-R1.R1`
- `VPNG-U005-R5.R6` -> `VPNG-M001-R1.R1.R6`
- `VPNG-U007-R7.R3.R4` -> `VPNG-D001-R1.R1.R3.R4`
- `VPNG-U007-R7.R3.R4.R1` -> `VPNG-D001-R1.R1.R3.R4.R1`

The original IDs in the historical body are intentionally preserved.
