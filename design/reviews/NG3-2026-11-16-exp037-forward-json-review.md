# NG3 — экспертное ревью EXP-037: final payload_forward JSON shape

**Дата:** 2026-11-16

## Scope

Parser-safety evidence only: no-counter owner rules and `/32` selector
representation. No runtime policy compiler or mutation.

## Findings / disposition

**F-01 — PASS.** Test instrumentation counters are absent from the final owner
shape and must not be accepted merely because EXP-035/036 used them.

**F-02 — PASS.** nft canonicalizes `/32` to an IPv4 string, while tested
broader prefixes use a `prefix` object. Both are unambiguous and can be
normalized strictly to `IPv4Network`.

**F-03 — PASS.** NEW state remains string `"new"`; RETURN state-set is the
two-element array `["established","related"]`. No broader state expression
is evidence-backed.

GitHub Actions
[43868540581](https://github.com/abyssdigger/vpn-gateway/actions/runs/43868540581)
completed SUCCESS with all regression jobs.

**FINAL VERDICT: PASS — observer implementation gate opened.**
