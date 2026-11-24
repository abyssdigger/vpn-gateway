# NG3 2026-11-24 — EXP-088 ten-peer WireGuard experiment-design review

**Scope:** review the planned experiment before an executable harness is written.

## Verdict

**PASS — EXPERIMENT DESIGN ACCEPTED; EXECUTION NOT STARTED IN THIS REVIEW UNIT.**

## Findings and dispositions

### F1 — experiment now has normative authority

**Decision:** accepted.  
**Resolution:** fixed.

EXP-088 traces directly to open requirements `VPNG-U001-R1.R3.R7`,
`VPNG-U001-R1.R3.R7.R2` and `VPNG-U001-R1.R3.R8`. It is no longer justified only by a
declaration or by technical interest.

### F2 — the test isolates the lower contract from the future Device Manager

**Decision:** accepted.

The planned stand contains no production Device Manager and no final user configuration
grammar. It tests the WireGuard state boundary that a later manager may consume.

### F3 — ten-peer scale is useful without becoming an arbitrary product limit

**Decision:** accepted.

Ten peers are the experiment scale requested by the projectholder. The requirement itself says
multiple ordered peers and does not invent a maximum of ten.

### F4 — base configuration and dynamic AllowedIPs ownership are independently testable

**Decision:** accepted.

The base configuration contains only permanent peer facts and per-peer probe /32s. The shared
payload prefix begins unowned and is applied only after fresh observation. Full interface
restart must return to that no-owner base state.

### F5 — stale evidence has an explicit experimental generation

**Decision:** accepted.

The stand uses an experiment-only realization generation. It does not modify `LogicalPathId`
or claim the final production type, but it makes the stale-evidence question directly
testable.

### F6 — transition atomicity is correctly an observation, not a preselected answer

**Decision:** accepted.

H1-H6 determine PASS. H7 records packet loss, wrong-peer delivery and the behavior of complete
multi-peer `wg set` updates. If the transition is not sufficiently strong, the later
architecture must add containment rather than rewriting the experiment criterion.

## Result

The experiment design is ready for a later executable-harness unit. No production
implementation or architecture closure is claimed.
