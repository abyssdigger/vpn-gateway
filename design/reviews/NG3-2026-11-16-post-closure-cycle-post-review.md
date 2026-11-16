# VPN-GATE NG3 — Post-cycle review of post-closure implementation-readiness cycle

**Date:** 2026-11-16  
**Reviewed historical cycle:** ng3-design-cycle-20261116-post-closure-implementation-readiness-40m  
**Historical checkpoint:** f91db0ed79dcebb86d3085ca0317074cb2047753  
**Review/fix branch:** ng3-review-20261116-post-closure-implementation-readiness

## 1. Review scope

This review re-checks the completed cycle as one change-set rather than accepting the
per-unit reviews independently.

Compared against the previous accepted checkpoint
ng3-design-cycle-20261116-first-release-inbound-constraint-40m,
the reviewed cycle is 65 commits ahead and adds the first bounded executable NG3 reference
slices plus their review artifacts.

The review covered requirements/architecture closure integrity, all new Python reference
units, cross-contract seams, executable-reference traceability, checkpoint claims, and
external CI evidence.

## 2. Revised verdict

### Requirements / architecture

**PASS.**

The cycle does not alter product requirements and no new semantic ambiguity was found.
The accepted Release 1 requirement tree remains 121/121 closed with architecture trace.

### Historical executable checkpoint f91db0ed

**PASS WITH REQUIRED POST-REVIEW FIXES, not a clean implementation baseline by itself.**

A material caller-validation defect was found in availability confirmation code after the
cycle checkpoint. The defect could convert invalid caller data into semantic path evidence.

Development should continue from the review/fix branch (or equivalent fixes), not from the
unmodified historical checkpoint.

## 3. Material finding — invalid availability input could fabricate evidence

**Severity:** material correctness / safety  
**Status:** fixed on review branch

Historical code used identity comparisons against AvailabilityOutcome but did not reject
non-enum values.

Example:

~~~text
state: no established problem
outcome: "positive"  # plain string, not AvailabilityOutcome.POSITIVE
    ->
falls through as if negative evidence
~~~

Arbitrary non-enum values could similarly be interpreted as negative or positive evidence
depending on current problem state.

That violates the architecture contract that only normalized accepted
positive | negative | no_evidence evidence may enter hysteresis.

Fix:

- require outcome to be an actual AvailabilityOutcome;
- reject invalid caller state instead of assigning evidence semantics.

Commit: c00836ef1894337458c59b6708fe79fdc1b63e66

## 4. Material finding — confirmation state admitted impossible numeric states

**Severity:** material contract-hardening defect  
**Status:** fixed on review branch

Historical AvailabilityConfirmationState only checked progress for negativity.

Because Python booleans are integers and runtime annotations are not enforced, states such as:

~~~text
availability_problem = 1
degradation_progress = True
degradation_progress = 0.5
~~~

were constructible.

The architecture defines bounded integer progress and a boolean established-problem flag.

Fix:

- strict boolean availability_problem;
- strict non-negative integer progress;
- reject progress above the currently supplied confirmation threshold;
- add regression coverage for invalid state and invalid outcome.

Regression tests for the repaired unit: 9/9 PASS in an independent rootless review run.

Test commit: 3188bb115d3d861831238785e3e20fb5b7397df2

## 5. Finding — config accepted a selector that Linux can never observe

**Severity:** implementation-validation defect  
**Status:** fixed on review branch

The accepted interface-inventory boundary rejects Linux ifnames longer than
IFNAMSIZ-1 = 15 bytes.

Historical structural config validation did not apply the same technical limit to exact or
prefix selector fragments. It could therefore accept an enabled selector that can never match
a valid observed Linux interface and silently remain pathless forever.

Fix:

- reject selector fragments longer than Linux IFNAMSIZ-1;
- enforce the same size invariant in direct InterfaceIdentity construction;
- add config and identity regression cases.

Commits:

