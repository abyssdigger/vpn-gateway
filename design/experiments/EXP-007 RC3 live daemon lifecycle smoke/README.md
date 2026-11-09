# EXP-007 — RC3 live daemon lifecycle smoke

This experiment runs the **actual RC3 daemon on the real gateway host**. It is not a
network-namespace simulation.

## Purpose

Validate the first live RC3 implementation gate:

- config security/lint boundary;
- startup materialization of routes + firewall/NAT;
- forwarding enablement only after materialization;
- survival of at least one periodic reconciliation interval;
- graceful SIGTERM cleanup.

Runtime drift injection is intentionally out of scope.

## Safety boundary

Run only on the dedicated vpn-gateway host in a maintenance window.

Before running, stop every previous vpn-gateway controller/daemon. The harness refuses to
start unless all of the following are clean:

- `net.ipv4.ip_forward == 0`;
- no `VPNG-*` firewall resources;
- no route protocol 201 or 202 entries.

The OpenConnect transport itself should remain up so the configured interface/local address
can resolve to a READY binding.

The script does not edit the supplied configuration. RC3 itself requires the config file
and its parent directory to be root-owned and not group/other writable.

## Run

```bash
git pull --ff-only
cd "design/experiments/EXP-007 RC3 live daemon lifecycle smoke"

sudo ./vpn-gateway-exp-007-rc3-live-smoke.sh \
    --config /etc/vpn-gateway/vpn-gateway.toml
```

Optional override:

```bash
sudo ./vpn-gateway-exp-007-rc3-live-smoke.sh \
    --config /etc/vpn-gateway/vpn-gateway.toml \
    --python-tree /path/to/design/RC3/code/python
```

The harness prints a concise result and leaves a timestamped directory plus a tarball and
SHA256 file in the current directory.

## PASS

All four checks must pass:

1. config check;
2. initial ACTIVE materialization;
3. steady state after one reconcile interval;
4. graceful cleanup back to the clean ownership boundary.

If the harness exits early, preserve the generated directory and `daemon.log`; do not
manually erase evidence before reviewing the failure.
