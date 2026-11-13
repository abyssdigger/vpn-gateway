# EXP-023 — NG1 real OpenConnect Profile-binding probe plane

**Status:** COMPLETE — PASS (2026-11-13)  
**Architecture baseline:** NG1 Profile-binding availability/control + EXP-022 PASS  
**Type:** real dual-OpenConnect path / isolated availability-condition validation

## Purpose

Validate the EXP-022 control-plane primitive against two real OpenConnect bindings that can
both reach the same remote endpoint.

This experiment does **not** redefine availability as ping. It validates one active
availability condition on a production-like VPN path.

## Stand

EXP-023 reuses the real dual-client OpenConnect stand already described and validated in
**EXP-011**. It does not define a new stand.

Relevant EXP-011 baseline:

- ocserv host `testing` = `192.168.201.107`;
- external endpoint TCP/UDP `44443`;
- `pri` = remote `192.168.201.108`, VPN peer `172.20.130.6`;
- `sec` = remote `192.168.201.199` in the historical EXP-011 run; current EXP-023 stand uses `192.168.201.109`, VPN peer `172.20.130.5`;
- with normal host ocserv, the two server-side interfaces materialize as current `vpns*`
  bindings.

EXP-023 difference: both normal OpenConnect sessions remain alive while only endpoint
forwarding behind `pri` is temporarily blocked.

The expected live topology is:

```text
             real OC path A
server vpnsA ==============> remote client A ----> endpoint
       |
       |     real OC path B
       + vpnsB ==============> remote client B ----> endpoint
```

Both paths must initially reach the same IPv4 endpoint.

The script may identify the two interfaces either by interface name or by their fixed
OpenConnect peer IPv4 addresses.

## Stand diagnosis, restoration and verification

Perform these interactively before running the harness.

### 1. Diagnose current server state

Do not start services first:

```sh
hostname
systemctl is-active ocserv
systemctl status ocserv --no-pager -l
pgrep -a ocserv
ss -lntup | grep ':44443' || true
ip -br link
ip -o -4 addr show
```

If the normal ocserv service is intentionally stopped from a previous experiment, that is
a diagnosed stand state rather than an experiment failure.

### 2. Restore only what is missing

For the known post-EXP-011 stopped-service state:

```sh
sudo systemctl start ocserv
sleep 0.1
sudo ss -lntup | grep ':44443'
```

The short delay is an interactive readiness allowance observed on this stand; automated
readiness checks should use polling instead.

### 3. Verify both OpenConnect clients reconnected

```sh
sudo watch -n1 occtl show users
```

Expected mapping:

```text
pri  -> 172.20.130.6 -> vpns00 (current interface name may be reallocated)
sec  -> 172.20.130.5 -> vpns01 (current interface name may be reallocated)
```

Then record the actual interfaces:

```sh
ip -o -4 addr show
```

### 4. Diagnose each remote client

On `pri`, then on `sec`, without changing anything:

```sh
hostname
ip -br addr
ip route
sysctl net.ipv4.ip_forward
iptables -S FORWARD
iptables -t nat -S
ping -c 1 -W 1 172.21.201.19
```

Also confirm that no EXP-023 blocking rule is already present:

```sh
sudo iptables -C FORWARD -d 172.21.201.19/32 \
    -m comment --comment VPNG-EXP023 -j DROP
```

That last command must return non-zero before the experiment.

Only after these outputs are reviewed should the experiment harness be run.

## What is being proved

1. both real OC bindings can initially reach the endpoint;
2. a dedicated probe table plus
   `uidrange + ipproto + to + oif` rule selects only the primary binding;
3. a data-path-only failure behind the primary OpenConnect client makes the primary
   condition fail without terminating the OC session or removing the server-side binding;
4. the secondary OC binding remains able to reach the same endpoint;
5. the primary probe therefore does not escape through the alternate OC path;
6. removing the failure restores the primary condition on the same server-side
   `(ifname,ifindex)` binding.

EXP-021/022 already prove the unprivileged ping and narrow nft mechanisms. EXP-023 does not
modify production firewall policy; it focuses on the real OpenConnect path.

## Operator actions known before launch

EXP-023 contains two polling windows that require a manual action on `pri`. The operator
must know both commands before starting the harness.

During the outage window on `pri`:

```sh
sudo /usr/sbin/iptables -I FORWARD 1 \
    -d 172.21.201.19/32 \
    -m comment --comment VPNG-EXP023 \
    -j DROP
```

During the recovery window on `pri`:

```sh
sudo /usr/sbin/iptables -D FORWARD \
    -d 172.21.201.19/32 \
    -m comment --comment VPNG-EXP023 \
    -j DROP
```

Each polling window is bounded to 180 seconds. If the experiment is interrupted while the
DROP exists, remove it manually with the recovery command above.
## Experimental run

After the interactive stand diagnosis/restoration/verification has been reviewed, separate
this run from prior terminal output first:

```sh
clear
```

Then run:

Generic form:

```sh
sudo ./exp-023-real-openconnect-probe-plane.sh \
    --primary-peer <primary-vpn-peer-ip> \
    --secondary-peer <secondary-vpn-peer-ip> \
    --target <remote-endpoint-ip>
```

Interface names may be supplied directly instead:

```sh
sudo ./exp-023-real-openconnect-probe-plane.sh \
    --primary-if vpns00 \
    --secondary-if vpns01 \
    --target <remote-endpoint-ip>
```

The script uses only a temporary local RPDB rule and routing table and removes them on exit.

## Creating the outage

When instructed by the harness, on **remote client A only** insert a temporary forwarding
DROP for the endpoint while leaving OpenConnect running:

```sh
sudo iptables -I FORWARD 1 -d <remote-endpoint-ip>/32 \
    -m comment --comment VPNG-EXP023 -j DROP
```

Later remove the same rule:

```sh
sudo iptables -D FORWARD -d <remote-endpoint-ip>/32 \
    -m comment --comment VPNG-EXP023 -j DROP
```

If the experiment is interrupted while the DROP is active, remove that remote rule
manually.

This intentionally breaks only endpoint payload through one VPN client. It avoids turning
the test into ordinary OpenConnect process/interface lifecycle.

## Diagnostics rule

Every command-derived assertion that stops the experiment prints the assertion first and
then the captured raw return code/stdout/stderr. This is the required pattern for future
VPN-GATE experiment harnesses.

## Decision boundary

A PASS validates the real OpenConnect use of the already-proven isolated probe plane. It
does not yet choose:

- configuration grammar;
- probe cadence, timeout or hysteresis;
- general condition composition;
- manual inhibit/schedule APIs.

## Target result

EXP-023 completed with `EXP_023_REAL_OPENCONNECT_PROBE_PLANE=PASS` on 2026-11-13.

See [EXP-023-result-20261113.md](EXP-023-result-20261113.md).

The real result confirms that a failed condition on one live OpenConnect binding does not
escape through another live OpenConnect binding and recovers on the same binding after the
primary data path is restored.
