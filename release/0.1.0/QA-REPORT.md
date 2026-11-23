# VPN-GATE 0.1.0 release-candidate QA report

**Release scope:** Release-1 / `0.1.0`  
**Tested release-set head:** `8a299116e492ee8462b870bd20f9f0f643e9a941`  
**Workflow run:** `45258483111`  
**QA job:** `release-0-1-0-deployment-qa`  
**QA job result:** **PASS**

## Candidate package

The candidate was built from the tested source head with
`release/0.1.0/build-bundle.sh`.

The build produced:

- `vpn-gate-0.1.0.tar.gz`;
- `vpn-gate-0.1.0.tar.gz.sha256`.

The checksum file was verified before deployment.

The validated GitHub Actions artifact is:

- artifact name: `vpn-gate-0.1.0-candidate`;
- artifact ID: `14859447074`;
- uploaded artifact size: **416194 bytes**;
- uploaded artifact ZIP digest:
  `sha256:566311fea9bcb33cefa72aaa3945d75de72d1aee3292821b68ddafe00f6f2a62`.

Before deployment the workflow verified:

- `vpn-gate-0.1.0.tar.gz: OK`;
- `vpn-gate-0.1.0-project-snapshot.tar.gz: OK`.

The uploaded artifact contains the product tarball/checksum, project-snapshot
tarball/checksum, `QA-REPORT.md`, and `REQUIREMENTS-COVERAGE.md`.

## Environment

The release bundle was deployed into a privileged **Debian 13** systemd container on a GitHub
hosted Linux runner.

The QA environment installed the release prerequisites and the actual VPN implementations used
by the deployment checks:

- `wireguard-tools`;
- `openconnect` with a local `ocserv` peer;
- `xl2tpd` and `ppp`.

The container used the runner host kernel networking support while exercising Debian 13
userspace and systemd.

## Bundle installation

**PASS**

The QA extracted the generated release archive and ran the bundle's own `install.sh`, rather
than installing directly from the repository source tree.

The installed canonical version was verified as `0.1.0`, and the controller's JSON and compact
text current-status presentations were required to report the same version before VPN-specific
payload checks were accepted.

Evidence marker:

`RELEASE_QA_BUNDLE_INSTALL=PASS`

## WireGuard / wg-quick

**PASS**

The client side followed the documented Release-1 integration shape:

- WireGuard client started inside the VPN-GATE managed network namespace;
- client configuration used `Table = off`;
- the configured interface was `wg-corp`;
- VPN transport was an exact UDP endpoint;
- VPN-GATE discovered the current path and installed the payload route;
- real encrypted WireGuard payload reached the test peer;
- stopping the WireGuard service removed the current path without restarting the controller.

Evidence markers:

- `RELEASE_QA_WIREGUARD_PAYLOAD=PASS`;
- `RELEASE_QA_WIREGUARD_LIFECYCLE=PASS`.

## OpenConnect

**PASS**

The QA used the actual Debian OpenConnect client against a local `ocserv` peer.

The client ran inside the managed network namespace and used the release bundle's
`openconnect-policy-neutral.sh`. That script configured the tunnel interface address/link state
without installing payload routes, RPDB policy, nftables state, NAT, or DNS policy. VPN-GATE
discovered `vpn-corp` and owned the tested payload route.

A real payload exchange through the OpenConnect tunnel passed, and stopping the client removed
the current path without restarting the controller.

Evidence markers:

- `RELEASE_QA_OPENCONNECT_PAYLOAD=PASS`;
- `RELEASE_QA_OPENCONNECT_LIFECYCLE=PASS`.

The disposable QA peer used local password authentication only to establish a reproducible test
session. Authentication/credential ownership remains administrator-side as described by the
deployment guide.

## L2TP / PPP

**PASS**

The QA used actual `xl2tpd` and `ppp` processes on both sides of a local L2TP tunnel.

The client daemon ran inside the VPN-GATE managed namespace, established a real PPP data-plane
interface `ppp0`, and used an exact UDP/1701 transport fact. VPN-GATE discovered the interface,
installed the payload route, and real payload reached the remote PPP peer.

Stopping the L2TP client removed the current path without restarting the controller.

Evidence markers:

- `RELEASE_QA_L2TP_PAYLOAD=PASS`;
- `RELEASE_QA_L2TP_LIFECYCLE=PASS`.

This QA covers the simple L2TP/UDP deployment documented for 0.1.0. It does **not** claim an
L2TP/IPsec deployment test; IPsec/IKE/ESP/NAT-T introduces additional underlay control traffic
and remains deployment-specific.

## Overall verdict

**PASS — the generated VPN-GATE 0.1.0 bundle installs successfully according to the release
deployment boundary and provides working payload/lifecycle behavior with WireGuard, OpenConnect,
and L2TP in the tested Debian 13 systemd environment.**

The QA result is evidence for the tested release-set head and may be carried across only a
proved metadata-only change that cannot affect the tested bundle or project snapshot. Any source
change that affects bundle contents, installation, deployment integration, runtime behavior,
release-version presentation, requirements coverage, or project-snapshot contents requires the
applicable checks to be repeated.


## Release-record commit applicability

This report records the complete release-set QA executed on
`8a299116e492ee8462b870bd20f9f0f643e9a941`.

The commit that materializes this updated QA report on `release/0.1.0` changes only
`release/0.1.0/QA-REPORT.md`. It does not change the product bundle, project-snapshot
contents, requirements coverage, installer, deployment contract, runtime, or QA implementation.

The final fulfillment review must verify that exact one-file difference before applying this QA
result to the frozen post-report candidate. The normal release workflow also reruns on that
candidate, providing an additional exact-candidate check.
