# VPN-GATE 0.1.0 deployment and administrator guide

## Supported deployment boundary

VPN-GATE 0.1.0 is deployed on a systemd Linux host. The tested target userspace is Debian 13.
The controller owns the managed network domain and its routing/firewall/NAT policy. VPN
credentials, remote endpoints, cryptographic keys, and vendor-specific tunnel settings remain
administrator-owned.

Install host prerequisites before installing the bundle:

```sh
apt-get update
apt-get install -y python3 iproute2 iputils-ping nftables procps
```

Install the VPN implementation required by each example using the package command shown in that
example. The examples below are the Release-1 documented integration paths and are exercised by
the release documentation walkthrough.

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
log_level = "info"
helper_routing_interfaces = ":local"
helper_routing_policy = "peaceful"

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
accepted. Then verify real traffic to a destination covered by that Profile, for example:

```sh
ping -c 3 <profile-destination-ip>
```

The payload address is deployment-specific; use an address that is actually reachable through
the configured VPN.

Stopping `vpn-gate-alpha.service` stops a correctly bound VPN unit before managed-domain
teardown.

## WireGuard / wg-quick example

Install WireGuard on Debian 13:

```sh
apt-get install -y --no-install-recommends wireguard-tools
```

Use a dedicated configuration such as
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

After installing the wrapper unit, reload systemd:

```sh
systemctl daemon-reload
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

Start the controller and the WireGuard wrapper as described by the common procedure. In current
status, the Device must resolve to `wg-corp`; then verify real Profile payload before accepting
the integration.

## OpenConnect example

Install OpenConnect on Debian 13:

```sh
apt-get install -y --no-install-recommends openconnect
```

The following password-authenticated example is deliberately explicit so the non-interactive
systemd path is reproducible. Certificate/token deployments may replace only the authentication
arguments while preserving the namespace/policy-neutral integration boundary.

Create a stack-specific service:

```ini
[Unit]
Description=VPN-GATE OpenConnect %i
BindsTo=vpn-gate-alpha.service
After=vpn-gate-alpha.service

[Service]
Type=simple
NetworkNamespacePath=/run/netns/vpn-gate-alpha
EnvironmentFile=/etc/vpn-gate-alpha/openconnect-%i.env
ExecStart=/bin/sh -c 'printf "%%s\\n" "$VPN_GATE_OC_PASSWORD" | exec /usr/sbin/openconnect \
    --non-inter --passwd-on-stdin --user="$VPN_GATE_OC_USER" \
    --interface=vpn-%i \
    --script=/usr/lib/vpn-gate-alpha/openconnect-policy-neutral.sh \
    --config=/etc/vpn-gate-alpha/openconnect-%i.conf \
    --servercert="$VPN_GATE_OC_SERVERCERT" "$VPN_GATE_OC_SERVER"'
Restart=no

[Install]
WantedBy=multi-user.target
```

Example `/etc/vpn-gate-alpha/openconnect-corp.env`:

```sh
VPN_GATE_OC_SERVER=https://vpn.example.net/
VPN_GATE_OC_USER=alice
VPN_GATE_OC_PASSWORD=replace-me
VPN_GATE_OC_SERVERCERT=pin-sha256:replace-with-server-public-key-pin
```

Protect the environment file and reload the installed unit:

```sh
chmod 0600 /etc/vpn-gate-alpha/openconnect-corp.env
systemctl daemon-reload
```

Put protocol and other VPN-specific options in `openconnect-corp.conf`. Keep authentication
secrets outside the release bundle and protect them with normal host permissions. For
certificate/token authentication, replace the password-specific arguments consistently rather
than adding policy/routing hooks.

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

Start the controller and this OpenConnect service through the common procedure. Current status
must resolve the Device to `vpn-corp`; then verify real Profile payload.

## L2TP client integration

L2TP uses the same generic boundary. The administrator-owned L2TP/PPP stack must run inside
the managed namespace and create its PPP data-plane interface there.

Install the Debian 13 client implementation:

```sh
apt-get install -y --no-install-recommends xl2tpd ppp
```

For an exact `ppp0` deployment:

```toml
[device.corp]
enabled = true
expected_interfaces = ["ppp0"]
use_outbound_nat = true
allow_vpn_client = "udp>198.51.100.30:1701"
```

The PPP options used by the stack must not install a default route or policy hooks owned by
VPN-GATE. For example, create `/etc/ppp/options.vpn-gate-corp` with site-specific
authentication plus:

```text
nodefaultroute
noauth
noccp
nobsdcomp
nodeflate
nopcomp
noaccomp
mtu 1400
mru 1400
lcp-echo-interval 5
lcp-echo-failure 3
```

Create `/etc/xl2tpd/xl2tpd-vpn-gate-corp.conf`:

```ini
[global]
port = 1701

