# NG3 35m checkpoint — Release-1 port-bundle correction

**Date:** 2026-11-17  
**Branch:** `ng3-beta-cycle-20261117-port-bundles-35m`  
**Baseline main:** snapshot 73, `6877dcba7f1fc3115e749e9edd9eb26ebb27b4ae`

## Completed review unit

This cycle corrects the snapshot-73 single-port omission.

Release-1 now canonically supports compact ordered port bundles:

```text
port-bundle := item ("," item)*
item        := N | A-B
```

with:

- no whitespace inside a bundle;
- ports in `1..65535`;
- inclusive ascending ranges;
- no duplicate or overlapping physical ports;
- declared item order preserved.

Device firewall uses bundles as independent source/destination set-membership selectors.

Server publication uses the same bundle syntax:

- omitted internal bundle -> identity mapping;
- explicit internal bundle -> equal expanded cardinality + positional 1:1 mapping.

`allow_vpn_client` remains exact-port.

## Implementation

Added normalized `PortSpan` / `PortBundle` values and propagated them through:

- canonical Release-1 parser;
- normalized Device firewall intent;
- Device firewall compiler;
- Linux nft Device-firewall renderer;
- alpha canonical config consumption.

Firewall lower realization uses native nft operands:

```text
single exact   -> scalar
single range   -> range
mixed bundle   -> set containing exact/range operands
```

It does not expand ranges into one lower rule per port.

Publication parser retains ordered host/internal PortBundles and validates translation
cardinality. Full server-publication materialization remains a known later runtime unit.

## Findings fixed in-cycle

1. Snapshot-73 review incorrectly treated lack of re-discussion as intentional range removal.
   The old finding/checkpoint are retained but explicitly marked superseded.
2. The first expanded EXP-042 harness failed because nft set braces were unescaped inside a
   Python f-string; the harness was corrected.
3. After nft range/set JSON was proven, live mutation exposed a real lower gap:
   `linux_device_firewall.py` still accepted only integer port operands. The lower
   validator/renderer was extended narrowly to the evidenced scalar/range/set shapes and now
   re-validates bounds/order/overlap.

## Evidence

Primary code/evidence workflow:

- NG3 Python run: `44136005710`;
- source: `7616d1c7624cc1928325d0649f1ae86aa32d1b94`;
- result: **PASS**.

Evidence:

```text
Ran 563 tests
OK

EXP042_PORT_BUNDLE=1
EXP-042 Device firewall predicate JSON: PASS

NG3 live bounded guarded Device firewall mutation: PASS
```

All NG3 jobs in that run passed, including installed alpha smoke and EXP-049/050.

Dedicated evidence:
`design/experiments/EXP-042 NG3 Device firewall predicate JSON/EXP-042-result-20261117-port-bundle-pass.md`.

Review:
`design/reviews/NG3-2026-11-17-port-bundle-correction-review.md`.

## Requirement inventory

Final mechanical check before checkpoint:

- normative R/C nodes: **159**;
- closed: **159**;
- pending_closure: **0**;
- rejected_closure: **0**;
- open: **0**;
- active `decomp`: **0**;
- active `unreal`: **0**;
- active `broken`: **0**;
- closed R/C without architecture reference: **0**.

Accumulated resolved `decomp` annotations remain **6 occurrences**:

- `VPNG0005-R5 -> VPNG0005-R5.R6`;
- `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1` — two occurrences;
- `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2` — two occurrences;
- `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`.

Accumulated exceptional state:

- `unreal`: none;
- `broken`: none;
- `[rejected_closure]`: none.

## Stale-text audit

Current requirements/config-model/architecture/guidance/code were checked for stale
single-port grammar and singular Device-firewall port fields.

The only remaining `source_port?` / `destination_port?` architecture text belongs to the
separate local/system allow intent, where exact ports remain intentional. The historical
snapshot-73 review/checkpoint retain their old text only inside clearly marked superseded
correction notes.

## Beta status

This correction removes a configuration/runtime inconsistency but does not change the main
beta work list:

1. real `use_outbound_nat = true` end-to-end payload evidence;
2. availability/effective-order/failover runtime;
3. truthful operator status;
4. completion or explicit beta-scope decision for Profile `+snat` and server publication.

Rust remains a later production/stable implementation boundary, not an alpha/beta gate.

No CHANGELOG update was made during active NG3 development.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG0005-R5` -> `VPNG9101-R1.R1`
- `VPNG0005-R5.R6` -> `VPNG9101-R1.R1.R6`

The original IDs in the historical body are intentionally preserved.
