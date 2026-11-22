# NG3 2026-11-22 — aggressive full-tunnel guard review

**Scope:** review EXP-085 as a prerequisite for E.004 implementation.

## Verdict

**PASS — FULL-TUNNEL ESCAPE-PROTECTION SEMANTICS ARE SUFFICIENTLY CONSTRAINED FOR
PRODUCTION E.004 WORK.**

### F1 — EXP-084 was insufficient for full-tunnel scope

**Decision:** accepted.  
**Resolution:** fixed by EXP-085.

The prefix-scoped EXP-084 guard would over-match when the managed set becomes `0.0.0.0/0`.
Without explicit exemptions it could block host-local delivery and traffic already handed
from VPN-GATE to the ordinary network.

### F2 — the selected exemptions preserve the requirement boundary

**Decision:** accepted.  
**Resolution:** fixed.

EXP-085 proves the full-tunnel candidate can preserve host-local delivery and
managed-boundary-originated return traffic while still dropping local/forwarded managed
outbound traffic whose effective egress is redirected to an ordinary uplink.

The exemptions therefore preserve the non-recapture semantics of
`VPNG-U001-R5.R2.R1` rather than weakening fail-closed escape protection.

### F3 — production E.004 may now encode the guard

**Decision:** accepted.

The production implementation must keep these semantics explicit and mechanically observed;
it must not merely copy the narrower EXP-084 rules.

E.004 remains `<partial>` until that production implementation and its effective-routing
verification are complete.
