# NG3 Release-1 administrator VPN onboarding

**Scope:** first-release administrator-managed VPN integration  
**Status:** implementation/documentation contract; automatic vendor-unit capture is out of scope

## Requirement/architecture mapping

This document is the selected Release-1 **systemd realization**, not the source of generic
requirement semantics.

It realizes:

- `VPNG-U001-R1.R3.C3` — external VPN runtime lifecycle may remain outside VPN-GATE
  ownership/supervision;
- `VPNG-U001-R1.R3.C3.R1` — the project provides a reproducible lifecycle integration
  contract for that externally supervised runtime;
- `VPNG-U001-R1.R3.C1.R1.R2` — VPN-specific configuration remains policy-neutral with
  respect to VPN-GATE-owned network policy;
- `VPNG-U001-R1.R3.R6.R2` — supported VPN clients may receive only the transport/control
  access needed for the channel;
- `VPNG-U001-R4.R4.R6.R4` — Device configuration expresses those bounded client-side VPN
  transport/control intents.

Concrete `NetworkNamespacePath=`, `After=`, `BindsTo=`, stack-specific unit identity and
`systemctl` behavior below are the selected Linux/systemd architecture for this release.
They are not embedded in those generic Requirement/Constraint statements.

## Goal

A supported VPN service runs as an ordinary administrator-visible systemd service, but its
processes and data-plane endpoint live inside the VPN-GATE managed network namespace.

VPN-GATE does not replace systemd as process supervisor.

The administrator keeps ordinary service operations:

```text
systemctl start <vpn-unit>
systemctl stop <vpn-unit>
systemctl restart <vpn-unit>
systemctl reload <vpn-unit>       # only when that VPN service supports reload
```

## Required systemd boundary

Use a distinct stack-specific unit identity. Prefer a separate instance of a vendor template
when one exists.

The unit must have the semantic equivalent of:

```ini
[Unit]
BindsTo=<VPN-GATE managed-domain/controller unit>
After=<VPN-GATE managed-domain/controller unit>

[Service]
NetworkNamespacePath=<VPN-GATE managed-netns path>
```

The concrete packaged VPN-GATE unit/path names are deployment details. The important contract
is:

1. the managed network namespace exists before the VPN process starts;
2. the VPN process is started directly inside that namespace;
3. loss/stop of the managed-domain unit propagates to the VPN unit;
4. shutdown ordering stops the VPN unit before the managed-domain owner is torn down.

Do not create a second service by symlinking/aliasing an ordinary unit name and then assuming
it is an independent service. A systemd alias is another name for the same unit. Use a distinct
template instance or a distinct wrapper unit.

## First-release ownership boundary

Release 1 does **not** automatically:

- discover arbitrary VPN systemd units;
- clone or edit vendor units;
- enable/disable them;
- take ownership of arbitrary already-running VPN processes;
- rewrite arbitrary VPN-specific configuration.

The administrator prepares the stack-specific VPN unit/instance and the VPN-specific
configuration.

VPN-GATE owns network policy inside the managed domain:

- payload routes and RPDB state;
- VPN-GATE nftables state;
- Device/Profile NAT and firewall state;
- integration-local exceptions explicitly derived from the supported onboarding contract.

The VPN-specific configuration owns VPN-specific state such as credentials, peers/remotes,
keys and implementation settings.

## Integration transport facts

A VPN client process inside the managed domain needs transport/control traffic to reach its
remote VPN endpoint through the host boundary.

These facts belong to the Device in the canonical Release-1 configuration:

```toml
[device.corp]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = true
allow_vpn_client = "udp:11941>198.51.100.7:1194"
```

When the VPN uses a dynamic local source port:

```toml
allow_vpn_client = "tcp>203.0.113.10:443"
```

Multiple exact client transports use an array. Grammar:

```text
tcp|udp[:<local-port>]><remote-IPv4>:<remote-port>
```

The current lower shape admits only:

```text
OUTPUT:
    exact current host-boundary identity
    exact managed local address
    exact remote IPv4
    exact remote port
    exact local port when known
        -> accept

INPUT:
    exact current host-boundary identity
    exact remote IPv4 + remote port
    exact managed local address
    exact local port when known
        -> accept

or, when local port is not fixed:
    exact remote endpoint selectors
    + ct state established,related
        -> accept
```

