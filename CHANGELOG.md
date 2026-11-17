# VPN-GATE active-line changelog

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
