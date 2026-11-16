# EXP-036 — NG3 prefix-scoped stateful return primitive

**Status:** PASS on privileged GitHub Linux CI; lower primitive only.

Hypothesis: a return rule using `ct state established,related`, exact
current reverse iif/oif and the same remote source prefix admits replies for
an already permitted outbound flow without becoming a generic reverse
forwarding allowance. Same-name/new-ifindex replacement must invalidate the
old reverse primitive.

Evidence: `EXP-036-result-20261116.md`. This experiment does not define full Profile policy.
