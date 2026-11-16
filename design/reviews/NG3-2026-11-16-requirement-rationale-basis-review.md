# VPN-GATE NG3 — full requirement rationale / basis review

**Date:** 2026-11-16  
**Reviewed baseline:** `633d53b954210a62f6e52135acae77f338db6803`  
**Normative methodology:** `design/requirements-model.md` at/after `56bb09107cb591e9ff8d086c2642c14bc70bb22b`

## 1. Scope

The review covered the complete current NG3 requirement tree after migration to primary
project requirements:

```text
primary project Requirements: 7
derived Requirements:        115
Constraints:                   6
total normative nodes:       128
```

Every node was checked for:

- provenance of primary roots (`Basis / Основание`);
- causal adequacy of derived `Purpose`;
- causal adequacy of Constraint `Reason`;
- ancestry/scope consistency;
- hidden architecture-as-requirement rationale;
- actor completeness for normative actions;
- continued architecture closure after wording corrections.

## 2. Primary Basis review

**PASS after wording clarification.**

All seven primary roots originate from the customer/analyst interview that produced the
initial NG3 requirement tree on 2026-11-15.

The project record is commit
`4b3785b5c228782768afe317d4f09386fd46b440`
(`NG3: establish initial requirement tree`, 2026-11-15 21:14:07 +03:00).

The migrated wording initially described that commit timestamp as the interview timestamp.
That was too strong: the Git timestamp proves when the requirement set was recorded, not the
exact instant of every customer utterance.

The Basis was therefore normalized to:

```text
interview date: 2026-11-15
project record: initial requirement-tree commit + exact commit time
topic locator: per primary requirement
```

No project-internal rationale is substituted for the external source.

## 3. Derived Purpose review

**PASS.**

The 115 derived Requirements were checked against their direct ancestry.

No derived Purpose requires a new independent user-facing promise beyond its primary root.
The top derived nodes deliberately restate the corresponding primary Statement as their
Purpose; this is the intended bridge from external primary promise to the existing detailed
tree, not a self-justification loop.

The R3 ancestry had three actor-ambiguous passive references to “allowed paths”. They were
clarified to mean paths allowed by the user. No path-eligibility semantics changed.

No Purpose was found that exists only to justify a preferred component, queue, state machine,
kernel mechanism or other implementation convenience.

## 4. Constraint Reason review

Six Constraints were reviewed.

### F1 — Device/Profile ID grammar used Purpose instead of Reason

**Node:** `VPNG0001-R1.R2.R4.R1.C1`  
**Severity:** semantic-form defect  
**Disposition:** accepted and fixed

The italic part said:

```text
Чтобы Device/Profile IDs оставались однозначными ...
```

That is a Purpose, not a cause of the restriction.

It now records the actual contract cause: the current human-facing contract does not define
a separate quoting/escaping semantics for IDs, therefore the accepted ID surface is restricted
to one simple canonical textual form.

### F2 — first-release VPN provisioning Reason was too close to its Statement

**Node:** `VPNG0001-R1.R3.C1`  
**Severity:** rationale clarity  
**Disposition:** accepted and fixed

The Reason now identifies the accepted first-release scope boundary — use of VPN channels
already provisioned/configured by the administrator/external environment — rather than merely
repeating who performs the work.

### F3 — ICMP-only first-release Reason mixed cause and intended implementation sequence

**Node:** `VPNG0003-R3.R6.R3.R1.C1`  
**Severity:** rationale clarity  
**Disposition:** accepted and fixed

The Reason now states the actual scope cause: first release accepts a minimal active-check
surface and requirements do not justify a universal probe framework before the baseline ICMP
path is implemented and validated.

### Other Constraints

The remaining three Reasons are adequate:

- `VPNG0001-R1.R2.R4.R6.C1` — historical grammar is genuinely unclosed; old spellings
  therefore cannot become normative by inheritance;
- `VPNG0001-R1.R3.C2` — the support limitation is a direct consequence of the already
  accepted isolated managed-network-domain boundary;
- `VPNG0002-R2.R3.C1` — the Release 1 inbound/bidirectional capacity restriction is tied
  to an explicit unproven return-path semantic and named future evidence gate.

No Constraint is being used as an unexplained root-level product requirement.

## 5. Actor-completeness review

**PASS after fixes.**

The review distinguished postconditions/properties (where the subject is the state/object
itself) from actions that can plausibly be performed by different actors.

Ambiguous action ownership was corrected in these areas:

- rejection/normalization of invalid configuration;
- acceptance of aliases and strict policy-value validation;
- unknown Device references;
- ambiguous Device binding;
- delivery of administrator onboarding instructions;
- Profile classification for NEW traffic;
- Release 1 inbound/bidirectional fail-fast validation;
- configured path-preference ownership;
- availability-target normalization/derivation;
- network-policy transition execution;
- operator-facing current-intent and effective-state observability.

The R3 root and derived Purpose now explicitly identify the user as the actor that allows
multiple VPN paths.

No product semantics were intentionally changed; the fixes make actors already implied by
the accepted ancestry explicit.

## 6. Architecture closure revalidation

The wording fixes change provenance/rationale clarity and explicit actors, not the accepted
product envelope.

The architecture was rechecked against the affected nodes:

- configuration validation remains owned by ConfigurationAdapter;
- Profile classification remains owned by PayloadPolicyCalculator;
- path ordering remains derived from user `device_order`/selector ordering and handled by
  the accepted payload/priority contracts;
- availability target normalization remains an accepted calculator/config boundary;
- policy transition execution remains a VPN-GATE-owned NetworkPolicyExecutor responsibility;
- status composition remains the RuntimeStatusAgent responsibility;
- administrator onboarding remains the accepted first-release external-channel boundary.

Therefore existing `[closed]` labels remain valid after this review.

## 7. Mechanical integrity after fixes

Expected invariants:

```text
normative nodes:                    128
primary roots:                        7
derived Requirements:               115
Constraints:                           6
Constraints with "Чтобы" Reason:       0
primary roots without interview Basis: 0
legacy VPNG-R... IDs:                  0
```

Architecture/config trace IDs remain unchanged by this review because no node ID changed.

## Final verdict

**PASS AFTER REVIEW FIXES.**

The complete current NG3 requirement tree now has:

- a verifiable external Basis for every primary root;
- a causally adequate Purpose for every derived Requirement;
- an actual Reason for every Constraint;
- no discovered self-justifying requirement rationale;
- explicit actors where action ownership would otherwise be ambiguous;
- preserved Release 1 architecture closure.

No unresolved rationale question requires customer escalation before continuing the normal
continuous-development workflow.
