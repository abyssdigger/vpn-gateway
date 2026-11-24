# VPN-GATE 0.1.0 release-candidate QA report — attempt 2

**Release scope:** Release-1 / `0.1.0`  
**Approved scope:** `release/0.1.0/RELEASE-SCOPE.md`  
**Attempt:** 2  
**Tested release-set head:** `4f0ef6ce91d32a3691575adbfdd69990bc5b8340`  
**Workflow run:** `45306006515`  
**QA job:** `release-0-1-0-deployment-qa` / `138149998905`  
**QA job result:** **PASS**

## Release-record gate

Before any bundle deployment, the exact tested head passed the release-record consistency gate:

- `RELEASE_RECORDS_SCOPE=PASS`;
- `RELEASE_RECORDS_SNAPSHOT=PASS`;
- `RELEASE_RECORDS_COVERAGE_220=PASS`;
- `RELEASE_RECORDS_ARCHITECTURE_FULL=PASS`.

The gate verifies the approved 0.1.0 scope, exact project-snapshot copies, all 220 current
Requirement/Constraint rows and the absence of current normative architecture
`partial`/`none` materialization edges.

## Candidate assets

The tested source head built and checksum-verified:

- `vpn-gate-0.1.0.tar.gz`  
  SHA-256: `c703eff07d1f9739d544b836bc5aa767a655bce8890520c5533117aa9a28b74a`;
- `vpn-gate-0.1.0-project-snapshot.tar.gz`  
  SHA-256: `cb141fc4b82adc140343e80c02f9e36f3fc163d7eadcf636533dc6571edb195f`.

Both checksum files were verified before deployment:

- `vpn-gate-0.1.0.tar.gz: OK`;
- `vpn-gate-0.1.0-project-snapshot.tar.gz: OK`.

The validated GitHub Actions artifact is:

- name: `vpn-gate-0.1.0-candidate`;
- artifact ID: `14881151700`;
- uploaded artifact size: **424204 bytes**;
- uploaded artifact ZIP digest:
  `sha256:dbcc3c6c71914853cf31c216626e33a008511d1a2c492b509d61ce7904913d6d`.

The uploaded artifact contains the product archive/checksum, project-snapshot
archive/checksum, `QA-REPORT.md`, `REQUIREMENTS-COVERAGE.md`, and
`RELEASE-SCOPE.md`.

## Environment

The actual generated release bundle was installed into a privileged **Debian 13** systemd
container on a GitHub-hosted Linux runner. The QA environment used real supported integration
implementations:

- `wireguard-tools`;
- `openconnect` with a local `ocserv` peer;
- `xl2tpd` and `ppp`.

The installed canonical version was required to be `0.1.0`, and the supported JSON/text
runtime status surfaces had to publish the same release version before payload tests were
accepted.

## Protective mode

**PASS**

The installed release bundle exercised the approved mandatory Protective-mode scope through
the installed `vpn-gate-control` surface.

Observed evidence:

- `RELEASE_QA_PROTECTIVE_ENTER_BLOCK=PASS` — confirmed entry blocks tested payload;
- `RELEASE_QA_PROTECTIVE_PERIODIC_REPAIR=PASS` — out-of-band deletion of the owned
  protective gate is detected and repaired;
- `RELEASE_QA_PROTECTIVE_SAFE_LEAVE=PASS` — fresh-confirmed normal state permits safe exit;
- `RELEASE_QA_PROTECTIVE_FAILED_LEAVE_RETAINS_BLOCK=PASS` — deliberately unconfirmed
  ordinary state causes explicit failed leave while traffic stays blocked;
- `RELEASE_QA_PROTECTIVE_RECOVERY_RELEASE=PASS` — after normal-state recovery, protective
  release converges safely.

This directly covers the release-specific decision **not** to exercise
`VPNG-U004-R5.C1`.

## WireGuard / wg-quick

**PASS**

The real WireGuard client ran inside the managed namespace with policy-neutral
`Table = off`; VPN-GATE discovered the path, owned the tested payload route and preserved
controller lifetime across VPN lifecycle.

Evidence:

- `RELEASE_QA_WIREGUARD_PAYLOAD=PASS`;
- `RELEASE_QA_WIREGUARD_LIFECYCLE=PASS`.

## OpenConnect

**PASS**

The real Debian OpenConnect client ran against a local `ocserv` peer using the release
bundle's policy-neutral helper. VPN-GATE discovered the path and owned the tested payload
routing.

Evidence:

- `RELEASE_QA_OPENCONNECT_PAYLOAD=PASS`;
- `RELEASE_QA_OPENCONNECT_LIFECYCLE=PASS`.

## L2TP / PPP

**PASS**

Real `xl2tpd`/`ppp` processes established the documented simple L2TP/UDP deployment
shape; VPN-GATE discovered the resulting PPP path and carried real payload.

Evidence:

- `RELEASE_QA_L2TP_PAYLOAD=PASS`;
- `RELEASE_QA_L2TP_LIFECYCLE=PASS`.

This does not claim L2TP/IPsec deployment validation.

## Overall verdict

**PASS — attempt-2 release assets are internally consistent, the generated 0.1.0 product bundle
installs successfully, full mandatory Protective mode passes installed-bundle checks, and
WireGuard/OpenConnect/L2TP payload/lifecycle behavior remains working in the tested Debian 13
systemd environment.**

Final marker:

`RELEASE_QA_RESULT=PASS`

## QA-report commit applicability

This report records QA executed on
`4f0ef6ce91d32a3691575adbfdd69990bc5b8340`.

The commit that materializes this report changes only
`release/0.1.0/QA-REPORT.md`. That file is not an input to the product tarball or the project
snapshot archive, so this report may be carried to the post-report candidate under
`PROJECT-CONVENTIONS.md` §10.4. The final fulfillment review must verify that applicability;
the normal branch workflow also reruns on the post-report head and therefore provides an
additional exact-head check.

This PASS does **not** revive the failed first release-cycle attempt and is not a release
decision.
