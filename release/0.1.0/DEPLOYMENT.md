# VPN-GATE 0.1.0 deployment

## Supported deployment boundary

VPN-GATE 0.1.0 is deployed on a systemd Linux host. The tested target userspace is Debian 13.
The controller owns the managed network domain and its routing/firewall/NAT policy. VPN
credentials, remote endpoints, cryptographic keys, and vendor-specific tunnel settings remain
administrator-owned.

Install host prerequisites before installing the bundle:

```sh
apt-get update
apt-get install -y python3 iproute2 nftables procps
```

Install the VPN implementation required by the deployment separately.

After extracting the bundle:

```sh
sudo ./install.sh
sudo editor /etc/vpn-gate-alpha/config.toml
```

Do not start a VPN client on the ordinary host and move its interface afterward. Start the
stack-specific VPN service directly inside the managed namespace.

## Common integration procedure for any VPN

1. Determine the exact VPN transport endpoint: IPv4 address, TCP/UDP protocol, remote port, and
   local port when stable.
2. Choose the tunnel interface name that VPN-GATE will discover.
3. Configure one Device with that interface and transport fact. Example:

```toml
[device.corp]
enabled = true
expected_interfaces = ["vpn-corp"]
use_outbound_nat = true
allow_vpn_client = "tcp>203.0.113.10:443"

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.20.0.0/16"]
device_order = ["corp"]
```

4. Configure the VPN implementation so it creates its data-plane interface but does not install
   payload routes/RPDB/firewall/NAT state owned by VPN-GATE.
5. Run the VPN under a distinct systemd service with this boundary:

```ini
[Unit]
BindsTo=vpn-gate-alpha.service
After=vpn-gate-alpha.service

[Service]
NetworkNamespacePath=/run/netns/vpn-gate-alpha
```

6. Start the controller first, then the VPN service:

```sh
systemctl start vpn-gate-alpha.service
systemctl start <stack-specific-vpn-unit>
```

7. Verify current state:

```sh
head -1 /run/vpn-gate-alpha/status.txt
cat /run/vpn-gate-alpha/status.txt
python3 -m json.tool /run/vpn-gate-alpha/status.json
```

The first line of the text status and the JSON `version` field must both report `0.1.0`.
The configured Profile must show the expected current tunnel interface before payload use is
accepted.

Stopping `vpn-gate-alpha.service` stops a correctly bound VPN unit before managed-domain
teardown.

## WireGuard / wg-quick example

Install `wireguard-tools`. Use a dedicated configuration such as
`/etc/wireguard/wg-corp.conf`:

```ini
[Interface]
PrivateKey = <client-private-key>
Address = 10.70.0.2/32
ListenPort = 51821
Table = off

[Peer]
PublicKey = <server-public-key>
Endpoint = 198.51.100.20:51820
AllowedIPs = 10.70.0.0/24
PersistentKeepalive = 25
```

`Table = off` is required so wg-quick does not create payload routes/RPDB state.

Use a distinct wrapper service:

```ini
[Unit]
Description=VPN-GATE WireGuard %i
BindsTo=vpn-gate-alpha.service
After=vpn-gate-alpha.service

[Service]
Type=oneshot
RemainAfterExit=yes
NetworkNamespacePath=/run/netns/vpn-gate-alpha
ExecStart=/usr/bin/wg-quick up %i
ExecStop=/usr/bin/wg-quick down %i

[Install]
WantedBy=multi-user.target
```

For the example above, the Device side can use:

```toml
[device.corp]
enabled = true
expected_interfaces = ["wg-corp"]
use_outbound_nat = true
allow_vpn_client = "udp:51821>198.51.100.20:51820"
```

Do not use wg-quick `PreUp`, `PostUp`, `PreDown`, or `PostDown` hooks to mutate
VPN-GATE-owned routes, RPDB, firewall, or NAT state.

## OpenConnect example

Install `openconnect`. Create a stack-specific service:

```ini
[Unit]
Description=VPN-GATE OpenConnect %i
BindsTo=vpn-gate-alpha.service
After=vpn-gate-alpha.service

[Service]
Type=simple
NetworkNamespacePath=/run/netns/vpn-gate-alpha
EnvironmentFile=/etc/vpn-gate-alpha/openconnect-%i.env
ExecStart=/usr/sbin/openconnect --non-inter --interface=vpn-%i \
    --script=/usr/lib/vpn-gate-alpha/openconnect-policy-neutral.sh \
    --config=/etc/vpn-gate-alpha/openconnect-%i.conf ${VPN_GATE_OC_SERVER}
Restart=no

[Install]
WantedBy=multi-user.target
```

Example `/etc/vpn-gate-alpha/openconnect-corp.env`:

```sh
VPN_GATE_OC_SERVER=https://vpn.example.net/
```

Put protocol, server-certificate pin, user/certificate authentication, and other
VPN-specific options in `openconnect-corp.conf`. Keep authentication secrets outside the
release bundle and protect them with normal host permissions.

The bundled `openconnect-policy-neutral.sh` configures only the tunnel interface IPv4 address
and link state. It deliberately does **not** add routes, RPDB rules, nftables rules, NAT, DNS,
or host-global settings. VPN-GATE creates the Profile routes after discovering `vpn-corp`.

A typical Device transport fact for TCP/443 is:

```toml
[device.corp]
enabled = true
expected_interfaces = ["vpn-corp"]
use_outbound_nat = true
allow_vpn_client = "tcp>203.0.113.10:443"
```

Use the actual resolved IPv4 endpoint selected for the deployment rather than a DNS name in
`allow_vpn_client`.

## L2TP client integration

L2TP uses the same generic boundary. The administrator-owned L2TP/PPP stack must run inside
the managed namespace and create its PPP data-plane interface there.

For an exact `ppp0` deployment:

```toml
[device.corp]
enabled = true
expected_interfaces = ["ppp0"]
use_outbound_nat = true
allow_vpn_client = "udp>198.51.100.30:1701"
```

The PPP options used by the stack must not install a default route or policy hooks owned by
VPN-GATE. In particular, use the implementation's equivalent of `nodefaultroute` and do not
attach `ip-up`/`ip-down` hooks that modify VPN-GATE routes, RPDB, nftables, or NAT state.

If L2TP is protected by IPsec, the additional IKE/ESP/NAT-T transport/control requirements are
outside this simple UDP/1701 example and must be represented/allowed according to the actual
underlay integration rather than inferred from the L2TP payload interface.

## Operational checks

A deployment is not ready merely because the VPN process is running. Check all of:

```sh
systemctl --no-pager --full status vpn-gate-alpha.service
cat /run/vpn-gate-alpha/status.txt
journalctl -u vpn-gate-alpha.service -p warning --no-pager
ip netns exec vpn-gate-alpha ip -br link
```

For a payload destination, verify connectivity from the intended ordinary-side source and
confirm that stopping/restarting only the VPN service causes the current interface generation
to disappear/reappear in status without restarting the controller.

Do not manually delete or rewrite VPN-GATE-owned namespace/routing/nftables state as a normal
recovery procedure.
