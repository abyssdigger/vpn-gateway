# EXP-065 — NG3 probe RPDB selector shape

## Purpose

Pin the current Linux/iproute2 representation and lookup behavior for the already selected
Release-1 probe-routing discriminator recovered from EXP-022:

```text
uidrange + ipproto icmp + exact target -> dedicated probe table
```

This experiment resolves a lower implementation inconsistency. EXP-029 used an arbitrary
`fwmark/fwmask` probe selector to prove generic reserved-namespace inventory shape; it did
not select the production probe-routing discriminator.

## Scenario

Inside a disposable network namespace:

1. create one current probe path interface;
2. install one target /32 route plus terminal blackhole in the first reserved probe table;
3. install one probe-priority RPDB rule with exact UID range, ICMP protocol and target;
4. record `ip -j -N -4 rule show`;
5. verify a matching route lookup selects the probe table and a non-matching UID does not.

## Acceptance

The experiment must establish:

- the exact JSON field representation needed by the authoritative structural observer;
- the selected rule can be installed in the accepted probe RPDB priority/table ranges;
- matching UID/protocol/target lookup reaches the dedicated probe route;
- a different UID does not use that probe rule.

No host state is modified.
