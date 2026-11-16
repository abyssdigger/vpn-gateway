# EXP-031 — NG3 nft namespace owner marker

## Purpose

Validate the selected versioned ownership marker for the reserved NG3 nft table:

```text
table ip vpn_gate
comment "vpn-gate:ng3:owner-v1"
```

This experiment is about ownership observation only. It does not define final payload filter
or NAT rules.

## Hypotheses

- **H1:** current nftables accepts a table comment on `table ip vpn_gate`;
- **H2:** the exact comment round-trips through `nft -j list ruleset`;
- **H3:** a same-name table without the marker is observably distinct;
- **H4:** foreign tables coexist and remain separately identifiable;
- **H5:** all experiment nft state disappears with the disposable network namespace.

## Observation rule

The future observer will use:

```text
nft -j list ruleset
```

and distinguish:

```text
ABSENT
OWNED(exact comment)
CONFLICT(same-name table, wrong/missing marker)
```

A correct marker is not blanket permission to delete unknown contained objects.

## Safety

All nft state exists only inside a disposable network namespace.

## Acceptance

All hypotheses must pass in privileged GitHub CI and the exact JSON representation must be
recorded before the marker becomes executable ownership evidence.


## Result

**COMPLETE — PASS.**

GitHub Actions run: `43838055259`.

See `EXP-031-result-20261116.md` for exact marked/unmarked JSON representation.
