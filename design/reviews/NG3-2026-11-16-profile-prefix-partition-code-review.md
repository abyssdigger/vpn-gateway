# NG3 — экспертное ревью Profile most-specific CIDR partition

**Дата:** 2026-11-16  
**CD branch:** `ng3-design-cycle-20261116-forward-policy-evidence-40m`  
**Scope:** pure bulk Profile classification into disjoint IPv4 CIDR fragments.
No Device-envelope intersection, nft compilation, mutation or forwarding activation.

## Traceability

**Implements:** `VPNG0002-R2.R1.R2`, `VPNG0002-R2.R3.R3`,
`VPNG0002-R2.R5.R1`, `VPNG0004-R4.R1`.

Gate:
`design/reviews/NG3-2026-11-16-profile-prefix-partition-gates.md`.

The unit is a bulk representation of semantics already implemented by
`classify_outbound_profile` and `classify_inbound_profile`:
outbound most-specific selection is global over outbound/bidirectional
candidates; inbound first restricts candidates by actual ingress path and then
uses most-specific remote-source selection.

## Reviewed implementation

- `profile_prefix_partition.py`;
- `test_profile_prefix_partition.py`;
- package export and reference-scope README.

The Calculator uses only strict `IPv4Network`, CIDR subtraction and final
same-owner collapse. Output fragments are pairwise disjoint and carry only
`profile_id + remote_prefix`. They are Profile permission, not final
effective permission.

## Findings / disposition

**F-01 — ACCEPTED + FIXED.**
The first implementation collapsed nested destinations belonging to one
Profile **before** subtracting prefixes of other Profiles. This is wrong for
alternating specificity, for example:

```text
A: 0.0.0.0/0
B: 0.0.0.0/1
A: 64.0.0.0/3
```

The nested A /3 is semantically significant because it regains ownership from
B /1 under most-specific selection. Initial GitHub Actions run
[43872060442](https://github.com/abyssdigger/vpn-gateway/actions/runs/43872060442)
correctly failed the new regression.

Commit `a78aa8e9030aa32e7035bb2d726ecabf4dab4dc3` fixes the algorithm:
all original semantic prefixes remain until cross-Profile subtraction;
only final already-disjoint fragments of one owner are collapsed.
The final run proves the corrected behavior.

**F-02 — PASS.**
Outbound exhaustive point-equivalence checks compare every IPv4 address in a
bounded test domain against `classify_outbound_profile`, including nested
three-owner specificity.

**F-03 — PASS.**
Inbound exhaustive equivalence is tested separately for multiple ingress
paths. A more-specific Profile on another Device/path does not shadow a valid
broader Profile on the current ingress, while a more-specific candidate that
does allow the ingress correctly wins.

**F-04 — PASS.**
Exact duplicate destination ownership among candidate Profiles is rejected,
duplicate Profile IDs and repeated destinations inside one Profile are
rejected, invalid direction/ingress and IPv6 inputs fail explicitly.
Result ordering is independent of request input order.

**F-05 — ACCEPTED AS SCOPE BOUNDARY.**
The partition does not apply Device traffic envelope. It must not be described
as final effective permission. The envelope remains a downstream restrictive
intersection and the complete semantic-to-nft compiler remains gated on its
normalized contract.

**F-06 — SIMPLIFICATION ACCEPTED.**
No persistent trie, ACL framework, rule ordering, deny graph or runtime lookup
state is required. Standard CIDR subtraction plus final collapse is sufficient
for the accepted finite IPv4 Profile input and is directly testable against the
existing point classifiers.

No rejected findings. No open accepted defects in this unit.

## Evidence

Final exported code:
GitHub Actions
[43872533382](https://github.com/abyssdigger/vpn-gateway/actions/runs/43872533382).

- **363 unit tests PASS**;
- **9/9 workflow jobs SUCCESS**;
- EXP-035/036/037/038 PASS;
- live strict `payload_forward` observer PASS;
- all pre-existing route/NAT/scaffold/barrier/platform integrations PASS.

The earlier failing run is retained as evidence of the defect and its
regression, not hidden by the later green run.

## Final verdict

**PASS — Profile most-specific CIDR partition Calculator is accepted.**

The next unit must not silently claim complete forward-policy compilation:
Device-envelope normalization/lower intersection remains the explicit gate.
