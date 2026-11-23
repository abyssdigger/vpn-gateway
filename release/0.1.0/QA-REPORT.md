# VPN-GATE 0.1.0 release-candidate QA report

**Release scope:** Release-1 / `0.1.0`  
**Tested source head:** `bad3c071ffde87315de686e35e99666afdcd3795`  
**Workflow run:** `45253823627`  
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
- artifact ID: `14856894209`;
- uploaded artifact size: **313846 bytes**;
- uploaded artifact ZIP digest:
  `sha256:c8ed09312e0af7faf91df7c7e1e7bba472c0997f85fec7a220452cac0654eaaa`.

The uploaded artifact contains the release tarball and its checksum file.

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

The QA result is evidence for the tested source head only. A source change that affects bundle
contents, installation, deployment integration, runtime behavior, or release-version presentation
requires the applicable checks to be repeated.


## Applicability to final release metadata preparation

The product-bundle build inputs validated by this report are intentionally unchanged during the
subsequent release-metadata finalization. The added requirements coverage, project snapshot,
release-asset builder, process records, and release-asset upload logic do not enter
`vpn-gate-0.1.0.tar.gz`.

The final fulfillment review is responsible for comparing the frozen release candidate with the
tested product-bundle baseline and confirming that no bundle/runtime/deployment input changed.
