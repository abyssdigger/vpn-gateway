# VPN-GATE 0.1.0 release bundle

This directory defines the source/release-record set for **Release-1 / 0.1.0**.

The governing product scope is the approved `RELEASE-SCOPE.md`. Release attempt 2 requires the
full Protective-mode family; the omission permitted by `VPNG-U004-R5.C1` is not exercised.
The aggressive host-routing helper remains outside 0.1.0 scope under
`VPNG-U001-R5.R2.C1`.

The bundle deliberately packages the evidenced NG3 Python reference runtime without renaming its
established `vpn-gate-alpha` service, managed-netns, configuration or runtime-status paths.
Those implementation-path names are not the release identity. The release identity is the root
`VERSION` value and the version published by the supported current-status surfaces.

## Build

From repository root:

```sh
sh release/0.1.0/build-bundle.sh
sh release/0.1.0/build-project-snapshot.sh
```

The release asset set is:

```text
vpn-gate-0.1.0.tar.gz
vpn-gate-0.1.0.tar.gz.sha256
vpn-gate-0.1.0-project-snapshot.tar.gz
vpn-gate-0.1.0-project-snapshot.tar.gz.sha256
QA-REPORT.md
REQUIREMENTS-COVERAGE.md
```

The product archive contains the runtime package, canonical `VERSION`, installer, controller
systemd unit, configuration example, deployment guide, policy-neutral OpenConnect helper and
root-local `vpn-gate-control` client.

## Install

On the target host:

```sh
tar -xzf vpn-gate-0.1.0.tar.gz
cd vpn-gate-0.1.0
./install.sh
```

Then follow `DEPLOYMENT.md`.

The installer does not start the controller, alter administrator VPN configuration or enable
host-wide IPv4 forwarding. It preserves an existing
`/etc/vpn-gate-alpha/config.toml`.

## Project/release records

`project-snapshot/` contains exact release-attempt copies of the current NG3 requirements,
architecture and changelog. `REQUIREMENTS-COVERAGE.md` is the complete release-specific
R/C disposition matrix evaluated against requirements **and** the approved release scope.

`QA-REPORT.md` is attempt-specific. A prior-attempt PASS is never carried into a new attempt
as a release-readiness verdict.

Publication still requires a frozen canonical `release/0.1.0` candidate, exact-candidate
fulfillment review and separate projectholder release decision.
