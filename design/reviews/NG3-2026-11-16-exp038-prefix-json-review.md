# NG3 — экспертное ревью EXP-038: prefix-boundary representation

**Дата:** 2026-11-16

## Findings / disposition

**F-01 — PASS.** `0.0.0.0/0` survives as an explicit payload-prefix
match; observer does not need a special missing-expression semantic case.

**F-02 — PASS.** All tested non-/32 boundaries use the same exact prefix
object schema. `/32` uses a plain IPv4 string. This gives a closed,
strict normalization rule for the full accepted IPv4 prefix-length range.

**F-03 — PASS.** NEW daddr and RETURN saddr share the same canonicalization,
so no separate parser family is required for remote-field direction.

No product requirement or user-facing syntax changed.

**FINAL VERDICT: PASS — strict payload_forward observer gate opened.**
