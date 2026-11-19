# VPN-GATE NG3 — development milestones

This log records **major steps** in the active NG3 lineage, not individual commits,
reviews, experiments or transient implementation details. The governing requirements,
architecture and evidence remain authoritative in their own artifacts.

## 2026-11-17 — Clean active NG3 lineage

The active `main` was established as an NG3-only development line. Historical RC
and NG1/NG2 material remains on `legacy-main-rc` and `legacy-main-ng1-2`;
the former mixed NG3 history remains on `legacy-main-ng3`. The active-tree
hygiene guard rejects reintroduction of legacy payload.

## 2026-11-17 — VPN server publication integrated into the NG3 runtime

The reference NG3 runtime gained Device `publish_vpn_server` handling with
host-owned publication boundaries and fail-closed mapping validation.
The accepted experiment evidence includes external TCP publication, ordinary VPN
lifecycle and cleanup of owned host resources.

---

The previous active-line changelog was preserved verbatim as
[CHANGELOG-OLD.md](CHANGELOG-OLD.md). Earlier RC/NG1/NG2 development history is
retained on the corresponding legacy branches, not copied into the current tree.
