# NG3 Release-1 administrator VPN onboarding

**Scope:** first-release administrator-managed VPN integration  
**Status:** implementation/documentation contract; automatic vendor-unit capture is out of scope

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

A VPN process inside the managed domain needs transport/control traffic to reach its remote
VPN endpoint through the host boundary.

For a supported first-release integration, VPN-GATE needs normalized facts sufficient for a
bounded local allow:

```toml
[integration.<id>]
device = "<device-id>"
protocol = "udp" | "tcp"
remote_ipv4 = "<exact IPv4>"
remote_port = <1..65535>
# optional when the VPN binds a stable local transport port:
local_port = <1..65535>
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

or, when local_port is not fixed:
    exact remote endpoint selectors
    + ct state established,related
        -> accept
```

There is no fallback to blanket UDP/TCP or blanket established/related local acceptance.

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
- arbitrary external `up`/`down` scripts requiring elevated `script-security` are not part
  of the supported first-release integration;
- host/external NAT, publication or underlay orchestration stays outside the managed namespace;
- remote protocol/address/port facts are supplied to VPN-GATE for the integration-local allow.

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

Direct root/admin modification or deletion of VPN-GATE-owned namespace, veth, nft, route/RPDB
or lifecycle dependency artifacts is external intervention.

When such drift is observable, VPN-GATE is expected to fail closed and diagnose it. Release 1
does not promise forensic recovery, adoption of arbitrary surviving processes, or discovery of
unknown namespace file-descriptor holders after manual damage.

The administrator must repair/clean that externally modified environment before returning to
the supported lifecycle.

## Future automation

A later release may allow configuration such as:

```text
VPN-GATE config names a vendor systemd unit
    -> VPN-GATE creates/verifies the stack-specific instance/drop-in
    -> controls enable/start/stop automatically
```

That is deliberately not required for Release 1.
