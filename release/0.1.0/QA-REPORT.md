# VPN-GATE 0.1.0 release-candidate QA report — documentation-driven acceptance

**Release scope:** Release-1 / `0.1.0`  
**Approved scope:** `release/0.1.0/RELEASE-SCOPE.md`  
**Tested release-set head:** `a48350396c6ff22f06ca6f59e404a6e9e38c040b`  
**Workflow run:** `45313040992`  
**QA job:** `release-0-1-0-deployment-qa` / `138173272991`  
**QA job result:** **PASS**

## Documentation-driven acceptance verdict

**PASS — the published 0.1.0 administrator procedure was executed end to end on the actual
generated release bundle and proved operationally applicable in the declared Debian 13/systemd
evidence boundary.**

The walkthrough treated the release-published documentation as the source of the administrator
procedure. QA-only setup was limited to creation of disposable remote peers/container/kernel
facilities; product installation/configuration/VPN client setup/operator actions followed the
published release path.

## Tested documentation identity

The product archive contained the exact documents used by the walkthrough:

- `README.md` SHA-256:
  `32b1a7982601637d8d88e5927d4f0a6bf5d31924b4def3880e62071f6bac7d7c`;
- `DEPLOYMENT.md` SHA-256:
  `1b63421d815be53c736b2a53489bf4a2a7ac9fc0835200f87046e6a1891ff01b`.

The installer copied those same documents into `/usr/share/doc/vpn-gate/`, and the walkthrough
verified byte equality between bundled and installed copies.

## Release-record gate

Before deployment the exact tested head passed:

- `RELEASE_RECORDS_SCOPE=PASS`;
- `RELEASE_RECORDS_SNAPSHOT=PASS`;
- `RELEASE_RECORDS_COVERAGE_220=PASS`;
- `RELEASE_RECORDS_ARCHITECTURE_FULL=PASS`.

## Release asset identity

Product archive:

`vpn-gate-0.1.0.tar.gz`

SHA-256:

`ad86d5c0089d5dca65fdda826c36054b6da7f7e20e120445d2c52b8bd0a81a7b`

Project-snapshot archive:

`vpn-gate-0.1.0-project-snapshot.tar.gz`

SHA-256:

`cb141fc4b82adc140343e80c02f9e36f3fc163d7eadcf636533dc6571edb195f`

Validated Actions artifact:

- name: `vpn-gate-0.1.0-candidate`;
- artifact ID: `14883549614`;
- size: **426367 bytes**;
- ZIP digest:
  `sha256:28524e99dd361aa18fa6378898dc78941f851d323d21146aa828a7e1ec2e8b79`.

## Environment boundary

The walkthrough used a privileged Debian 13 systemd container on a GitHub-hosted Linux runner.

The outer QA harness preinstalled only environment machinery required to run the disposable
systemd test environment and remote OpenConnect peer (`systemd`, `dbus`, Python, `kmod`,
`openssl`, `ocserv`). VPN-GATE runtime prerequisites and all three client VPN
implementations were then installed through the commands in the published administrator guide.

This remains container/kernel evidence, not a claim of separate physical-host validation.

## Administrator walkthrough

| Published procedure | Administrator-visible confirmation | Result |
| --- | --- | --- |
| Extract release bundle | bundled README/DEPLOYMENT present | PASS |
| Debian 13 base prerequisites | documented packages install successfully | PASS |
| Run release installer | installed version `0.1.0`; installed docs byte-identical | PASS |
| Create VPN-GATE config | documented Device/Profile grammar accepted | PASS |
| WireGuard package/config/service | `wg-corp` shown in built-in current status | PASS |
| WireGuard payload | real Profile payload succeeds | PASS |
| WireGuard service stop/restart | path disappears/reappears without controller restart | PASS |
| OpenConnect package/config/service | `vpn-corp` shown in built-in current status | PASS |
| OpenConnect payload | real Profile payload succeeds against disposable `ocserv` peer | PASS |
| OpenConnect service stop/restart | path disappears/reappears without controller restart | PASS |
| L2TP/PPP package/config/service | `ppp0` shown in built-in current status | PASS |
| L2TP/PPP payload | real Profile payload succeeds | PASS |
| L2TP service stop/restart | path disappears/reappears without controller restart | PASS |
| Protective initial status | built-in control reports `inactive` | PASS |
| Protective manual enter + status | built-in control reports `active`; real payload is blocked | PASS |
| Protective manual leave + status | built-in control reports `inactive`; real payload is restored | PASS |

The walkthrough emitted:

- `DOC_WALKTHROUGH_BUNDLE_EXTRACT=PASS`;
- `DOC_WALKTHROUGH_BASE_PREREQUISITES=PASS`;
- `DOC_WALKTHROUGH_BUNDLE_INSTALL=PASS`;
- `DOC_WALKTHROUGH_WIREGUARD_PREREQUISITES=PASS`;
- `DOC_WALKTHROUGH_WIREGUARD_DIAGNOSTICS=PASS`;
- `DOC_WALKTHROUGH_WIREGUARD_PAYLOAD=PASS`;
- `DOC_WALKTHROUGH_WIREGUARD_STOP_STATUS=PASS`;
- `DOC_WALKTHROUGH_WIREGUARD_RESTART_DIAGNOSTICS=PASS`;
- `DOC_WALKTHROUGH_WIREGUARD_RESTART_PAYLOAD=PASS`;
- `DOC_WALKTHROUGH_OPENCONNECT_PREREQUISITES=PASS`;
- `DOC_WALKTHROUGH_OPENCONNECT_DIAGNOSTICS=PASS`;
- `DOC_WALKTHROUGH_OPENCONNECT_PAYLOAD=PASS`;
- `DOC_WALKTHROUGH_OPENCONNECT_STOP_STATUS=PASS`;
- `DOC_WALKTHROUGH_OPENCONNECT_RESTART_DIAGNOSTICS=PASS`;
- `DOC_WALKTHROUGH_OPENCONNECT_RESTART_PAYLOAD=PASS`;
- `DOC_WALKTHROUGH_L2TP_PREREQUISITES=PASS`;
- `DOC_WALKTHROUGH_L2TP_DIAGNOSTICS=PASS`;
- `DOC_WALKTHROUGH_L2TP_PAYLOAD=PASS`;
- `DOC_WALKTHROUGH_L2TP_STOP_STATUS=PASS`;
- `DOC_WALKTHROUGH_L2TP_RESTART_DIAGNOSTICS=PASS`;
- `DOC_WALKTHROUGH_L2TP_RESTART_PAYLOAD=PASS`;
- `DOC_WALKTHROUGH_PROTECTIVE_INITIAL_STATUS=PASS`;
- `DOC_WALKTHROUGH_PROTECTIVE_ENTER_STATUS_PAYLOAD=PASS`;
- `DOC_WALKTHROUGH_PROTECTIVE_LEAVE_STATUS_PAYLOAD=PASS`;
- `DOC_WALKTHROUGH_ADMINISTRATOR_PROCEDURE=PASS`;
- `RELEASE_QA_DOCUMENTATION_WALKTHROUGH=PASS`.

## Built-in diagnostics used by the walkthrough

For each VPN integration, the administrator-visible checks executed the published diagnostic
commands:

- `systemctl --no-pager --full status vpn-gate-alpha.service`;
- `head -1 /run/vpn-gate-alpha/status.txt`;
- `cat /run/vpn-gate-alpha/status.txt`;
- `python3 -m json.tool /run/vpn-gate-alpha/status.json`;
- `journalctl -u vpn-gate-alpha.service -p warning --no-pager`;
- `ip netns exec vpn-gate-alpha ip -br link`.

The expected current tunnel interface had to be visible in both current-state data and the
managed namespace before real payload was accepted.

Protective mode used the published built-in
`vpn-gate-control protective status` surface before enter, after enter and after leave.

## Additional negative/safety QA

The following checks were performed **after** the successful ordinary administrator path and do
not substitute for it:

- out-of-band deletion of the owned Protective gate followed by periodic repair:
  `RELEASE_QA_PROTECTIVE_PERIODIC_REPAIR=PASS`;
- deliberately unconfirmed ordinary state followed by failed leave while payload remains blocked:
  `RELEASE_QA_PROTECTIVE_FAILED_LEAVE_RETAINS_BLOCK=PASS`;
- normal-state recovery followed by safe automatic release:
  `RELEASE_QA_PROTECTIVE_RECOVERY_RELEASE=PASS`.

Compatibility markers also remain PASS:

- `RELEASE_QA_WIREGUARD_PAYLOAD=PASS`;
- `RELEASE_QA_WIREGUARD_LIFECYCLE=PASS`;
- `RELEASE_QA_OPENCONNECT_PAYLOAD=PASS`;
- `RELEASE_QA_OPENCONNECT_LIFECYCLE=PASS`;
- `RELEASE_QA_L2TP_PAYLOAD=PASS`;
- `RELEASE_QA_L2TP_LIFECYCLE=PASS`;
- `RELEASE_QA_PROTECTIVE_ENTER_BLOCK=PASS`;
- `RELEASE_QA_PROTECTIVE_SAFE_LEAVE=PASS`;
- `RELEASE_QA_RESULT=PASS`.

## Applicability discovered by the walkthrough

The strict walkthrough found two documentation defects before reaching PASS:

1. the original Debian WireGuard package command pulled a recommended kernel image that is not
   required for the already-supported host kernel and was not installable in the declared
   container evidence boundary; the documented command now uses
   `--no-install-recommends`;
2. the original L2TP service recipe omitted the runtime directory required by
   `xl2tpd-control`; the documented service now owns `RuntimeDirectory=xl2tpd`.

Both fixes were made to the administrator procedure itself and then re-executed by the
walkthrough. They are evidence that this acceptance checks documentation applicability rather
than merely replaying an implementation test.

## Overall verdict

**PASS — the 0.1.0 administrator procedure is proven applicable for installation,
configuration, documented WireGuard/OpenConnect/plain-L2TP integrations, built-in diagnostics,
real payload, VPN service lifecycle and manual Protective-mode operation within the declared
Debian 13/systemd evidence boundary.**

L2TP evidence remains plain L2TP/UDP + PPP; it does not claim L2TP/IPsec validation.

## QA-report commit applicability

This report records QA executed on
`a48350396c6ff22f06ca6f59e404a6e9e38c040b`.

The commit that materializes this report changes only
`release/0.1.0/QA-REPORT.md`; that file is not an input to the product tarball or project
snapshot. The exact post-report branch workflow must nevertheless rerun before a new frozen
candidate/fulfillment review is accepted.

This PASS is evidence, not a projectholder release decision.
