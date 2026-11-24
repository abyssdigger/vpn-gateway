# EXP-029 — NG3 structural routing inventory shape

## Purpose

Discover and pin the current numeric JSON representation produced by:

```text
ip -j -N -4 route show table all
ip -j -N -4 rule show
```

for the already accepted NG3 high table/RPDB resource space.

The structural inventory parser is intentionally not implemented until this evidence is
available.

## Scenario

Inside a disposable network namespace the harness creates:

- one payload high-ID table with:
  - one managed unicast path route;
  - one terminal blackhole guard;
- one probe high-ID table with one managed route;
- one probe RPDB rule using `fwmark/mask`;
- one payload RPDB rule using `iif + to`.

It then prints only the selected managed rows from the full numeric JSON inventories.

## Hypothesis

The inventory commands expose enough stable numeric/structural fields to classify:

- reserved high table ID;
- destination;
- route type;
- protocol role;
- metric;
- interface;
- RPDB priority;
- RPDB lookup table;
- payload ingress/destination selectors;
- probe mark selector.

## Safety

All objects exist only in a disposable network namespace.

## Acceptance

The experiment must PASS in privileged CI and the recorded JSON form must be reviewed before
the NG3 structural route/RPDB parser is implemented.


## Result

**COMPLETE — PASS.**

GitHub Actions run: `43827772041`.

The exact observed route/RPDB JSON and accepted normalization facts are recorded in
`EXP-029-result-20261116.md`.
