# VPN-GATE NG3 — Initial Requirements and Architecture Review

**Status:** final review for the first NG3 design review unit  
**Cycle:** `ng3-design-cycle-20261115-40m`  
**Requirements:** `design/NG3/requirements.md`  
**Architecture:** `design/NG3/architecture.md`  
**Requirements model:** `design/requirements-model.md`  
**Component model:** `design/component-model.md`

## 1. Review scope

This review answers four questions:

1. Is the initial NG3 requirement tree sensible on its own, without treating NG2 as the
   specification?
2. Does the first architecture honestly report implementation of those requirements?
3. Which NG2 ideas were independently re-derived, and which were merely tempting to carry
   forward?
4. Which accepted requirements or product questions remain without sufficient architecture?

The review does not review production code. NG3 currently has no implementation baseline.

## 2. Mandatory NG2 handoff input

The review explicitly considered:

```text
legacy-main-ng1-2:design/NG2/HANDOFF.md
branch: code-cycle-20261115-publisher-failure-recovery-40m
handoff review-input commit: a8d17ffd0c4fd2bef37e2ce231d4d9d8f4c89e0b
```

The handoff was treated as historical evidence and conversation delta only.

No NG2 item was accepted merely because the handoff called it normative for NG2.

For each material NG2 idea, this review asks whether NG3 requirements independently need
the behavior.

# 3. Requirement sanity review

## 3.1. L1 coverage

The accepted L1 set is internally coherent:

- `VPNG-R1` defines the product as a managed VPN router;
- `VPNG-R2` makes VPN use explicit policy rather than accidental reachability;
- `VPNG-R3` defines deterministic preference and adaptation;
- `VPNG-R4` defines fail-closed safety;
- `VPNG-R5` defines lifecycle/recovery obligations;
- `VPNG-R6` defines current-state observability;
- `VPNG-R7` defines implementation quality: sufficiency, comprehensibility, isolation,
  parallel development, component-model use and requirement traceability.

This is a plausible minimal top-level partition for the product as currently understood.

No L1 is merely the name of an NG2 component.

## 3.2. R7 is a legitimate product implementation requirement

`VPNG-R7` is intentionally different in kind from R1-R6: it constrains the quality and
evolvability of the implementation rather than packet behavior.

That is appropriate here because maintainability, comprehensibility, isolated change and
parallel development are explicit project requirements, not stylistic preferences.

In particular:

`VPNG-R7.R5` makes `design/component-model.md` a required implementation method.

The component model therefore remains reusable and product-independent; NG3 is the thing
that depends on it, not vice versa.

## 3.3. Requirement tree does not yet prove whole-product completeness

The tree is sufficient to start core payload/availability design, but it is not yet evidence
that every major VPN-GATE product responsibility has been captured.

The original VPN-path ownership gap was resolved during this review by
`VPNG-R1.R3 -> VPNG-R1.R3.C1 -> VPNG-R1.R3.C1.R1`. The remaining gaps are lower-level
configuration/onboarding semantics rather than uncertainty over who provisions the VPN
channel in the first release.

# 4. Findings and disposition

## F1 — Active probing leaked into the first requirement draft

**Severity:** design-model correctness  
**Disposition:** accepted and fixed during this cycle

The first draft made active probing/cadence/physical generation look like requirements under
`VPNG-R3.R6`.

That reversed the intended dependency:

```text
known implementation
    -> invented lower requirement
```

The requirement tree was corrected to require only:

- current path-usability evidence;
- correct path identity;
- freshness;
- adequacy for supported failure scenarios.

Active observation is now an architecture choice used for scenario S3.

Physical generation is an architecture mechanism for freshness, not a requirement.

## F2 — "No unbounded history" leaked into path behavior

**Severity:** requirement layering  
**Disposition:** accepted and fixed during this cycle

The first `VPNG-R3.R5` wording mixed product adaptation stability with the known simplified
implementation.

The product requirement now states the observable confirmation behavior.

The implementation preference for bounded current/aggregate state lives under
`VPNG-R7.R1.R1`.

