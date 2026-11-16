# EXP-038 — NG3 payload_forward IPv4 prefix-boundary JSON

**Status:** PASS on privileged GitHub Linux CI.

## Question

How does the current nftables target canonicalize no-counter
`ip daddr` / `ip saddr` matches for strict IPv4 prefixes at the
important boundaries `/0`, `/1`, `/31`, and `/32`?

In particular, does `0.0.0.0/0` survive as an explicit payload match or
is it optimized out?

## Scope

Disposable namespace; exact production NEW/RETURN rule skeletons only.
Record complete JSON for both remote fields at each prefix length.
No packet semantics are inferred beyond EXP-035/036.

PASS evidence: `EXP-038-result-20261116.md`. Observer implementation gate is opened by the reviewed result.
