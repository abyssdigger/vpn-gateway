# NG3 — экспертное ревью EXP-035: exact-ifindex NEW-forward primitive

**Дата:** 2026-11-16  
**CD branch:** `ng3-design-cycle-20261116-forward-policy-evidence-40m`  
**Scope:** только нижний Linux/nft primitive для одного разрешённого NEW-flow.
Полная Profile filter policy вне scope.

## Traceability

**Implements:** `VPNG-U002-R2.R1.R2`, `VPNG-U002-R2.R3.R3`,
`VPNG-U002-R2.R5.R1`, `VPNG-U001-R1.R3.R2`,
`VPNG-U001-R1.R3.R3`, `VPNG-U004-R4.R1`,
`VPNG-U004-R4.R2`, `VPNG-U004-R4.R3.R2`.

**Constrained by:** `VPNG-U002-R2.R3.C1`,
`VPNG-U001-R1.R2.R4.R6.C1`.

Requirement and component gates are recorded in
`NG3-2026-11-16-exp035-forward-rule-gates.md`.
No new product semantics or external grammar were introduced.

## Evidence review

GitHub Actions run
[43867342131](https://github.com/abyssdigger/vpn-gateway/actions/runs/43867342131)
completed successfully. Existing unit suite: **302 PASS**.

The privileged `linux-payload-forward` job proved:

- baseline `payload_forward policy drop` denies traffic;
- numeric current `meta iif/oif` + `ct state new` +
  destination prefix matches the intended packet;
- different ingress does not match;
- different egress does not match even when destination remains in prefix;
- outside-prefix traffic does not match with same ingress/egress;
- same-name/new-ifindex replacement does not inherit the stale rule;
- live operands render as ifnames, stale operand as decimal-string ifindex.

The harness correctly used rule-counter deltas rather than a successful ping
as evidence, because return traffic was intentionally not admitted.

## Findings / disposition

**F-01 — ACCEPTED AS SCOPE BOUNDARY, NOT A DEFECT.**
The experiment proves only one outbound NEW primitive. It does not prove
stateful return-flow admission. Treating the positive counter result as a
complete bidirectional forwarding proof would be invalid. The result document
and architecture explicitly prohibit that interpretation.

**F-02 — ACCEPTED AS FUTURE DESIGN GATE.**
The tested destination-prefix rule does not establish correct composition of
overlapping Profiles. Most-specific Profile classification is semantic policy
and must remain above the lower Driver; independent nft rule order must not
become an accidental classifier.

**F-03 — ACCEPTED AS FUTURE EVIDENCE GATE.**
No evidence yet defines the exact lower primitive for permitted
`ESTABLISHED/RELATED` return traffic or inbound NEW traffic. Those must be
designed and tested before a full payload-forward parser/compiler is accepted.

No implementation defect in the experiment harness was found.
No rejected findings.

## Simplification

The experiment introduces no runtime component, state owner, retry loop,
general firewall AST, persistent handle registry or new configuration. It is
the minimum privileged test sufficient for the exact kernel/nft claim.

## Verdict

**PASS — EXP-035 establishes the tested outbound NEW lower primitive only.**

Next review unit should close the stateful return-flow primitive before any
claim of complete `payload_forward` owner classification or materialization.