[lac corp]
lns = 198.51.100.30
pppoptfile = /etc/ppp/options.vpn-gate-corp
autodial = no
redial = no
length bit = yes
```

Create a dedicated service:

```ini
[Unit]
Description=VPN-GATE L2TP corp
BindsTo=vpn-gate-alpha.service
After=vpn-gate-alpha.service

[Service]
Type=simple
RuntimeDirectory=xl2tpd
RuntimeDirectoryMode=0755
NetworkNamespacePath=/run/netns/vpn-gate-alpha
ExecStart=/usr/sbin/xl2tpd -D \
    -c /etc/xl2tpd/xl2tpd-vpn-gate-corp.conf \
    -p /run/vpn-gate-l2tp-corp.pid \
    -C /run/vpn-gate-l2tp-corp-control
Restart=no
```

Reload systemd after installing the service:

```sh
systemctl daemon-reload
```

After starting the controller and L2TP service, request the documented LAC connection:

```sh
ip netns exec vpn-gate-alpha xl2tpd-control \
    -c /run/vpn-gate-l2tp-corp-control connect-lac corp
```

Current status must resolve the Device to `ppp0`; then verify real Profile payload.

Do not attach `ip-up`/`ip-down` hooks that modify VPN-GATE routes, RPDB, nftables, or NAT
state.

If L2TP is protected by IPsec, the additional IKE/ESP/NAT-T transport/control requirements are
outside this simple UDP/1701 example and must be represented/allowed according to the actual
underlay integration rather than inferred from the L2TP payload interface.

## Protective mode

Run the manual Protective-mode check only after one of the documented VPN integrations has a
confirmed current path and working Profile payload.

The installed release provides a root-only control client. First inspect the initial state:

```sh
vpn-gate-control protective status
```

The JSON response must have `"ok": true` and `"status": "inactive"` under
`protective`.

Enter Protective mode and inspect it again:

```sh
vpn-gate-control protective enter
vpn-gate-control protective status
```

Both commands must report success and the second status must report `"status": "active"`.
Repeat the same real Profile payload check used for the VPN integration; it must now fail while
the managed runtime objects and diagnostic files remain available.

Leave Protective mode and confirm the result:

```sh
vpn-gate-control protective leave
vpn-gate-control protective status
```

Successful leave must report `"status": "inactive"`. Repeat the real Profile payload check; it
must work again.

`enter` succeeds only after VPN-GATE freshly confirms the dedicated Protective gate. While
active, the controller blocks IPv4 traffic through the ordinary managed boundary in both
directions and forwarding between VPN paths, while preserving managed runtime objects and
diagnostic context.

The Manager periodically re-observes the gate and repairs exact owned drift. A final `leave`
first freshly confirms the applicable normal desired state and then removes the gate. If that
precondition or gate removal cannot be confirmed, `leave` returns non-zero and traffic remains
blocked/re-contained.

Independent authorized automation may use a separate source identity:

```sh
vpn-gate-control protective enter --source automation:maintenance
vpn-gate-control protective leave --source automation:maintenance
```

Sources are independent; one source cannot clear another source's request.

The current deployment mechanism is a root-only Unix socket at
`/run/vpn-gate-alpha/control.sock`. Socket/CLI are replaceable deployment machinery; the
Protective-mode semantics are owned by VPN-GATE rather than by this transport.

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

For each WireGuard, OpenConnect and L2TP example above, these operational checks are part of
the documented acceptance path, not optional troubleshooting steps.

Do not manually delete or rewrite VPN-GATE-owned namespace/routing/nftables state as a normal
recovery procedure.
