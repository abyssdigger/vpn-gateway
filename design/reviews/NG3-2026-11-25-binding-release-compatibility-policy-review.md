# NG3 binding-release compatibility policy review — 2026-11-25

**Review unit:** requirement-classification clarification and release-based backward-compatibility policy  
**Requirements:** `VPNG-M001-R4*`  
**Architecture:** `design/NG3/architecture-ng.md` maintainability/continuity/process coverage  
**Process:** `PROJECT-CONVENTIONS.md` §10  
**Reviewed head:** `c13758aebae10ea260b69a204e594aed49f2beea`

## Verdict

**PASS — compatibility is now an explicit maintenance/operational concern with a projectholder-controlled binding-release baseline, without imposing premature compatibility on pre-binding releases.**

The requirement namespace rule now classifies the optimized concern / beneficiary rather than the actor implementing the obligation. The compatibility lifecycle is therefore correctly under `VPNG-M001`, while the release methodology remains the process materialization of the accepted policy.

## Accepted semantics

- Publication alone does not create a backward-compatibility guarantee.
- Until the first release explicitly designated by the projectholder as `binding`, inter-version backward compatibility is not mandatory.
- The first `binding release` establishes the compatibility baseline for supported external contracts covered by the guarantee.
- Subsequent releases in the same major line preserve that compatibility unless a contract is explicitly outside the guarantee.
- A new major release may intentionally break compatibility only when the approved release scope makes the break explicit and records applicable migration consequences/path.
- The current 0.1.0 scope is explicitly `non-binding`.

## Findings and dispositions

### F1 — current 0.1.0 scope did not state the newly required compatibility role

**Decision:** accepted.  
**Resolution:** fixed by `59bd8fab5569960c51cdb331e58b5722cb8334f6`.

The approved 0.1.0 scope now records `Compatibility role: non-binding`, matching the explicit projectholder decision and preventing publication of 0.1.0 from accidentally creating a compatibility baseline.

### F2 — the new closed compatibility constraints initially lacked accepted closure

**Decision:** accepted.  
**Resolution:** fixed by `d3efd2aa6cdfb6d2977a2ddce455594b75a412be`.

`VPNG-M001-R4.C1` and `VPNG-M001-R4.C2` are process-policy constraints rather than runtime mechanisms. The established architecture process-coverage section now traces them to `PROJECT-CONVENTIONS.md` §10, using the same boundary already used for `VPNG-D001-R3*`.

The first CI run exposed this omission through the architecture-traceability invariant rather than allowing an unclosed `closed` requirement.

### F3 — permanent parent traceability must not depend on a closed-node test

**Decision:** accepted.  
**Resolution:** fixed by `c13758aebae10ea260b69a204e594aed49f2beea`.

`VPNG-M001-R4` is `permanent`, so the closed-requirement test does not require its direct architecture marker. The architecture coverage was nevertheless extended to include the parent explicitly, preserving bidirectional traceability independently of test implementation details.

### F4 — the old managed-Device config heading is not an inter-version guarantee

**Decision:** accepted.  
**Resolution:** deferred to the WireGuard/config-model refinement block.

The current `config-model.md` heading “Обратная совместимость” describes preservation of the externally managed Device operating mode when `managed_vpn` is absent. With the new project-wide compatibility term now normative, that heading should be renamed/reworded during the next relevant config-model edit so it cannot be mistaken for an inter-version compatibility promise. No runtime or user-facing contract needs to change merely to rename the concept.

## Evidence

- Initial workflow run `45560338081`, unit job `139022255086`: **FAIL**, exactly two architecture-closure failures for the newly added `VPNG-M001-R4.C1/C2`; this finding was accepted and corrected.
- Corrected workflow run `45560630178`, unit job `139023308256`: **PASS**.
- Final reviewed workflow run `45560761177`, unit job `139023737723`: **PASS**.
- Actual-main lineage guard for final reviewed head: run `45560761228`: **PASS**.
- Final diff remains methodology/requirements/architecture/release-scope only; no product runtime implementation changed.

## Status disposition

No further requirement-status transition is required. `VPNG-M001-R4` remains `permanent`; `VPNG-M001-R4.C1` and `VPNG-M001-R4.C2` remain `closed` with explicit process-backed closure.
