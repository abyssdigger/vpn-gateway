# NG3 2026-11-22 — aggressive host-routing / protective-mode re-entry review

**Scope:** re-enter the postponed aggressive host-routing helper and administrative protective
mode for active research and requirement/design refinement.

**CDC start:** 2026-11-22 18:16:28 +03:00  
**Baseline:** `f88949a8b5251f7ce3a31569506c157feb1f2503`  
**User decision:** explicitly start a new CDC to research aggressive host routing together with
protective mode.

## Decision

**PASS — RE-ENTER BOTH CAPABILITIES INTO THE ACTIVE DEVELOPMENT FRONTIER.**

The current Release-1 constraints remain accepted:

- `VPNG-U001-R5.R2.C1` still says Release 1 does not require the aggressive helper;
- `VPNG-U004-R5.C1` still says Release 1 does not require the protective mode.

Those constraints limit release obligation; they do not prohibit current research or future
implementation.

Under the mandatory requirement-status model, active re-entry without an accepted closure
candidate is represented by `open`, not by removing the status label.

## Requirement status transitions

Re-enter:

- `VPNG-U001-R5.R2`: `postponed -> open`;
- `VPNG-U001-R5.R2.R2`: `postponed -> open`;
- `VPNG-U001-R5.R2.R3`: `postponed -> open`;
- `VPNG-U004-R5`: `postponed -> open`.

Keep unchanged:

- `VPNG-U001-R5.R2.R1`: `closed`; EXP-074 remains accepted narrow evidence for
  authoritative managed-destination routing;
- both Release-1 constraints: `closed`;
- peaceful host routing and all core fail-closed requirements.

## Research boundary

The research unit must treat the two capabilities as composed but independently owned:

1. aggressive host-routing owns the explicitly delegated ordinary-host routing scope;
2. protective mode is a public VPN-GATE safety capability with independent administrator value;
3. unrecoverable aggressive-helper failure may request the same public protective operation;
4. the helper must first establish whatever host-side containment is available to it and must
   not assume that a request to core protective mode has already succeeded.

Research must determine:

- the exact authoritative drift/recovery contract for `VPNG-U001-R5.R2.R2`;
- the minimum independently confirmable host-side containment required by
  `VPNG-U001-R5.R2.R3`;
- the decomposition of `VPNG-U004-R5` into control/lifecycle and traffic-postcondition
  contracts;
- which current mechanisms (EXP-074 host RPDB ownership and the managed-netns ForwardingGate)
  are reusable evidence versus insufficient partial mechanisms;
- the atomicity/ordering needed when entering and leaving protective mode.

No product semantics are changed by this review beyond re-entering the already accepted
capabilities into the active development frontier.

## Verdict

**PASS.** The four nodes above should become `open`; research/design may proceed without
claiming architecture closure.
