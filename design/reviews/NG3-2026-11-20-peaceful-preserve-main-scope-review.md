# NG3 review — peaceful preserve-main scope finding

**Date:** 2026-11-20  
**Branch:** `ng3-design-cycle-20261120-helper-routing-finalize-30m`  
**Affected:** `VPNG-U001-R2`, `VPNG-U001-R2.R2`  
**Finding:** global preserve-main rule affects routing outside selected helper scope  
**Verdict:** **CONFIRMED — ARCHITECTURE CORRECTED, IMPLEMENTATION PENDING**

## Finding

The previous peaceful lowering scoped only helper dispatch. Its earlier global
`lookup main suppress_prefixlength 0` could select an explicit non-default `main` route for
traffic outside helper scope before a later administrator RPDB rule that normally precedes
the kernel `main` rule.

That violates the parent non-interference requirement even though the packet is not captured
into VPN-GATE.

## Evidence

EXP-080 run `44772483578` reproduced the old interference and proved that matching
preserve-main to the same selector as dispatch restores unselected administrator RPDB
behavior while preserving selected explicit-main precedence.

## Required fix

Materialize one selector-specific preserve+dispatch pair per effective peaceful selector.
The managed-boundary absolute `goto` bypass from EXP-079 remains unchanged.

`VPNG-U001-R2.R2` is returned to [`pending_closure`] until implementation and regression
evidence match this corrected lowering.
