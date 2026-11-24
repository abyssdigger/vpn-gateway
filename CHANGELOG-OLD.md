# VPN-GATE active-line changelog

## 2026-11-17 — NG3 server publication runtime

Canonical Device `publish_vpn_server` is now materialized end-to-end by the reference
alpha/beta runtime.

- added strict owner-scoped host nft DNAT plus existing managed local publication admission;
- proved interface, exact-IPv4 and selector-less mapping with foreign-transit exclusion;
- added authoritative host forwarding/interface/address prerequisite checks without acquiring
  ordinary-host ownership;
- rejects ambiguous overlapping publication mappings before any runtime mutation;
- installed EXP-051 evidence passes real external TCP publication, ordinary VPN lifecycle and
  verified host-owner cleanup.

## 2026-11-17 — actual-main lineage bootstrap

The active `main` tree was separated from historical generation payload.

- RC2/RC3 history is preserved on `legacy-main-rc`;
- NG1/NG2 history is preserved on `legacy-main-ng1-2`;
- the former mixed NG3 main through snapshot 74 is preserved on `legacy-main-ng3`;
- active `main` starts from the accepted NG3 snapshot-74 content after removing physical
  legacy generation trees, legacy experiments/reviews and legacy CI workflows;
- `.github/workflows/actual-main-hygiene.yml` prevents those artifact classes from
  reappearing unnoticed.

Earlier changelog history remains available at
`legacy-main-ng3:CHANGELOG.md`.
