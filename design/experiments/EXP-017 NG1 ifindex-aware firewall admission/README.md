# EXP-017 — NG1 ifindex-aware firewall admission

**Status:** PASS  
**Architecture baseline:** NG1 Draft 5 after 2026-11-12 safety correction  
**Type:** Linux netfilter/interface-generation experiment

## Question

Can NG1 bind firewall admission to one concrete Linux interface generation rather than to
a reusable interface name, so a same-name/new-ifindex replacement does not inherit policy
from its predecessor?

## Method

A disposable namespace created interface `vpn0` with generation A, installed nftables
rules using numeric `meta iif A` / `meta oif A`, proved traffic, deleted the interface,
then recreated the same name with generation B before changing the rules.

The experiment then changed ingress and egress generation rules independently.

## Result

PASS on GitHub Linux kernel/nftables integration runner.

Observed sequence:

1. **PASS A** — numeric iif/oif for generation A admitted the original interface.
2. **PASS B** — same-name generation B did not inherit old generation A iif/oif rules.
3. **PASS C** — adding only B's ingress rule admitted the request while stale A output
   still blocked the reply.
4. **PASS D** — adding B's output rule restored complete echo flow.

This proves that the nft kernel primitive is generation-specific.

## Observation finding

A second important result changed the verifier design.

nft JSON/text rendering may resolve a **live** numeric iif/oif back to the current
interface name:

```json
"right": "vpn0"
```

while a stale reference to the disappeared generation remains numeric.

Therefore production verification must **not** reconstruct generation identity solely from
the rendered meta-match right-hand value.

The experiment additionally proved a stable rule marker:

```text
comment "vpng-ifref:iif:<ifindex>"
```

The comment remains attached to the generation-specific rule and is visible in nft JSON
independently of symbolic interface rendering. Production NG1 therefore uses compiler-owned
`vpng-ifref:iif:N` / `vpng-ifref:oif:N` comments as its exact observable generation
markers while the underlying kernel match remains numeric meta iif/oif.

## Production consequence

- nftables is the NG1 production firewall/NAT backend.
- dynamic Device interface policy uses numeric ifindex;
- same-name/new-ifindex is a fresh lifecycle generation;
- generated dynamic-interface rules carry an exact compiler-owned generation comment;
- verifier checks complete policy semantics plus the generation-marker multiset;
- legacy iptables name matching remains historical/regression evidence only.

## Evidence note

The CI job containing the experiment initially remained red because the **subsequent**
production nft round-trip still assumed that live nft JSON always rendered numeric iif/oif.
EXP-017 itself had already printed PASS A/B/C/D. That downstream verifier defect is tracked
and corrected separately; it is not an EXP-017 failure.

## Decision

The original firewall-backend gate is closed: **PASS**.

No DeviceManager serialization workaround is required for same-name reuse. The production
backend can enforce NG1's `(ifname,ifindex)` generation model directly.
