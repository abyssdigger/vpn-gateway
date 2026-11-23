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
`VERSION`, installer, controller systemd unit, configuration example, deployment guide, and
the policy-neutral OpenConnect helper used by the documented example.

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

Release 0.1.0 uses the accepted Release-1 configuration and dataplane semantics. Protective mode
is not part of the required first-release feature set under `VPNG-U004-R5.C1`; the ordinary
fail-closed guarantees remain applicable independently.

This directory prepares a candidate. Publication as an actual product release still requires
the candidate-specific fulfillment review and the separate projectholder release decision.
