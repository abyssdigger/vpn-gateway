# EXP-051 extension result — installed human runtime status PASS

**Date:** 2026-11-22  
**Status:** COMPLETE — PASS  
**Source commit:** `3f6248101e5ff287745842113ace85a9c5cc4319`  
**GitHub Actions run:** `44956806186`  
**Unit job:** `137006664951` — PASS, 793 tests  
**Installed alpha smoke job:** `137006665030` — PASS

## Requirement traceability

- `VPNG9101-R2.R2`
- `VPNG9101-R2.R2.R1`
- `VPNG9101-R2.R2.R2`
- `VPNG9101-R2.R2.R3`
- `VPNG9101-R2.R2.R4`

## Result

The installed Debian 13/systemd alpha publishes `/run/vpn-gate-alpha/status.txt` from the
same current `RuntimeStatusSnapshot` that feeds the alpha JSON surface.

Observed acceptance markers:

```text
EXP051_RUNTIME_STATUS_TEXT_ZERO_PATH=PASS
EXP051_RUNTIME_STATUS_TEXT_FIRST_PATH=PASS
EXP051_RUNTIME_STATUS_TEXT_NEW_GENERATION=PASS
EXP051_RESULT=PASS
```

The zero-path state rendered the enabled Device as `not discovered`; after the VPN path
appeared the report rendered `vpn0` as path `01.` with `unchecked` availability; after
VPN-only endpoint recreation the report remained current and continued to identify the new
current path by the stable human-facing interface row.

Unit evidence additionally proves per-path availability rendering for a two-path Profile:
one path may be `available (<normalized-check>)` while another is
`not available (<normalized-check>)`, without collapsing the two into one Profile verdict.
Unconfirmed effective state renders Device/Profile truthfully as `unknown`.

## Boundary

This result proves the required compact text semantics and installed alpha publication. It
does not make the concrete `status.txt` pathname a stable external API and does not require
the text to round-trip through configuration parsing. JSON remains an alternative alpha
serialization of the same authoritative current snapshot.
