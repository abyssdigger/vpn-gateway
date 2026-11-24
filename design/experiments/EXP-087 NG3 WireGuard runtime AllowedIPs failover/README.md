# EXP-087 — WireGuard runtime AllowedIPs failover

**Status:** COMPLETE — PASS / FEASIBILITY CONFIRMED  
**Date:** 2026-11-24

## Question

Can one WireGuard interface keep multiple peers, probe their availability independently, and
move one shared payload prefix between them at runtime without editing a WireGuard config file?

This is experimental evidence only. It does not add Release-1 product behavior, configuration,
architecture, or service-manager integration.

## Topology

One client namespace owns one `wg0` and two WireGuard peers on separate underlay links.

Each peer permanently owns one unique in-tunnel probe address:

- peer A: `10.201.0.1/32`;
- peer B: `10.201.0.2/32`.

Both remote namespaces independently expose the same payload address `10.77.0.1`; the
shared payload ownership candidate is `10.77.0.0/24`.

The experiment models desired WireGuard state as:

```text
peer A = permanent probe /32 + shared payload prefix iff selected
peer B = permanent probe /32 + shared payload prefix iff selected
```

and applies that state only with runtime `wg set wg0 peer ... allowed-ips ...` commands.

## Hypotheses

### H1 — runtime mutation needs no config-file rewrite

`wg set` can replace the current `AllowedIPs` set for both peers while `wg0` remains up.
The test does not create or edit `wg0.conf`.

### H2 — the external transport endpoint is not a usable current probe target through `wg0`

The peer underlay IP is reachable on the underlay, but an ICMP probe forced through `wg0`
to that same transport IP fails when that IP is not owned by any WireGuard peer
`AllowedIPs`.

This checks the current VPN-GATE probe shape (`ping -I <vpn-if> <target>`) rather than merely
checking host reachability.

### H3 — permanent peer-specific in-tunnel /32 targets discriminate peers behind one wg0

With both peers alive, `ping -I wg0 10.201.0.1` reaches only peer A and
`ping -I wg0 10.201.0.2` reaches only peer B. Their permanent probe prefixes coexist while
the shared payload prefix belongs to only one peer.

### H4 — availability-driven desired state can move the shared prefix at runtime

After peer A is made unavailable while peer B remains reachable, one runtime desired-state
apply moves `10.77.0.0/24` from A to B while preserving both permanent probe /32s.
Payload then uses B.

### H5 — recovery is reversible

After peer A becomes reachable again, runtime desired-state apply can move the shared payload
prefix back to A and payload follows it.

## Non-goals

- no production code;
- no service-manager integration;
- no Release-1 config grammar change;
- no claim that the update is transactionally atomic under concurrent payload;
- no claim that probing the peer's in-tunnel address proves reachability of every remote
  payload destination behind that peer.

## Acceptance markers

A successful run must emit:

```text
EXP087_RUNTIME_ONLY_ALLOWEDIPS=PASS
EXP087_TRANSPORT_ENDPOINT_PROBE_UNSUITABLE=PASS
EXP087_PEER_PROBE_DISCRIMINATION=PASS
EXP087_FAILOVER_TO_B=PASS
EXP087_RECOVERY_TO_A=PASS
EXP087_RESULT=PASS
```


## Result

Privileged Linux/WireGuard evidence passed at source commit
`4ae88f67d3cd02f64f04f99e9a62cb3876abea76`, GitHub Actions run
`45333802569`, job `linux-wireguard-multipeer` (`138241133580`).

All H1-H5 passed:

- `AllowedIPs` ownership was changed at runtime using only `wg set`; no config file was
  created, edited or reloaded;
- the reachable underlay transport endpoint was not a usable ICMP target when the probe was
  forced through `wg0`;
- permanent peer-specific in-tunnel `/32` targets independently selected peer A and peer B
  behind the same `wg0`;
- moving the shared payload prefix to B after A became unavailable moved real payload to B;
- restoring A and moving the shared prefix back moved real payload back to A.

Detailed evidence: [EXP-087-result-20261124.md](EXP-087-result-20261124.md).