- ca5675b1c72da788ac25ac29b73a8873034e64b9
- 89afe767a24407587a77e06a57ca25ae84cef88b
- 409ac50ba5e298f8dc25efd804f8bbcc61576bfd
- 57b462f2bfbe9d9f95e4816df4e0747e3f46a5bf

This fix deliberately does not invent additional user-facing restrictions for whitespace,
colon or other disputed interface-name characters.

## 6. Finding — package docstring was not a module docstring

**Severity:** low / documentary Python defect  
**Status:** fixed on review branch

rou/__init__.py placed imports before the string intended as the package docstring, so it
was not assigned to rou.__doc__.

Fixed mechanically in commit:
7c4ac2b6a5e0f76bff4a2f81aac367173731c82b

No runtime semantics changed.

## 7. Residual risk — route-priority planner is clean-state machinery only

**Severity:** important next-implementation boundary  
**Status:** not a defect in the bounded unit; must remain explicit

route_priority.py correctly plans priority permutations when current state is representable
as exactly one metric per logical path.

It does not represent a partially executed make-before-break state such as:

~~~text
same path X currently observed at Mold and Mnew
~~~

which is precisely a state that can exist if execution fails after add and before delete.

Therefore this planner must not be mistaken for the complete NetworkPolicyExecutor
recovery/convergence algorithm.

The future Executor unit still needs:

- fresh authoritative route observation;
- representation of duplicate/stale owned route instances;
- classification of already-completed partial move steps;
- convergence from partial state without replaying stale command sequences;
- final postcondition verification.

This is consistent with the original gate, which excluded execution/recovery.

## 8. Residual process risk — checkpoint has no GitHub CI evidence

**Severity:** process/evidence gap  
**Status:** open

For checkpoint commit f91db0ed79dcebb86d3085ca0317074cb2047753:

- combined commit statuses: none;
- associated GitHub Actions workflow runs: none.

The checkpoint records 78 rootless test functions and prior local PASS statements, but GitHub
does not independently attest that the final checkpoint tree executed those 78 tests.

This does not invalidate the reviewed semantics, but before executable reference code becomes
a merge/release gate, CI should make the rootless suite reproducible from the commit itself.

## 9. Residual implementation-hardening pattern — trusted normalized constructors

**Severity:** low-to-medium future API risk  
**Status:** open by design for current reference code

Several normalized dataclasses are exported but rely on trusted builders/parsers for their
invariants, including ExpectedInterfaceSelector, LogicalPathId, DeviceBindingState and
PayloadProfileRequest.

The accepted pipeline produces valid values, so no current product-semantic defect was proven.

Before these types become a wider runtime/plugin/public API, choose one explicit boundary:

1. keep constructors internal and accept values only from validated normalization paths; or
2. enforce the complete normalized invariants in the value objects themselves.

Do not silently rely on Python type annotations as runtime validation.

## 10. Parts of the cycle that remain accepted

No additional defect was found in the reviewed semantics of:

- strict Device/Profile structural config and active-Device derivation;
- destination canonicalization;
- stable logical slot binding and delayed promotion after committed disappearance;
- Profile-local path ordering;
- zero-path Profile preservation;
- inbound ingress-path restriction;
- matching-prefix longest-prefix classification;
- availability priority as membership-preserving stable partition;
- pure clean-state make-before-break priority planning;
- requirement -> architecture -> executable-reference traceability.

## 11. Recommended continuation point

Use branch:

ng3-review-20261116-post-closure-implementation-readiness

as the implementation continuation base after this review, or port its fixes onto the next
cycle branch.

The historical 40-minute branch remains useful as immutable cycle evidence and should not be
rewritten.

## Final verdict

**PASS AFTER POST-CYCLE FIXES.**

Product semantics and Release 1 architecture closure remain accepted.

The repeat review found one material availability-evidence correctness bug, one related state
validation defect, one Linux/config validation mismatch, and one minor package-documentation
defect; all are fixed on the separate review branch.

The most important remaining implementation boundary is still the real
VPNPathAdapter/Executor observation-and-convergence path, especially recovery from partial
make-before-break state.
