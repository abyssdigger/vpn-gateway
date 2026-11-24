# NG3 2026-11-22 — supported VPN transport/control closure review

**Scope:** `VPNG-U001-R1.R3.R6*` and Release-1 configuration contracts
`VPNG-U001-R4.R4.R6.R3/R4`.

## Verdict

**PASS — ACCEPT ARCHITECTURE CLOSURE.**

## Finding

The supported OpenVPN/systemd path already implements and proves the bounded VPN
transport/control responsibilities, but five requirements retained `pending_closure`
because the structured architecture did not explicitly carry every migrated/current ID.

## Architecture

The accepted split is now explicit:

- A.002 ConfigurationAdapter normalizes the Release-1
  `allow_vpn_client` and `publish_vpn_server` configuration contracts;
- C.001 NetworkPolicyAdapter owns bounded managed-local transport/control admission and the
  managed-local half of server publication;
- E.001 HostPublicationAdapter owns the independent host-side server publication mapping;
- the managed-VPN integration coverage index owns the cross-component parent
  `VPNG-U001-R1.R3.R6`.

This does not transfer VPN-specific configuration or process supervision to VPN-GATE.

## Evidence

Existing executable evidence is sufficient and is not changed by this documentation-only
closure correction.

Current EXP-051 installed Debian 13/systemd alpha evidence proves:

- zero-path startup remains fail-closed for payload while the exact configured OpenVPN client
  transport/control flow is admitted;
- the real OpenVPN client starts inside the managed namespace and establishes the supported
  channel through that bounded admission;
- requested `publish_vpn_server` is ready only after both managed-local admission and
  owner-scoped host DNAT mapping are present;
- server publication is exercised end-to-end before the VPN data-plane endpoint appears;
- VPN-only restart preserves the integration contract and obtains a fresh endpoint generation.

The earlier EXP-049 FAIL remains valuable historical evidence for why bounded integration-local
admission is required. The later supported-integration implementation and EXP-049/EXP-050/
EXP-051 PASS evidence supersede that old candidate failure rather than erasing it.

## Closure decision

Close:

- `VPNG-U001-R1.R3.R6`;
- `VPNG-U001-R1.R3.R6.R1`;
- `VPNG-U001-R1.R3.R6.R2`;
- `VPNG-U001-R4.R4.R6.R3`;
- `VPNG-U001-R4.R4.R6.R4`.

No requirement semantics, configuration grammar or executable behavior changed in this
review unit. No new `decomp`, `unreal`, `broken` or `rejected_closure` state is
introduced.