This preserves the distinction:

```text
R3: what adaptation must mean
R7: how much implementation complexity is acceptable
architecture: bounded state chosen to satisfy both
```

## F3 — Ownership of VPN paths required an explicit product decision

**Severity:** major requirement gap  
**Disposition:** accepted and resolved by explicit requirement/constraint

The initial L1 wording spoke about "configured VPN paths" but did not decide who creates and
configures those paths.

The accepted requirement chain is now:

```text
VPNG-R1.R3
    VPN-GATE must be able to consume supported VPN channels as paths

VPNG-R1.R3.C1
    first release: administrator deploys and basically configures the VPN channel

VPNG-R1.R3.C1.R1
    VPN-GATE must provide the instructions/contract needed to make that channel
    visible, manageable and usable by VPN-GATE
```

This resolves the ownership question for the first release without importing NG1/NG2
VPN-process architecture.

Architectural consequence:

- no VPN-session/tunnel provisioning Manager is introduced;
- the architecture contains an external VPN-channel boundary;
- exact administrator-facing onboarding identity/mechanism remains to be refined before a
  concrete Driver/Agent/Adapter is chosen.

This is a successful example of constraint lifting: the limitation is visible at the product
boundary and its compensating administrator-facing requirement is explicit.

## F4 — User configuration semantics are deliberately incomplete

**Severity:** normal requirement/design gap  
**Disposition:** accepted, open

The architecture can consume normalized payload intent, but the requirements do not yet
define enough to design the authoritative user configuration model.

Still open:

- traffic-class expression;
- path references;
- direction representation;
- overlap/conflict presentation;
- live configuration-change guarantees.

The architecture correctly does not invent a universal configuration object.

This leaves `VPNG-R1.R2`, parts of `VPNG-R2`, and `VPNG-R6.R1` without complete
architecture.

## F5 — Availability confirmation is improved but not fully specified

**Severity:** localized requirement gap  
**Disposition:** accepted, open but non-blocking outside availability internals

`VPNG-R3.R5.R1` and `VPNG-R3.R5.R2` now separately define finite degradation and recovery
confirmation.

Still unspecified:

- exact negative-evidence semantics;
- whether confirmation thresholds are user-facing configuration or internal policy;
- how delayed positive evidence interacts with an evaluation boundary.

Therefore the bounded state responsibility is justified, but the final event/input contract
and exact hysteresis algorithm are intentionally not normative yet.

## F6 — Final user-visible status aggregation is not designed

**Severity:** normal architecture gap  
**Disposition:** accepted, open

`VPNG-R6` is strong enough to require observability but not yet specific enough to justify
a particular global StatusManager/RuntimeStateManager.

The current architecture can publish component-local current projections.

It cannot yet claim a complete implementation of `VPNG-R6`.

This is preferable to creating a status super-component before its semantics are known.

## F7 — Lifecycle postconditions do not yet justify a LifecycleManager

**Severity:** none; simplification finding  
**Disposition:** accepted architecture decision

`VPNG-R5` and `VPNG-R4.R4` require startup/shutdown/recovery postconditions.

They do not currently require a long-lived lifecycle Engine.

The architecture therefore retains procedural orchestration as the minimal default and
introduces no LifecycleManager.

A dedicated component should appear only if later requirements give it persistent semantic
state or ongoing management responsibility.

## F8 — Architecture names resemble NG2 but responsibilities were re-derived

**Severity:** review concern  
**Disposition:** accepted

Names such as `PayloadTrafficManager` are similar to NG2.

The review found that the responsibility is nevertheless independently justified by the
combination of:

- `VPNG-R1.R1`;
- `VPNG-R2`;
- `VPNG-R3.R1-R5` plus `VPNG-R3.R7`;
- `VPNG-R4`;
- `VPNG-R5.R2-R3`;
- `VPNG-R7`.

The name itself is not treated as inherited design.

If later decomposition produces a better responsibility boundary, the name has no protected
status.

## F9 — Architecture traceability is materially honest but partial

**Severity:** minor  
**Disposition:** accepted