There is no fallback to blanket UDP/TCP or blanket established/related local acceptance.
There is also no public top-level `[integration.*]` object in the canonical Release-1
configuration.

## OpenVPN

On Debian 13 the OpenVPN package provides vendor template units including
`openvpn-client@.service`. Prefer a dedicated stack-specific instance rather than modifying
the ordinary host-side instance.

Example conceptual naming:

```text
openvpn-client@corp.service             # ordinary host integration, if desired
openvpn-client@vpn-gate-corp.service    # stack-specific integration
```

Apply the namespace/dependency drop-in only to the stack-specific instance.

For the supported policy-neutral shape:

- the OpenVPN process starts inside the managed namespace;
- route installation by OpenVPN is disabled with `route-noexec`;
- a stable client transport port should be configured when practical and encoded in
  `allow_vpn_client`; the accepted EXP-049/050 OpenVPN shape uses one, which gives exact
  INPUT/OUTPUT port selectors across service restart;
- arbitrary external `up`/`down` scripts requiring elevated `script-security 2` are not
  part of the supported first-release integration;
- host/external NAT, publication or underlay orchestration stays outside the managed namespace;
- remote protocol/address/port facts are supplied through the Device `allow_vpn_client` field.

EXP-049 uses this shape with OpenVPN 2.6.14 on Debian 13.

## WireGuard / wg-quick

Prefer a separate stack-specific instance of the `wg-quick@.service` template and apply the
same namespace/dependency drop-in to that instance.

The stack-specific WireGuard configuration should use:

```ini
[Interface]
Table = off
```

so `wg-quick` does not materialize routes/RPDB policy that belongs to VPN-GATE.

VPN-specific keys, peers, endpoints and tunnel settings remain administrator-owned.

Legacy `PreUp`, `PostUp`, `PreDown` or `PostDown` commands that mutate routes, RPDB,
NAT, firewall or other VPN-GATE-owned state inside the managed namespace are outside the
supported first-release contract. External host orchestration belongs outside the stack.

## OpenConnect

The Debian 13 `openconnect` package provides the VPN binary but no stock OpenConnect systemd
service template.

For Release 1, create a small administrator-owned stack-specific template/wrapper unit whose
`ExecStart=` invokes the vendor `/usr/sbin/openconnect` binary and apply the same
`BindsTo=`, `After=` and `NetworkNamespacePath=` boundary.

Do not convert OpenConnect's network-configuration scripts into Device/Profile policy
implicitly. Any script behavior that mutates VPN-GATE-owned managed-domain policy must be
removed, disabled or externalized according to the integration instructions.

## Out-of-band host intervention

The supported lifecycle assumes the administrator manages the stack through the documented
VPN-GATE/systemd boundary.

Direct root/admin modification or deletion of authoritative VPN-GATE-owned managed-domain
state outside the documented lifecycle is external intervention for recovery purposes.
Release 1 does not promise forensic recovery, adoption of arbitrary surviving processes, or
discovery of unknown namespace file-descriptor holders after such manual damage.

Do not confuse that authoritative state with administrator-owned integration state. The
stack-specific VPN systemd unit/drop-in and VPN-specific configuration remain administrator
owned under this onboarding contract. Ordinary-host routing created by the peaceful helper is
also administrator-controlled after the helper lifecycle operation completes.

If external intervention removes a safety- or readiness-critical invariant, VPN-GATE follows
the applicable safety/readiness requirement for that invariant; this recovery limitation does
not impose a universal "any drift -> close all forwarding" rule.

For unsupported damage to authoritative VPN-GATE-owned state, the administrator must
repair/clean the externally modified environment as documented before returning to the
supported lifecycle when automatic recovery cannot establish a trustworthy postcondition.

## Future automation

A later release may allow configuration such as:

```text
VPN-GATE config names a vendor systemd unit
    -> VPN-GATE creates/verifies the stack-specific instance/drop-in
    -> controls enable/start/stop automatically
```

That is deliberately not required for Release 1.
