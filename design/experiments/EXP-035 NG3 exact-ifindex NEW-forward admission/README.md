# EXP-035 — NG3 exact-ifindex NEW-flow nft FORWARD admission

**Status:** PREPARED / UNPROVEN.
**Owner:** NG3 lower Linux nft implementation.
**Environment:** privileged GitHub Actions Linux runner, disposable netns.

## Hypothesis

An owned `payload_forward` chain with `policy drop` can safely admit
only one NEW IPv4 path using a rule with exact numeric
`meta iif` / `meta oif`, `ip daddr` prefix, `ct state new`,
and `accept`. When the interface is replaced with the same name
but new ifindex, the old rule does not automatically admit its traffic.

## Required evidence

1. Actual nft JSON expression shape after adding the rule.
2. Managed forwarding with rule absent is denied.
3. Matching NEW packets are admitted.
4. Different ingress, different egress and a destination outside
   the prefix are denied.
5. Replacing the egress interface with the same name but a different
   ifindex invalidates the old rule until the new physical rule is
   added.

The experiment must preserve default-drop and not infer a complete
Profile permission model, stateful return policy or multi-Profile
longest-prefix arbitration from the result.

## Result

PENDING. CI/harness evidence and architectural consequence to be
recorded without promoting test syntax to accepted production shape
until the result has been reviewed.
