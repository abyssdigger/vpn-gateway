# EXP-059 — NG3 paired RPDB bootstrap with suppress-prefixlength

## Status

COMPLETE — PASS — SELECTED.

## Question

Can VPN-GATE preserve ordinary main-table longest-prefix semantics without mutating or copying
main routes by using paired RPDB rules per managed Profile prefix?

For each managed prefix P, ordered most-specific first:

1. to P lookup main suppress_prefixlength prefixlen(P)
2. to P lookup the dedicated bootstrap table

A higher-priority ingress rule sends packets arriving from the managed boundary directly to main.
The dedicated bootstrap table contains only VPN-GATE managed routes to the stack.

This means a main route strictly more specific than P wins automatically, while an equal or
broader main route is suppressed and explicit Profile policy wins. Main route changes are observed
by the kernel on every lookup; VPN-GATE does not replicate them.

Stateful return remains a separate mark/table owner from EXP-053.

## PASS criterion

PASS requires:

1. main table stays byte-for-byte unchanged;
2. full-tunnel external traffic from host/ordinary LAN enters the managed stack;
3. connected LAN and uplink routes remain ordinary;
4. a more-specific static main route inside a broad managed prefix remains ordinary;
5. a nested managed prefix more specific than that static route wins and enters the stack;
6. adding a new more-specific main route after bootstrap activation is honored immediately without VPN-GATE mutation;
7. stack-origin traffic bypasses all bootstrap rules and uses main;
8. exact managed /32 equal to an external transport endpoint is directionally disambiguated;
9. cleanup removes only VPN-GATE table/rules and leaves main unchanged.