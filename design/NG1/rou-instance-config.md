# VPN-GATE NG1 — instance/bootstrap configuration schema version 1

Status: **normative for NG1 Draft 5**

Instance configuration is separate from router policy.

Example:

```toml
schema_version = 1

[instance]
namespace = "vpn-gate-rou0"
host_interface = "rouvpn0"
host_address = "192.0.2.1/30"
inner_address = "192.0.2.2/30"
publication_bind_address = "0.0.0.0"
router_config = "/etc/vpn-gateway/routers/rou0.toml"
state_file = "/var/lib/vpn-gateway/rou0/state.json"
```

All fields are required.

## Fields

- `namespace`: owned Linux network namespace name using safe characters
  `[A-Za-z0-9_.-]`, starting alphanumeric.
- `host_interface`: host-side veth name, Linux IFNAMSIZ constrained.
- `host_address`: stable host-side IPv4 interface address/prefix.
- `inner_address`: stable ROU-side IPv4 interface address/prefix.
- `publication_bind_address`: host-main-namespace IPv4 address used by publication
  sockets. `0.0.0.0` explicitly means wildcard.
- `router_config`: absolute path to router schema-v1 TOML.
- `state_file`: absolute path for durable runtime history, required to remain below
  `/var/lib/vpn-gateway` so the hardened systemd unit can grant the minimum persistent
  write scope.

The internal peer name is fixed to `host0` in schema version 1 and is not configurable.

Host/inner addresses must:

- be different;
- belong to the same IPv4 subnet;
- be usable endpoint addresses;
- may use RFC3021 `/31`.

No automatic address allocation exists in schema version 1.

## Instance identifier

The CLI/systemd instance identifier is not duplicated in the TOML file. It uses:

```text
[a-z0-9][a-z0-9-]*
```

The default production path is:

```text
/etc/vpn-gateway/instances/<instance-id>.toml
```

The CLI may accept an explicit instance-file override for testing/administration, but
systemd template operation uses the conventional path.


## systemd lifecycle

The reference `rouvpn@.service` uses:

- `ExecStartPre=rou prepare <id>`: create a fully absent instance or repair safe
  fail-closed bootstrap state of a fully present instance;
- `ExecStart=rou run <id>`: start the production runtime only after strict preparation;
- `ExecStopPost=rou contain <id>`: best-effort `ip_forward=0` containment.

`rou up <id>` enables and starts the instance service. `rou down <id>` disables/stops
the service, proves it inactive, then removes the namespace/veth appliance.
