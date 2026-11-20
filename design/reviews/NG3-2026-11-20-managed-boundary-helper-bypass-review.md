# NG3 review — managed-boundary absolute helper bypass

**Date:** 2026-11-20  
**Branch:** `ng3-design-cycle-20261120-helper-routing-selectors-35m`  
**Finding:** former managed-boundary `lookup main` bypass was not absolute  
**Verdict:** **ACCEPTED FIX — use RPDB goto over helper range**

## Finding

The previous lower design treated

```text
iif <managed-boundary> lookup main
```

as if a match always removed the packet from later helper rules. Linux RPDB continues with
the next rule when a table lookup produces no route. Therefore `:external`/`:any` peaceful
dispatch, and the analogous aggressive dispatch, could recapture traffic emitted from STACK
when `main` had no usable route.

This violates the already accepted no-recapture behavior; it is not a new product decision.

## Fix

Use:

```text
iif <managed-boundary> goto <post-helper>
...
<post-helper>: nop
```

The jump skips every helper preserve/dispatch rule. `nop` resumes ordinary RPDB processing
after the reserved helper range, so VPN-GATE neither forces `main` nor captures the packet
back into STACK.

## Evidence

EXP-079 run `44759680923` / job `136368681135`: PASS, including the no-ordinary-route case
and the kernel JSON representation of `goto`/`nop`.

## Disposition

- Release-1 peaceful architecture corrected to the absolute bypass.
- The same lower fact is attached to postponed aggressive no-recapture behavior.
- No requirement wording or product scope changes.
- Implementation must use the absolute bypass before the scoped-dispatch block is accepted.
