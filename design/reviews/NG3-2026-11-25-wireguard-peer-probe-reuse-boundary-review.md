# NG3 WireGuard peer-probe reuse-boundary review — 2026-11-25

**Review unit:** D.002 production reuse boundary before implementation  
**Requirements:** `VPNG-U001-R1.R3.R8`  
**Architecture:** C.001, C.008, D.002, D.003  
**Evidence basis:** `EV-00050`

## Findings

### F1 — current availability owner identity cannot represent a WireGuard peer

**Decision:** accepted  
**Resolution:** clarified

`ProbePolicyOwner` requires a Profile id and `LogicalPathId`, and downstream production code
uses both fields semantically. A WireGuard peer is explicitly not a logical path under D.002.
Synthetic owners would therefore violate the selected component model rather than constitute
reuse.

### F2 — the physical ICMP Driver is less generic than the architecture role

**Decision:** accepted  
**Resolution:** clarified

The subprocess/timeout/result-classification mechanics are reusable, but
`LinuxIcmpProbeDriver.check()` currently consumes an A.007-specific
`ProbeObservationContext`. The next reuse step should extract a protocol-neutral physical
execution context while retaining the A.007 wrapper behavior.

### F3 — C.001 needs a distinct owner-scoped peer-probe precondition

**Decision:** accepted  
**Resolution:** clarified

D.002 needs route/local-admission state for each permanent peer-specific /32 without creating
Profile/path identity. That requires a distinct peer-probe owner at the C.001 boundary, not
coercion into `ProbePolicyOwner`.

### F4 — D.003 is independently implementable and should precede D.002 production wiring

**Decision:** accepted  
**Resolution:** clarified

EV-00050 already selects complete desired `AllowedIPs` application with fresh exact
postcondition verification. D.003 does not need peer-selection policy or probe ownership and is
therefore the narrowest next production implementation unit.

## Verdict

**PASS for design/reuse boundary.** No D.002 materialization status changes in this review.
The next implementation unit should materialize D.003, then establish the narrow C.008/C.001
peer-probe reuse seam before implementing D.002 Manager selection/runtime composition.
