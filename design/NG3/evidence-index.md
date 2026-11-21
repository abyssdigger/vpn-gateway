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



## EV-00010 — lower-boundary roles and complete bidirectional traceability

**Status:** accepted  
**Scope:** reusable lower-boundary applicability decision; role-correct Driver/Reader/Backend
classification; exact-contract nft Reader reuse; complete closed requirement -> structured
architecture entry-point invariant; structured production-runtime language boundary.  
**Review:** `design/reviews/NG3-2026-11-21-lower-boundary-reuse-trace-cdc.md`  
**Reviewed implementation baseline:** `f2e045285510c8d202db95efef450811bfcdfa87`  
**Executable evidence:** GitHub Actions `NG3 Python` run `44949136760` — PASS,
21/21 jobs; unit suite 790 tests PASS.  
**Trace invariants:** 144/144 closed Requirement/Constraint IDs have a structured architecture
entry point; 109/109 production Python units are present in the implementation trace manifest.

The evidence confirms that the terminology/reuse comb did not change required network
behavior and that the completed traceability rules are mechanically enforced.
