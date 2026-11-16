# EXP-041 — ordered Device firewall child-chain primitives

## Purpose

Prove the Linux/nftables lower primitives required by the already accepted NG3 ordered
Device-firewall composition without selecting external configuration grammar or final
protocol-specific REJECT semantics.

The experiment covers:

- exact jump from `payload_forward` into one owned Device child chain;
- preservation of child-chain rule order in nft JSON;
- `return` meaning "continue in payload_forward to the Profile hard gate";
- terminal child-chain `drop` meaning explicit-policy no-match fail-closed;
- an owned `reject` rule JSON/action primitive as evidence only.

## Requirements

- `VPNG0001-R1.R2.R4.R6.R2`;
- `VPNG0001-R1.R2.R4.R6.R2.R1`;
- `VPNG0001-R1.R2.R4.R6.R2.R2`;
- `VPNG0001-R1.R2.R4.R6.R2.R3`;
- `VPNG0001-R1.R2.R4.R6.R2.R4`;
- `VPNG0004-R4.R1`;
- `VPNG0004-R4.R2`.

## Candidate lower shape

The test uses one disposable Device child chain:

```text
payload_forward
    exact managed host/path pair -> jump device_fw_exp041
    exact Profile NEW permission -> accept
    policy drop

device_fw_exp041
    ordered explicit rules
    ...
    terminal drop for explicit-policy no-match
```

An ALLOW-like Device rule is represented by `return`, never by `accept`.

The experiment does **not** define stable production child-chain naming. It also does not
define the final mapping from normalized `REJECT` to protocol-specific nft reject forms.

## Procedure

A disposable three-namespace forwarding topology is created.

1. Create the marked NG3 nft table and `payload_forward policy drop`.
2. Create one ordinary Device child chain with owner comments on all test rules.
3. Add an exact host/path jump before the Profile hard-gate allow.
4. Verify a matching child `drop` blocks traffic that the Profile rule would otherwise
   accept.
5. Replace that matching action with `return`; verify the same traffic reaches the later
   Profile allow and succeeds.
6. Verify an unmatched packet hits the explicit-policy terminal `drop`.
7. Add a non-conflicting test-only `reject` rule and capture its nft JSON.
8. Read the full ruleset JSON and assert jump target, action primitives, comments and exact
   rule ordering.

## Decision

PASS opens a later strict owner-observation/desired-state unit for Device child chains.

PASS does not authorize physical production mutation, choose external Device-firewall
syntax, or close the separate protocol-appropriate REJECT realization gate.
