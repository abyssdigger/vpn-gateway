# NG3 deferral — user-facing policy grammar

**Status:** POSTPONED INTERFACE DECISION  
**Created:** 2026-11-16  
**Applies to:** Release-1 development, before final parser/CLI acceptance

## Why this is a deferral, not an open product requirement

The current NG3 requirement tree already fixes the relevant semantics and constraints.
What remains undecided is the exact compact human-facing encoding.

The affected semantic capabilities are:

- Device VPN-side NAT intent exact spelling;
- ordered Device firewall rules;
- named VPN endpoint declarations/selectors;
- Profile ordinary-side gateway NAT;
- Device transport publication where exact NG3 spelling is still unresolved;
- Profile availability-check exact external field/string spelling and any future user-facing
  timing/unit knobs not already required by the accepted semantic contract.

The governing constraints explicitly prohibit guessing historical prototype spelling:

- `VPNG0001-R1.R2.R4.R6.C1`;
- `VPNG0001-R1.R2.R4.R4.R4.C1`;
- `VPNG0001-R1.R2.R4.R6.R2.R5.C1` for endpoint-scoped firewall syntax.

No product promise is missing merely because punctuation/compact serialization has not yet
been selected.

## Current accepted semantic inputs

The later configuration-format review must preserve, at minimum:

### Device VPN-side NAT

- semantic modes are already `NONE | MASQUERADE`;
- active Device NAT intent remains explicit;
- exact external field/value spelling remains an interface decision.

### Device firewall

- exact user order;
- `IN | OUT`;
- `ALLOW | DENY | REJECT`;
- optional protocol;
- optional source/destination ports;
- optional source/destination IPv4 CIDRs;
- optional comment;
- omitted firewall => permissive Device layer;
- explicit policy no-match => DROP;
- optional future logical endpoint selector when provenance is supported.

### Named endpoint

A durable user-facing endpoint identity, when introduced, must not be a runtime ifname.
It must resolve through accepted transport-endpoint provenance/current path binding.

### Profile ordinary-side gateway NAT

The encoding must represent explicit opt-in/opt-out Profile intent and must not conflate this
with Device VPN-side `masquerade`.

### Availability-check surface

- Profile/path-scoped ICMP semantics and optional target semantics are already accepted;
- explicit target must be preserved exactly and omitted target must normalize deterministically;
- historical `interface_balancing = "icmp[/ip]"` spelling is evidence only;
- no user-facing timing/unit field is required merely because runtime code has internal
  cadence/hysteresis values.

### Publication

The encoding must preserve accepted publication ownership and collision semantics without
silently inheriting obsolete prototype syntax.

## Explicitly not selected now

No decision is made here about:

- slash/comma/quote compact grammar;
- whether the historical Device `nat = "none|masquerade"` spelling is retained;
- exact availability-check field spelling and any optional timing/unit presentation;
- TOML scalar versus array/table representation;
- exact field names for the new firewall or endpoint declarations;
- named-endpoint path syntax;
- gateway-NAT field spelling;
- publication shorthand.

Those are user-visible schema choices and require the dedicated configuration-format review.

## Re-entry condition

This deferral becomes active work when **either**:

1. implementation of one of the affected parser/config surfaces becomes the next bounded
   development unit; or
2. the user explicitly asks to settle the compact configuration notation.

At re-entry, the review must compare the smallest viable candidate grammars against the
accepted semantics and existing "magic slash/quote/comma" style, then obtain human acceptance
for the user-visible schema before parser implementation.

## Blocking scope

This deferral blocks only parser/serialization and documentation that require the final
external grammar.

It does **not** block:

- normalized semantic architecture;
- lower nft/kernel evidence;
- pure policy compilation from already-normalized inputs;
- endpoint-provenance experiments;
- owner/observation/mutation design that is independent of external spelling.

## Requirement-state inventory

- active `decomp`: none;
- active `unreal`: none;
- `[rejected_closure]`: none.
