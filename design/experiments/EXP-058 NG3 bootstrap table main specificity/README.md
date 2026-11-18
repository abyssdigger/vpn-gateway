# EXP-058 — NG3 dedicated bootstrap table preserving ordinary main specificity

## Status

PREPARED — evidence pending.

## Question

Can VPN-GATE avoid all host main mutations while preserving the same longest-prefix behavior
that conventional VPN routes get naturally from main?

Selected candidate:

- bootstrap nft classifier marks ordinary/local packets whose destination belongs to managed Profile destinations;
- packets arriving from the managed boundary are never bootstrap-marked;
- one bootstrap RPDB fwmark rule selects a dedicated bootstrap table;
- that table contains managed routes plus throw routes for ordinary main prefixes that are strictly more specific than a covering managed prefix.

A throw route terminates lookup in the bootstrap table and lets RPDB continue to ordinary main.
A more-specific managed route in the same bootstrap table still wins over a broader throw.

Stateful return is intentionally not part of this table; EXP-053's return mark/table remains
a separate owner because return steering must force an already-associated flow back to the stack.

## PASS criterion

PASS requires one run to prove:

1. host main table is unchanged;
2. ordinary host/LAN traffic to an external full-tunnel destination enters the stack;
3. ordinary traffic to directly connected LAN stays ordinary despite full-tunnel capture;
4. host traffic to directly connected uplink stays ordinary;
5. a pre-existing more-specific static main route inside a managed broad prefix stays ordinary;
6. a still-more-specific managed route nested inside that static prefix wins and enters stack;
7. packets originating from the managed stack bypass bootstrap marking and use main;
8. exact managed /32 equal to an external endpoint is directionally disambiguated without a pin;
9. cleanup removes only the owned bootstrap table/rule/nft state.

A PASS permits replacement of the conservative EXP-054 pin/main-route implementation by this
non-invasive dedicated-table model.