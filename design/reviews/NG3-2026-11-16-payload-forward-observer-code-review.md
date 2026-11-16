# NG3 — экспертное ревью authoritative payload_forward observer

**Дата:** 2026-11-16  
**CD branch:** `ng3-design-cycle-20261116-forward-policy-evidence-40m`  
**Scope:** strict read-only owner-shape observation of `payload_forward`.
No desired-policy compilation, mutation or forwarding activation.

## Traceability

**Implements:** `VPNG0002-R2.R1.R2`, `VPNG0002-R2.R3.R3`,
`VPNG0002-R2.R5.R1`, `VPNG0001-R1.R3.R2`,
`VPNG0001-R1.R3.R3`, `VPNG0004-R4.R1`,
`VPNG0004-R4.R2`, `VPNG0004-R4.R5`.

**Constrained by:** `VPNG0002-R2.R3.C1`,
`VPNG0001-R1.R2.R4.R6.C1`.

Design gate:
`design/reviews/NG3-2026-11-16-forward-observer-gates.md`.

External representation evidence:
EXP-035, EXP-036, EXP-037 and EXP-038.

## Reviewed implementation

- `payload_forward_observation.py`;
- `test_payload_forward_observation.py`;
- `integration_payload_forward_observation.py`;
- package export and reference-scope README.

The Calculator has no I/O and accepts only:

- exact marked `payload_forward` scope;
- NEW owner comment + exact `ct state new`;
- RETURN owner comment + exact `ct state established,related`;
- exact iif/oif matches;
- one IPv4 saddr/daddr remote selector;
- evidence-backed prefix representation for the full prefix-length range;
- plain accept;
- no test-only counter or arbitrary additional expression/field.

Current names and decimal indices are normalized through a fresh unambiguous
interface inventory. A vanished numeric generation remains stale and cannot
equal a same-name current replacement.

## Findings / disposition

**F-01 — ACCEPTED + FIXED.**
Initial API fields were named `current` and `stale`. Although technically
intended to mean interface-generation currency, `current` could be
misinterpreted by a downstream Executor as “desired current policy”.
Commit `34692da3b952f6c719cb08aea606fc304ccd518b` renamed them to
`current_identity_rules` / `stale_identity_rules` and documented that
`recognized` and `conflict_free` are owner-shape/local observations only.
They do **not** authorize deletion, preservation as desired state, or
forwarding activation.

**F-02 — ACCEPTED AS INTENTIONAL STRICTNESS.**
The observer rejects counter-bearing rules even though EXP-035/036 used
counters. EXP-037 proved the final production shape without counters; counters
were experimental instrumentation and no accepted requirement needs them.
Rejecting them avoids widening owner/deletion authority.

**F-03 — ACCEPTED AS SCOPE BOUNDARY.**
The observer intentionally allows either remote field with either NEW/RETURN
kind because it is a lower parser capable of representing outbound and inbound
physical forms. It does not infer Profile direction from rule order or choose
which recognized rule is desired. That responsibility remains with the
higher pure policy projection/comparison.

**F-04 — ACCEPTED AS FUTURE GATE.**
Recognition of an owner shape alone cannot prove a rule belongs to the current
semantic policy. Before physical filter cleanup/materialization, a complete
desired projection and actual-vs-desired comparison are mandatory.

No rejected findings. No open accepted defects in this review unit.

## Evidence

GitHub Actions `NG3 Python` on final exported code:
[run 43870148272](https://github.com/abyssdigger/vpn-gateway/actions/runs/43870148272).

- **327 unit tests PASS**;
- all workflow jobs SUCCESS;
- EXP-035 exact NEW primitive PASS;
- EXP-036 prefix-scoped stateful return PASS;
- EXP-037 no-counter /32 JSON PASS;
- EXP-038 /0,/1,/31,/32 boundary JSON PASS;
- live strict observer + same-name stale generation PASS.

## Simplification verdict

No new Manager, Agent, persistent state, desired compiler, mutation Driver,
retry loop, firewall AST or event contract. The component remains a pure
Direct Calculator over explicit inputs.

## Final verdict

**PASS — authoritative strict payload_forward owner observation is accepted.**
Next independent unit: complete pure desired forward-rule projection and
actual-vs-desired comparison. Physical filter mutation remains gated.
