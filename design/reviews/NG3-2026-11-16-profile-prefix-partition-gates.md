# NG3 — requirement/component gate: Profile most-specific CIDR partition

**Дата:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-forward-policy-evidence-40m`

## Requirements

**Implements:** `VPNG-U002-R2.R1.R2`, `VPNG-U002-R2.R3.R3`,
`VPNG-U002-R2.R5.R1`, `VPNG-U004-R4.R1`.

Full ancestry and closure were rechecked. The required semantic is already
unambiguous: outbound selects globally by most-specific remote destination;
inbound first restricts candidates by actual ingress path, then selects by
most-specific remote source.

**Requirement gate: PASS.**

## Component design

**Scenario:** overlapping Profile destinations must be compiled into positive
lower allow rules without a broad Profile accidentally authorizing traffic that
belongs to a more-specific Profile.

**Component:** pure Calculator producing disjoint Profile-owned IPv4Network
fragments. It reuses `PayloadProfileRequest` and `LogicalPathId`; no new
persistent state or external boundary.

**Interactions:** none. Higher semantic projection consumes fragments.
Device envelope is intentionally downstream and may only narrow them.

**Traceability:** global outbound partition implements R2.R1.R2/R2.R5.R1;
per-ingress inbound candidate restriction implements R2.R1.R2; direction
filtering implements R2.R3.R3; duplicate/ambiguous exact ownership fails
rather than widening permission per R4.R1.

**Constraints:** this result is not final effective permission. It does not
close Device envelope or physical nft compiler gates.

**Simplification:** stdlib `IPv4Network.address_exclude` +
`collapse_addresses`; no trie/framework/order-sensitive rules.

**Evidence plan:** deterministic unit tests and exhaustive point-equivalence
inside small CIDR domains against existing point classifiers.

**Component-design gate: PASS.**
