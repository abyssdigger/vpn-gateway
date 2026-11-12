# Disposition — whole-code review after Draft 5 safety correction

F1 and F2 are accepted as current blocking findings.

- nftables is confirmed as the target and only future production firewall/NAT backend.
- legacy iptables remains temporarily for regression evidence but will be removed from
  Planner/runtime/status ownership.
- EXP-017 has been corrected and extended to collect generation-sensitive nft JSON output.
- production nft verification will not rely on desired-name substitution.

F3/F4 are accepted consistency obligations. Existing remote-initiated constraints and
incremental lifecycle model are retained.

F5/F6 remain explicitly experiment-gated by EXP-016 and EXP-015 respectively.

F7 is accepted as the release-completeness checklist.

No new feature work is started before F1/F2 are resolved and reviewed.
