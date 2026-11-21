# NG3 2026-11-22 — operational lifecycle closure review

**Scope:** `VPNG9101-R1`, `VPNG9101-R1.R1` and
`VPNG9101-R1.R1.R6`.

## Verdict

**PASS — ACCEPT ARCHITECTURE CLOSURE.**

## Finding

These nodes remained `pending_closure` after the purpose/parent refactor even though their
required behavior is already represented by the accepted lifecycle architecture and executable
evidence.

`A.001 ProductLifecycleControl` provides bounded start, stop and restart semantics and now
explicitly covers the migrated operational lifecycle parent requirements. Its replaceable
control-surface decision permits alpha to apply changed configuration through a supported
restart path; a distinct reload operation is not required by `VPNG9101-R1.R1.R6`.

## Evidence

Existing selected evidence is sufficient for this closure:

- EXP-050 proves bounded external lifecycle integration including
  `EXP050_CYCLE_2_RESTART_SAME_CONFIG=PASS` and
  `EXP050_CYCLE_2_RESTART_CHANGED_CONFIG=PASS`;
- EXP-051 proves installed alpha startup/readiness, runtime reconciliation, restart-safe VPN
  generation handling and confirmed cleanup;
- the current alpha deployment contract explicitly states that changed `config.toml` is
  applied by controller restart when reload is unavailable.

The closed descendants already establish startup postconditions, cleanup, independent cleanup
attempts, recoverable drift/retry and restart composition. No new implementation mechanism or
product semantic is required.

## Disposition

- `VPNG9101-R1.R1.R6`: close.
- `VPNG9101-R1.R1`: close after R6 closure; all current lifecycle responsibilities have
  accepted architecture.
- `VPNG9101-R1`: close as the complete operational lifecycle parent.

Their existing `decomposition` states are unchanged. In particular, decomposition-incomplete
descendants remain honestly marked incomplete; architecture closure is orthogonal to normative
decomposition completeness.

No new `decomp`, `unreal`, `broken` or `rejected_closure` state is introduced.
