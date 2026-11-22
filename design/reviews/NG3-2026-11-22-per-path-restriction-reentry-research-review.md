# NG3 2026-11-22 — postponed per-path restriction re-entry research review

**Scope:** review the re-entry research for `VPNG-U001-R1.R4.R2.R1` and
`VPNG-U001-R4.R4.R6.R2.R5`.

**Research:** `design/NG3/research/NG3-2026-11-22-per-path-restrictions-reentry.md`

## Verdict

**PASS — KEEP BOTH NODES POSTPONED; THE REMAINING BLOCKER IS PRODUCT PATH ADDRESSABILITY,
NOT LOWER LINUX FIREWALL FEASIBILITY.**

## Findings

### F1 — current LogicalPathId is valid runtime identity but not a durable user selector

Accepted.

The current identity `(device_id, selector_index, slot_index)` is deliberately a binding
slot identity. Binding tests prove that slot membership is preserved for survivors during one
committed lifecycle, but initial process state is empty and prefix/quota admission is seeded
from fresh observation order.

Therefore exposing selector/slot ordinals as long-lived user policy would conflate an
internal runtime identity with the stable product identity required by
`VPNG-U001-R4.R4.R6.R2.R5`.

### F2 — endpoint provenance must not be resurrected as the public identity

Accepted.

Runtime ifname/ifindex or transport peer/endpoint may remain lower binding evidence, but the
user-facing selector must be a stable configured identity. Reintroducing endpoint provenance
as the policy key would contradict the current requirement purpose and the earlier
requirement refactor.

### F3 — a configured path key is the minimal clean product seam

Accepted as the preferred re-entry direction, not yet as normative grammar.

A Device-scoped opaque configured path key provides the required stable user reference while
allowing runtime binding to continue using current `LogicalPathId -> InterfaceIdentity`
semantics.

Exact TOML spelling is intentionally left for a subsequent configuration-format decision.

### F4 — quota>1 prefix selectors still require a product decision

Accepted.

Naming the internal slots does not make their external meaning stable across restart.
Individually addressable restrictions can be introduced safely first for binding selectors
whose path identity is already singular, or the product must add a durable sub-binding
discriminator for members of a multi-slot family.

The research correctly rejects persistence of incidental observation order as a substitute
for product identity.

### F5 — per-path policy must compose conjunctively

Accepted.

The correct semantic relation is:

```text
Profile permission
AND Device-wide restriction
AND optional path-specific restriction
```

Per-path policy is not an override and cannot widen Device or Profile permission.

The existing Device firewall already resolves each current `LogicalPathId` to its current
endpoint and emits path-specific lower chains, so no new packet/path discriminator experiment
is required. Lower composition will need an architecture/compiler extension because the
current single-chain first-match structure does not itself represent two independent
restrictive gates.

## Re-entry disposition

Do not change requirement status in this block.

Before re-entry, accept:

1. configured path key semantics;
2. the supported boundary for multi-slot selectors;
3. requirement decomposition for binding stability and conjunctive restriction;
4. the normalized-intent/C.001 composition architecture.

No additional Linux feasibility experiment is currently justified.
