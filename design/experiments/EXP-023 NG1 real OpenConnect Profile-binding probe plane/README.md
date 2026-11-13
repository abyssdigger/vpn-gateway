# EXP-023 — NG1 real OpenConnect Profile-binding probe plane

**Status:** READY FOR TARGET RUN  
**Architecture baseline:** NG1 Profile-binding availability/control + EXP-022 PASS  
**Type:** real dual-OpenConnect path / isolated availability-condition validation

## Purpose

Validate the EXP-022 control-plane primitive against two real OpenConnect bindings that can
both reach the same remote endpoint.

This experiment does **not** redefine availability as ping. It validates one active
availability condition on a production-like VPN path.

## Stand description

This experiment changes stand relative to the preceding synthetic netns experiment.
Before any experiment mutation, verify the following real topology.

The server has two simultaneously bound OpenConnect interfaces:

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

## Mandatory preflight

Do **not** start the mutating experiment first.

For the current stand the expected roles are:

| Role | Expected value |
| --- | --- |
| primary OC user/peer | `pri` / `172.20.130.6` |
| secondary OC user/peer | `sec` / `172.20.130.5` |
| server-side interfaces | two current `vpns*` bindings, resolved from peer addresses |
| common endpoint | `172.21.201.19` |
| outage location | remote `pri` client, forwarding to the endpoint only |
| must remain alive during outage | both OpenConnect sessions and both server-side bindings |

First update the repository and run **preflight only**:

```sh
git pull --ff-only

cd "design/experiments/EXP-023 NG1 real OpenConnect Profile-binding probe plane"

sudo ./exp-023-real-openconnect-probe-plane.sh \
    --primary-peer 172.20.130.6 \
    --secondary-peer 172.20.130.5 \
    --target 172.21.201.19 \
    --preflight-only
```

This mode performs no RPDB/table changes. It must show:

- two different concrete interfaces;
- both interfaces contain `IFF_UP`;
- their current ifindexes and raw `ip -o link` lines;
- the ordinary route to the endpoint;
- successful endpoint probe through **each** concrete OC interface;
- final marker:

```text
EXP_023_PREFLIGHT=PASS
```

On each remote OC client, before the experiment, verify forwarding/NAT and endpoint
reachability using the existing operational configuration. At minimum on **pri**:

```sh
ip -br addr
ip route
sysctl net.ipv4.ip_forward
iptables -t nat -S
ping -c 1 172.21.201.19
```

Run the same checks on **sec**. There must be no leftover `VPNG-EXP023` DROP rule:

```sh
sudo iptables -C FORWARD -d 172.21.201.19/32 \
    -m comment --comment VPNG-EXP023 -j DROP
```

That command is expected to return non-zero before the experiment.

Only after the server preflight and both remote-client checks match this description should
the mutating run begin.
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

## Experimental run

After the mandatory preflight has been reviewed, run without `--preflight-only`.

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
