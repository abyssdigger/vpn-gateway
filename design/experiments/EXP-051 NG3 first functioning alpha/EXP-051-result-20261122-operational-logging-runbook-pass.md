# EXP-051 extension result — operational logging and admin runbook applicability PASS

**Date:** 2026-11-22  
**Status:** COMPLETE — PASS  
**Source commit:** `d3787abfce7bfa9059ba919a9a032d9c09017e4d`  
**GitHub Actions run:** `44989015020`  
**Unit job:** `137105803566` — PASS, 800 tests  
**Installed alpha smoke job:** `137105803801` — PASS

## Requirement traceability

- `VPNG-M001-R2.R3`
- `VPNG-M001-R2.R3.R1`
- `VPNG-M001-R2.R3.R2`
- `VPNG-M001-R2.R3.R2.R1`
- `VPNG-M001-R2.R3.R2.R2`
- `VPNG-M001-R2.R3.R2.R3`
- `VPNG-M001-R2.R3.R2.R4`
- `VPNG-M001-R2.R3.R3`
- `VPNG-M001-R2.R3.R4`
- `VPNG-M001-R2.R3.R5`
- `VPNG-M001-R2.R3.R6`
- `VPNG-M001-R2.R3.R6.C1`
- administrator-documentation obligation `VPNG-M001-R1.R1.C1.R1`

## Operational logging result

The installed Debian 13/systemd alpha proved the new operational logging path with
`log_level = "debug"`.

Observed acceptance markers:

```text
EXP051_OPERATIONAL_LOG_DEBUG_REACTION=PASS
EXP051_OPERATIONAL_LOG_BINDING_INFO=PASS
EXP051_OPERATIONAL_LOG_JOURNAL_PRIORITY=PASS
EXP051_OPERATIONAL_LOG_CHANGE_DRIVEN=PASS
EXP051_OPERATIONAL_LOG_ENDPOINT_GENERATION=PASS
EXP051_VPN_ONLY_RESTART_RECONCILED=PASS
EXP051_ADMIN_RUNBOOK_APPLICABILITY=PASS
EXP051_RESULT=PASS
```

The journal contained normalized component-attributed records such as:

```text
INFO LIFE config_accepted ...
INFO LIFE ready ...
INFO BIND path_binding_changed current=vpn0@<ifindex> ...
DEBUG PROF effective_order_changed ...
DEBUG POLICY policy_applied ...
```

The endpoint-generation check proved that same-name VPN recreation is visible as a distinct
binding generation rather than being collapsed to the interface name.

The journal-priority check queried the same service with `journalctl -p info`: INFO binding
records remained visible while DEBUG policy records were excluded. This confirms that the
systemd stream preserves the standard DEBUG/INFO/WARNING/ERROR severity metadata rather than
only printing level words.

The stable-audit interval check proved that repeated equivalent observation does not add
BIND/AVAIL/PROF/POLICY operational records.

## Admin runbook applicability

`design/NG3/admin-runbook.md` was checked against the same real systemd alpha path rather
than only inspected textually. EXP-051 performs the material runbook sequence:

1. Debian 13 package prerequisites are installed, including `procps` for `watch`;
2. the repository `install.sh` installs the controller;
3. canonical Device/Profile configuration is written and accepted;
4. an OpenVPN client config with `route-noexec` and the documented stable local transport
   port is prepared;
5. the documented stack-specific systemd wrapper starts OpenVPN inside the managed netns;
6. controller READY, human `status.txt`, JSON status and real Profile payload are checked;
7. controller and VPN journals are read separately;
8. journal severity filtering is exercised;
9. VPN-only restart produces a fresh endpoint generation without controller restart;
10. controller stop performs bound-VPN shutdown and owned cleanup.

During applicability review two documentation defects were found and corrected before this
PASS: `procps` was missing from the stated prerequisites even though the guide uses
`watch`, and the canonical config-model logging section/example had a structural placement
and literal-`\\n` typo.

## Boundary

This result validates the current alpha administrator path and operational-log semantics. It
does not promote the concrete journal transport or alpha file paths to stable Release-1 APIs.

Developer execution trace remains separately blocked by `VPNG-D001-R2` and
`design/deferrals/NG3-developer-execution-trace.md`.
