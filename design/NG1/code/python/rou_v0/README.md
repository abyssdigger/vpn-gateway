# NG1 ROU v0 — executable reference prototype

Status: **ready for first live test**.

ROU v0 is intentionally not a generic configuration implementation. It is the smallest
complete NG1 appliance capable of proving lifecycle, real ocserv/OpenConnect transport,
profile routing, binding failover, fail-closed zero-path behavior, drift repair and
structural-integrity isolation.

## Hard-coded lab model

- namespace: `vpn-gate-rou0`;
- external host interface: `rouvpn0 = 192.0.2.1/30`;
- internal interface: `host0 = 192.0.2.2/30`;
- source ocserv config: `/etc/ocserv/ocserv.conf`;
- published transport: `44443/tcp` + `44443/udp` -> internal ocserv `44443`;
- binding selector: prefix `vpns`, network `172.20.130.0/29`, capacity `2`;
- one OUTBOUND profile;
- protected test destination: `172.21.201.19/32`;
- profile table: `100`;
- RPDB priority: `100`;
- unicast metrics: `10`, `20`;
- protected + terminal blackholes: protocol `201`, metric `65536`;
- unicast routes: protocol `202`.

These constants are deliberate. Generic config parsing starts only after the v0 lifecycle
and integrity gates pass.

## Files

- `rou_v0.py` — appliance bootstrap, process supervision, binding projection,
  reconciliation, verification and cleanup;
- `rou_v0_relay.py` — host-side TCP/UDP publication relay with independent UDP
  per-peer associations;
- `tests/test_rou_v0.py` — rootless projection and desired-state tests;
- `tests/relay_smoke.py` — rootless two-peer UDP relay smoke;
- `rou_v0_live_smoke.sh` — destructive live test for the dedicated `.107` test VM.

## Safety model

ROU owns the entire private network namespace. Any normal binding change or recoverable
owned routing/RPDB/firewall drift is handled under a conservative barrier:

    ip_forward=0
      -> full profile/RPDB/firewall projection
      -> verification
      -> ip_forward=1
      -> verification

Binding disappearance is a normal transport lifecycle event, not corruption. With no
admitted bindings, the profile table retains both the protected destination blackhole and
terminal blackhole default; FORWARD remains default DROP.

Loss of appliance infrastructure (`host0`, `rouvpn0`, their addresses or underlay default)
is treated as non-repairable structural integrity failure in v0. The controller closes
forwarding, exits non-zero and removes the owned appliance resources.

Firewall verification compares the canonical `iptables-legacy-save` state captured after a
verified apply. Route and RPDB verification use `ip -j` semantic state rather than textual
formatting.

## UDP publication

EXP-011 deliberately used one UDP peer association. ROU v0 removes that limitation:
every external UDP peer receives its own connected internal UDP socket and return-path
association, with idle expiry. This is required for simultaneous DTLS sessions from `pri`
and `sec`.

## Rootless checks

```sh
python3 -m py_compile rou_v0.py rou_v0_relay.py
python3 -m unittest discover -s tests -v
python3 tests/relay_smoke.py
bash -n rou_v0_live_smoke.sh
```

A generic container may not permit `ip netns`; that is not treated as a failed ROU test.
The live namespace/kernel gate is the dedicated Debian test VM.

## First live run on the test OC server

The harness is destructive to the temporary ROU instance and deliberately stops/starts
VPN sessions. Use only on the dedicated test VM.

1. Update the repository.
2. Stop the normal server:

```sh
systemctl stop ocserv
```

3. Verify `44443/tcp+udp` are free.
4. Run from this directory:

```sh
sudo ./rou_v0_live_smoke.sh
```

The harness restores the normal `ocserv.service` in its EXIT trap.

## Live hypotheses

The harness verifies:

1. namespace/veth/ocserv/publication startup;
2. simultaneous CSTP/DTLS for both existing clients;
3. two-path profile routes plus protected and terminal blackholes;
4. real payload forwarding to `172.21.201.19`;
5. preferred OC worker/interface disappearance with survivor metric preserved and payload
   failover;
6. fresh reconnect/re-admission without survivor churn;
7. zero-binding explicit fail-closed state;
8. owned route drift repair under an observed `ip_forward=0` barrier;
9. owned firewall drift repair under the same barrier;
10. non-repairable `host0` integrity loss causing fail-closed controller exit and complete
    appliance cleanup.

Only after this live gate passes should v0 grow a configuration parser, multiple profiles,
additional transports or systemd packaging.
