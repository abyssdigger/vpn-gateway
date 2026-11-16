# NG3 — экспертное ревью exact payload_forward desired/comparison

**Дата:** 2026-11-16  
**CD branch:** `ng3-design-cycle-20261116-forward-policy-evidence-40m`  
**Scope:** exact lower desired rule data and pure actual-vs-desired comparison.
No Profile/Device semantic compiler and no nft mutation.

## Traceability

**Implements:** `VPNG0002-R2.R1.R1`, `VPNG0002-R2.R1.R2`,
`VPNG0002-R2.R3.R3`, `VPNG0002-R2.R5.R1`,
`VPNG0001-R1.R3.R2`, `VPNG0001-R1.R3.R3`,
`VPNG0004-R4.R1`, `VPNG0004-R4.R2`, `VPNG0004-R4.R5`.

**Constrained by:** `VPNG0002-R2.R3.C1`,
`VPNG0001-R1.R2.R4.R6.C1`.

Gate:
`design/reviews/NG3-2026-11-16-forward-desired-comparison-gates.md`.

## Reviewed implementation

- `payload_forward_desired.py` — exact immutable physical rule specs;
- `payload_forward_compare.py` — pure comparison;
- `test_payload_forward_compare.py`;
- package export and reference-scope README.

The desired model contains only fields that are physically part of the
already-proven lower nft rule identity: kind, current ingress/egress identity,
remote address field and strict IPv4 prefix. Profile/Device IDs and kernel
handles are deliberately absent.

## Findings / disposition

**F-01 — PASS.**
A recognized rule with current interface identities is not automatically
confirmed. `compare_payload_forward` confirms only an exact key present in
the explicitly supplied lower desired state; every other recognized rule is
stale. This preserves the observer review boundary.

**F-02 — PASS.**
A desired rule whose endpoint is not present in the same fresh interface
inventory is rejected as invalid input. The comparison therefore cannot turn a
stale/same-name endpoint assumption into a missing-rule request for mutation.

**F-03 — PASS.**
Duplicate desired physical rules are rejected and the desired tuple is
canonicalized independently of caller collection order. This matches the
set-like policy semantics and prevents duplicate physical materialization
from becoming hidden ordering policy.

**F-04 — ACCEPTED AS SCOPE BOUNDARY.**
The physical desired model intentionally has no Profile/Device provenance.
That is correct only because this unit does not compile policy. A future
semantic compiler must perform Profile most-specific classification, direction,
path eligibility and Device-envelope intersection **before** producing these
deduplicated physical specs. The lower comparator must not be extended to
make those choices.

**F-05 — ACCEPTED AS FUTURE GATE.**
Rule order is not modeled in lower desired identity. All accepted shapes here
are positive `accept` rules under a default-drop base chain. If a future
compiler introduces ordering-sensitive deny/mark/jump behavior, this lower
contract must be redesigned rather than silently reusing the unordered model.

No rejected findings. No open accepted defects in this unit.

## Evidence

Final code GitHub Actions:
[run 43870953291](https://github.com/abyssdigger/vpn-gateway/actions/runs/43870953291).

- **344 unit tests PASS**;
- all 9 workflow jobs SUCCESS;
- EXP-035…038 PASS;
- live strict payload_forward observation PASS.

No new external/kernel claim is introduced by the pure comparison itself.

## Simplification verdict

No I/O, mutation, profile compiler, Device-envelope model, rule handle in
desired state, lifecycle owner, retry/history/cache or general firewall AST.

## Final verdict

**PASS — exact lower payload_forward desired state and actual-vs-desired
comparison are accepted.**

Physical filter mutation remains gated. The next design problem is the higher
semantic compiler that maps complete Profile/Device permission into this lower
desired set; it must not guess the unresolved Device-envelope lower contract.
