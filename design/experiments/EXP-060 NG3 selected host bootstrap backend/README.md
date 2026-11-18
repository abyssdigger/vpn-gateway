# EXP-060 — NG3 selected paired-RPDB host bootstrap backend

## Status

PREPARED — evidence pending.

## Purpose

Validate the selected EXP-059 mechanism through production-shaped reference code:

canonical Release-1 config -> mechanism-neutral host-boundary plan -> selected Linux lowering
-> strict route/RPDB owner backend -> bounded convergence -> real route/packet checks -> cleanup.

## PASS criterion

PASS requires:

- full-tunnel ordinary traffic enters the managed stack;
- connected and more-specific main routes remain ordinary;
- nested managed prefixes override a broader ordinary route;
- a newly added more-specific main route wins immediately without VPN-GATE reconciliation;
- stack-origin traffic bypasses bootstrap through main;
- exact managed /32 equal to the configured VPN transport endpoint is supported without pins;
- backend fresh observation confirms exact owner state;
- cleanup removes all bootstrap owner routes/rules and leaves main unchanged.