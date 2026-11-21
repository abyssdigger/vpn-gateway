# NG3 evidence index

**Status:** normative stable evidence-address registry  
**Architecture:** `design/NG3/structured-architecture.md`

Evidence IDs are stable addresses. New top-level entries normally advance by 10
(`EV-00000`, `EV-00010`, ...); intermediate values may be inserted later without
renumbering existing references.

Architecture references the EV ID. Ephemeral CI run IDs, commit SHAs and concrete experiment
artifacts stay inside the EV entry or its linked review/result artifact.

## EV-00000 — lifecycle decomposition and implementation-trace baseline

**Status:** accepted  
**Scope:** decomposition of managed-network lifecycle into environment / managed-L3 boundary /
ordinary-side portal; independent host publication Adapter; initial bidirectional
architecture-to-code marker discipline.  
**Review:** `design/reviews/NG3-2026-11-21-partial-decomposition-lifecycle-review.md`  
**Reviewed implementation baseline:** `b35095144ceffa74265ce3b2e34a1680546903f2`  
**Executable evidence:** GitHub Actions `NG3 Python` run `44932489415` — PASS.  
**Stable architecture snapshot:** Main snapshot 151,
`2073808bc1ba61af9d79bdac1d97fccb9319fcf6`.

This entry preserves the concrete historical evidence without requiring stable architecture
text to depend on the workflow provider's run identifier.

