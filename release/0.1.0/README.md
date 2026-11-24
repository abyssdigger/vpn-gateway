# VPN-GATE 0.1.0 release bundle

This directory defines the source bundle for **Release-1 / 0.1.0**.

The release bundle deliberately packages the already evidenced NG3 Python reference runtime
without renaming its established `vpn-gate-alpha` service, managed-netns, configuration, or
runtime-status paths. Those implementation-path names are not the release identity. The release
identity is the canonical root `VERSION` value and the version published by the current-status
surface.

## Build

From the repository root:

```sh
sh release/0.1.0/build-bundle.sh
```

The default output directory is `dist/`. The build produces:

```text
vpn-gate-0.1.0.tar.gz
vpn-gate-0.1.0.tar.gz.sha256
```

The archive is self-contained for installation. It contains the runtime package, canonical
`VERSION`, installer, controller systemd unit, configuration example, deployment guide,
the policy-neutral OpenConnect helper used by the documented example, and the root-only
`vpn-gate-control` Protective-mode client.

## Install

On the target host, extract the archive and run as root:

```sh
tar -xzf vpn-gate-0.1.0.tar.gz
cd vpn-gate-0.1.0
./install.sh
```

Then follow `DEPLOYMENT.md`.

The installer does not start the controller, alter an administrator VPN configuration, or enable
host-wide IPv4 forwarding. It preserves an existing `/etc/vpn-gate-alpha/config.toml`.

## Release scope notes

Release 0.1.0 is governed by `RELEASE-SCOPE.md`. For this release the omission permitted by
`VPNG-U004-R5.C1` is explicitly **not exercised**: full Protective mode is a release
commitment. The aggressive host-routing helper remains outside 0.1.0 scope under
`VPNG-U001-R5.R2.C1`.

This directory prepares a candidate. Publication as an actual product release still requires
the candidate-specific fulfillment review and the separate projectholder release decision.
