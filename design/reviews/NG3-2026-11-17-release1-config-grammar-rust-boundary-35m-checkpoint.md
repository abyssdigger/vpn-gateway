# NG3 35m checkpoint — canonical Release-1 config grammar + Rust target boundary

**Date:** 2026-11-17  
**Branch:** `ng3-beta-cycle-20261117-config-grammar-35m`  
**Baseline main:** `48587d41f8c7313081909a673ddcf2c7902e1ab8`

## Completed review unit

The postponed ordinary Release-1 configuration-format decision is resolved and implemented as
a strict canonical Adapter.

Canonical user surface:

- Device `use_outbound_nat`;
- Device `allow_vpn_client`;
- ordered one-line Device `firewall`;
- Device `publish_vpn_server`;
- Profile direction `+snat`;
- Profile `availability_check = "icmp[/IPv4]"`.

Historical aliases are not accepted. Public top-level `[integration.*]` was removed from the
canonical model.

The executable Python alpha now consumes the canonical parser. It materializes
`use_outbound_nat`, ordinary Device firewall and `allow_vpn_client`; it fails fast for
canonical capabilities whose complete lower alpha path is not yet assembled:
`availability_check`, Profile `+snat`, and `publish_vpn_server`.

The target production runtime implementation boundary is now Rust under
`VPNG0007-R7.R8`. Alpha/beta Python reference releases remain explicitly permitted by
`VPNG0007-R7.R8.C1`.

## Evidence

NG3 Python workflow run `44128242193` on
`4a8d2dfd30de5e2f11b2f17eb4bd052b04f2d099`: **PASS**.

- unit: 560 tests, OK;
- all Linux route/nft/policy jobs: PASS;
- EXP-049: PASS;
- EXP-050: PASS;
- EXP-051 installed systemd alpha with canonical config: PASS;
- VPN-only restart reconciliation: PASS;
- clean stack stop: PASS.

Canonical EXP-051 rerun record:
`design/experiments/EXP-051 NG3 first functioning alpha/EXP-051-result-20261117-canonical-config-pass.md`.

Review:
`design/reviews/NG3-2026-11-17-release1-config-grammar-rust-boundary-review.md`.

## Review findings fixed in-cycle

- corrected Profile NAT suffix from accidental `+masquerade` to accepted `+snat`;
- removed accidental inheritance of old firewall port ranges; Release 1 uses single ports;
- fixed a full-example cross-Device selector overlap caught by unit validation;
- stopped canonical Adapter from leaking lower `ConfigError`;
- removed stale architecture/config documentation claiming ordinary grammar was still
  postponed;
- correlated R7.R8 Purpose with its immediate implementation-quality parent rather than
  claiming Rust itself closes network fail-closed semantics.

## Final requirement inventory

Mechanical final check:

- normative R/C nodes: **159**;
- closed: **159**;
- pending_closure: **0**;
- rejected_closure: **0**;
- open: **0**;
- active `decomp`: **0**;
- active `unreal`: **0**;
- active `broken`: **0**;
- closed R/C without architecture reference: **0**.

Accumulated resolved decomp annotations: **6 occurrences**, all with concrete deblockers:

- `VPNG0005-R5 -> VPNG0005-R5.R6`;
- `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1` — two recorded occurrences;
- `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2` — two recorded occurrences;
- `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`.

Accumulated active/rejected exceptional state:

- `unreal`: none;
- `broken`: none;
- `[rejected_closure]`: none.

## Beta status

The configuration-format blocker is gone, but this checkpoint does **not** label the product
beta yet.

Next material beta work remains:

1. canonical `use_outbound_nat = true` real end-to-end payload evidence;
2. availability/effective-order/failover runtime assembly;
3. truthful operator status presentation;
4. completion or explicit beta-scope decision for canonical-but-current-alpha-rejected
   `+snat` and server publication.

The Rust rewrite is explicitly not an alpha/beta gate.

No CHANGELOG update was made during active NG3 development.
