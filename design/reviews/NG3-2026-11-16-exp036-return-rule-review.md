# NG3 — экспертное ревью EXP-036: prefix-scoped stateful return

**Дата:** 2026-11-16  
**Branch:** `ng3-design-cycle-20261116-forward-policy-evidence-40m`

## Traceability

**Implements:** `VPNG-U002-R2.R1.R2`, `VPNG-U002-R2.R3.R3`,
`VPNG-U001-R1.R3.R2`, `VPNG-U001-R1.R3.R3`,
`VPNG-U004-R4.R1`, `VPNG-U004-R4.R2`, `VPNG-U004-R4.R3.R2`.

**Constrained by:** `VPNG-U002-R2.R3.C1`,
`VPNG-U001-R1.R2.R4.R6.C1`.

Gate: `NG3-2026-11-16-exp036-return-rule-gates.md`.

## Findings

**F-01 — ACCEPTED AS DESIGN DECISION.**
A generic pair-wide established/related rule would discard current remote-prefix
scope. The tested primitive correctly repeats that prefix on the reverse
direction, preserving fail-closed behavior under policy narrowing.

**F-02 — ACCEPTED AS SCOPE BOUNDARY.**
The experiment covers outbound NEW plus its return. It does not itself prove
the complete inbound NEW compiler. It does prove the two nft expression
families required by a generic strict observer: NEW state with one remote-prefix
field and RETURN state-set with the reverse remote-prefix field.

**F-03 — ACCEPTED AS OBSERVER REQUIREMENT.**
Live interface operands render as names and stale generation operands as decimal
ifindices. Parser equality on textual names is invalid; normalization must use
one fresh unambiguous `InterfaceIdentity` snapshot.

No harness defect found. No rejected findings.

## Evidence

GitHub Actions
[43867923312](https://github.com/abyssdigger/vpn-gateway/actions/runs/43867923312):
workflow SUCCESS; EXP-035 PASS; EXP-036 PASS; existing regressions PASS.

## Verdict

**PASS — prefix-scoped stateful return accepted as lower technical evidence.**
Full Profile forward-policy compilation and mutation remain gated.