The architecture has exact requirement references at component/section scope.

However some requirements are only partially realized because their upstream or downstream
contracts are not yet designed.

The architecture explicitly marks those gaps rather than claiming whole-L1 completion.

Future reviews should continue to distinguish:

```text
requirement has some implementing architecture
!=
requirement is fully architected end-to-end
```

No extra traceability taxonomy is introduced yet; the coverage table is sufficient for the
current document.

# 5. NG2 handoff reconciliation

## 5.1. Independently re-derived and therefore acceptable in NG3

### Availability modifies preference, not membership

NG2 handoff idea:
availability affects route priority only.

NG3 basis:
- `VPNG-R2.R4`
- `VPNG-R3.R2`
- `VPNG-R3.R7`

**Result:** re-derived. Keep the semantic rule.

### All-clear availability is a no-op on configured order

NG2 handoff idea:
when no path has an established problem, availability does not change routing order.

NG3 basis:
- `VPNG-R3.R1`
- `VPNG-R3.R7`

**Result:** re-derived.

### Bounded availability state rather than history

NG2 handoff idea:
bounded counters/current facts; no attempt journal/window history.

NG3 basis:
- `VPNG-R3.R5`
- `VPNG-R3.R5.R1`
- `VPNG-R3.R5.R2`
- `VPNG-R7.R1`
- `VPNG-R7.R1.R1`

**Result:** the need for bounded implementation is re-derived. The exact NG2
`pending_good_news/tick_pending` representation is not inherited.

### Stale physical observation rejection

NG2 handoff idea:
a physical generation token prevents old workers from affecting a new path context.

NG3 basis:
- `VPNG-R3.R6.R1`
- `VPNG-R3.R6.R2`

**Result:** the behavior is re-derived. A local generation token is currently the minimal
architecture mechanism, but its NG2 type/API is not inherited.

### Payload/network lower-domain boundary

NG2 handoff idea:
upper payload policy does not know route-table/nft/sysctl mechanics.

NG3 basis:
- `VPNG-R7.R3`
- `VPNG-R7.R3.R2`
- `VPNG-R4.R2-R5`
- `VPNG-R5.R2-R4`
- `VPNG-R7.R5`

**Result:** Adapter/Executor separation is independently justified.

## 5.2. Not carried into NG3

The following NG2 details are not requirements and are not part of current NG3 architecture:

- `PayloadTrafficStateRequest` schema;
- `AvailabilityPriorityChannel` field layout;
- exact `good_news + tick` input representation;
- same-pass asymmetry rules;
- policy-only-change reset details;
- `AvailabilityProbeManager` as a required separate Manager;
- probe-specific NetworkRules generation model;
- one shared owner-composing `NetworkRulesAdapter`;
- owner identity represented by Manager object identity;
- exact publisher-failure retry rules;
- `ExceptionGroup` as required error representation;
- EventEnvelope/revision/epoch machinery;
- the NG2 metric empty-slot route permutation algorithm;
- `BLACKHOLE_METRIC=65536`;
- nftables/iproute command layout;
- Linux protocol numbers;
- specific ICMP transport choice;
- exact timer/audit cadence;
- final RuntimeStateManager/ProfileState structure.

Some may be selected later if a requirement plus evidence makes them the smallest sufficient
solution.

## 5.3. NG2 evidence that remains potentially reusable

Historical experiments may remain useful if NG3 later makes the same kernel claim:

- EXP-025 stale probe conntrack generation;
- EXP-026 probe-class conntrack cleanup;
- EXP-027 route-priority transition;
- existing Linux/nft/LOCAL_PROCESS behavior evidence.

The evidence can be reused only when the NG3 claim is materially the same.

The architecture that originally motivated the experiment does not automatically transfer
with the evidence.

# 6. Requirements left without complete architecture

The following areas are intentionally suspended rather than filled with speculative design.

