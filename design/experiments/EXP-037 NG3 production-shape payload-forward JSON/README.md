# EXP-037 — NG3 production-shape payload_forward JSON

**Status:** PASS on privileged GitHub Linux CI.

## Hypothesis

The final lower owner shapes can omit packet counters while retaining the
EXP-035/036 semantics, and nft JSON has an unambiguous representation for
IPv4 `/32` remote selectors in both `ip daddr` NEW and `ip saddr`
RETURN rules.

## Scope

Disposable Linux namespace only. Create one no-counter NEW rule and one
no-counter RETURN rule with `/32` selectors, list canonical JSON, and verify
the expressions/actions and owner comments. Packet semantics are already
covered by EXP-035/036; this experiment closes parser representation only.

PASS evidence: `EXP-037-result-20261116.md`. The result authorizes the strict read-only observer shape, not full policy materialization.
