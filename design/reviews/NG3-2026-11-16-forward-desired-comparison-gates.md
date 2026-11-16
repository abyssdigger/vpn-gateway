# NG3 — requirement/component gate: payload_forward lower desired comparison

**Дата:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-forward-policy-evidence-40m`

## Requirements

**Implements:** `VPNG0002-R2.R1.R1`, `VPNG0002-R2.R1.R2`,
`VPNG0002-R2.R3.R3`, `VPNG0002-R2.R5.R1`,
`VPNG0001-R1.R3.R2`, `VPNG0001-R1.R3.R3`,
`VPNG0004-R4.R1`, `VPNG0004-R4.R2`, `VPNG0004-R4.R5`.

**Constrained by:** `VPNG0002-R2.R3.C1`,
`VPNG0001-R1.R2.R4.R6.C1`.

All referenced ancestry remains closed with required Basis/Purpose/Reason and
Statements. This unit does not choose user-visible policy.

## Scenario

After authoritative observation, the structural owner needs to know whether
each exact physical forward rule is the already-requested lower state, missing,
or stale. The higher semantic compiler is an explicit input boundary and is
not fabricated here.

## Components / responsibilities

- immutable `PayloadForwardRuleSpec` / `PayloadForwardDesiredState`: exact
  lower data only;
- Direct Calculator `compare_payload_forward`: comparison only;
- existing strict observer: physical owner-shape/current-generation facts.

The comparator must never infer Profile direction, choose most-specific
Profile, apply Device envelope, or mutate nft.

## External environment

None beyond the already normalized observation/interface inputs. EXP-035–038
already prove representation.

## Constraints / lifting

Incomplete higher semantic compilation remains a development gate, not a
product constraint. The current useful product envelope is unchanged.

## Simplification

No semantic provenance in physical key, no handle in desired state, no cache,
I/O, async state, retry, generic firewall AST or mutation.

## Evidence

Rootless deterministic tests; existing full CI. Expert review must explicitly
check that observer “recognized” is never promoted to desired/current policy.

**Gate verdict: PASS for lower desired/comparison. Physical mutation and full
Profile/Device compiler remain GATED.**