| Requirement | Missing architecture / decision |
| --- | --- |
| `VPNG-R1.R2` | authoritative user configuration boundary |
| `VPNG-R1.R3.C1.R1` | concrete administrator-facing VPN-channel onboarding contract/instructions |
| parts of `VPNG-R2` | concrete traffic classification/configuration model |
| `VPNG-R3.R5` subtree | final negative-evidence and threshold semantics |
| `VPNG-R4.R3-R5` | concrete lower network transition algorithm |
| `VPNG-R5.R1` | full startup dependency graph |
| `VPNG-R5.R4-R5` | complete ownership map for cleanup |
| `VPNG-R6.R1-R4` | final system-wide status aggregation/presentation |
| lower implementation of `VPNG-R7` | code does not exist yet; architecture rules only |

This is an expected result of requirement-first design.

A requirement without architecture is visible work.

An architecture without a requirement would be hidden scope growth.

# 7. Standalone common-sense review of the requirements

Ignoring NG2 and reading only the NG3 requirements:

## What is strong

- The product has a clear routing purpose.
- Permission is explicit rather than inferred from availability.
- Multiple paths have deterministic user preference.
- Adaptation is subordinate to policy.
- Safety under uncertainty is explicit.
- Lifecycle cleanup/recovery is a product obligation.
- Observability describes effective reality rather than only intent.
- Implementation quality is a real requirement rather than an informal coding preference.
- The requirement tree does not currently expose Linux or a specific VPN protocol as product
  semantics.

## What remains underspecified

- The exact administrator-facing contract by which an externally provisioned VPN channel becomes identifiable and usable by VPN-GATE.
- What the user configuration vocabulary is.
- What exact remote/path failures availability is required to detect.
- How much availability tuning is user-visible.
- What status surface the operator receives.
- Which deployment/network topologies are part of the supported product envelope.
- IP-family/protocol/environment constraints have not yet been accepted.

None of these should be guessed from old implementation.

## Compact requirement presentation

The NG3 requirement document now uses one normative line per node:

```text
**[ID]** Purpose | Statement   — R
**[ID]** Reason  | Statement   — C
```

Section headings are grouping only and carry no requirement semantics.

This is a presentation change, not a semantic compression: full `Purpose/Reason` and
`Statement` remain mandatory. The format is intentionally straightforward to validate
mechanically later.

# 8. Simplification review

The current architecture deliberately avoided:

- a universal runtime state Manager;
- a lifecycle Engine;
- an availability super-state-machine;
- event history/replay;
- a second route writer;
- physical probe details in payload policy;
- kernel allocation semantics above the Adapter;
- automatic transfer of NG2 route algorithms.

No omitted mechanism is currently required by an accepted NG3 requirement.

The architecture therefore satisfies the intent of `VPNG-R7.R1` at this stage.

# 9. Traceability evidence

A mechanical reference check was run against the current NG3 requirement and architecture
documents.

Result:

```text
requirement/constraint IDs in tree:   55
architecture requirement references:  177
unique IDs referenced:                 51
missing/broken IDs:                    0
```

The seven component-role sections currently detected in the architecture are:

- PayloadTrafficManager — Manager;
- PayloadPolicyCalculator — Calculator;
- AvailabilityPriorityCalculator — Calculator;
- AvailabilityProbeAgent — Agent;
- ActiveProbeDriver — Driver;
- NetworkPolicyAdapter — Adapter;
- NetworkPolicyExecutor — Executor.

Direct architecture coverage currently leaves only parent/aggregate L1 nodes without their
own explicit references; the cross-cutting implementation-quality children are now linked at
architecture-document scope.

This check proves reference integrity only. It does not prove that every traceability claim
is semantically correct; that is covered by the expert review above.

# 10. Final verdict

**Verdict: PASS for the first NG3 requirement-first architecture review unit, with explicit
open requirement gates.**

The core payload/availability decomposition is sufficiently justified to serve as the first
NG3 architecture baseline.

The review does **not** declare the whole NG3 product architecture complete.

The VPN-channel ownership gate is now resolved for the first release: the administrator
provisions/configures the channel, and VPN-GATE consumes it through a documented onboarding
contract.

The next requirement-first unit should refine that onboarding/configuration contract and
final observability semantics before expanding architecture into those areas.
