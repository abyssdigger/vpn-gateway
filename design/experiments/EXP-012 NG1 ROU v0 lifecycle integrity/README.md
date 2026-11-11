# EXP-012 — NG1 ROU v0 lifecycle and integrity live smoke

Status: **COMPLETE — PASS**

## Objective

Run the first complete executable ROU appliance against the dedicated Debian/ocserv test
host and validate the NG1 control loop end to end.

This is deliberately not a generic configuration test. ROU v0 hard-codes the known lab
model so the experiment isolates lifecycle, routing, fail-closed behavior and integrity
recovery before configuration complexity is introduced.

## Implementation under test

`design/NG1/code/python/rou_v0/`

- `rou_v0.py` — namespace/bootstrap/controller/reconciliation;
- `rou_v0_relay.py` — TCP relay plus independent per-peer UDP associations;
- `rou_v0_live_smoke.sh` — live harness.

Hard-coded model:

    main NS:  rouvpn0 192.0.2.1/30
                    |
                   veth
                    |
    ROU NS:   host0    192.0.2.2/30

    publication: 44443/tcp + 44443/udp
          -> ocserv 192.0.2.2:44443

    binding: vpns+ / 172.20.130.0/29 / capacity 2
    profile: OUTBOUND
    target:  172.21.201.19/32
    table:   100
    rule:    priority 100, iif host0, target -> table 100
    metrics: 10, 20
    route protocols: 202 unicast, 201 blackhole
    blackhole metric: 65536

## Preconditions

Dedicated test OC server:

- Debian 13;
- normal `ocserv.service` known-good on TCP/UDP 44443;
- clients `pri` and `sec` configured to reconnect automatically;
- both client VPN paths can reach `172.21.201.19`;
- iptables-legacy selected and available;
- repository updated to the ROU v0 implementation.

Before starting the harness the normal `ocserv.service` is stopped and TCP/UDP 44443 must
be free. The harness EXIT trap attempts to restore the normal service.

## Safety model under test

ROU owns the complete private namespace. A binding transition or recoverable owned-state
drift is reconciled under:

    ip_forward=0
      -> complete owned-state projection
      -> verification
      -> ip_forward=1
      -> verification

Loss of core appliance infrastructure is not repaired in place by v0. It must force
fail-closed exit and cleanup.

## Hypotheses

### H1 — appliance startup

ROU creates its namespace/veth, derives and starts ocserv inside the namespace, and opens
the host-side TCP/UDP publication endpoint.

### H2 — real multi-peer publication

Both existing clients, `pri` and `sec`, reconnect through the publication relay and
simultaneously establish DTLS.

This is the live gate for the v0 per-peer UDP association implementation.

### H3 — initial profile projection

Two eligible `vpnsXX` bindings are admitted at metrics 10 and 20. Table 100 contains:

- two unicast routes for the protected target;
- an explicit protected-target blackhole;
- terminal blackhole default.

### H4 — real payload path

A temporary host route sends `172.21.201.19/32` through `rouvpn0`. Ping succeeds through
the preferred admitted OC binding.

### H5 — preferred binding disappearance

The preferred ocserv worker is terminated. Its interface disappears as a normal transport
event. The surviving binding keeps metric 20 and real payload still reaches the target.

### H6 — fresh binding return

The client reconnects, creating a fresh concrete binding. It is admitted without survivor
metric churn.

### H7 — zero-path fail-closed

Both VPN workers are terminated. With zero admitted bindings:

- no profile unicast route remains;
- protected blackhole remains;
- terminal blackhole remains;
- payload ping fails.

### H8 — owned route drift recovery

The harness deletes the preferred proto-202 route. ROU detects the mismatch, exposes an
observable `ip_forward=0` barrier, rebuilds/verifies the desired state and restores
forwarding.

### H9 — owned firewall drift recovery

The harness inserts an unauthorized FORWARD accept rule inside the ROU namespace. ROU
detects it, repairs the complete owned firewall under the forwarding barrier and restores
forwarding only after verification.

### H10 — structural infrastructure failure

The harness deletes internal `host0`. ROU must treat this as structural appliance
integrity loss:

- disable forwarding;
- exit non-zero;
- remove the namespace/veth;
- close publication sockets;
- leave no owned appliance runtime state.

## PASS criterion

All H1-H10 must pass and the harness must print:

    OVERALL=PASS

A failure is evidence for the next v0 correction; it must not be papered over by weakening
the hypothesis.

## Live result

The dedicated Debian 13 live run on 2026-11-11 completed all H1-H10 successfully and
printed `OVERALL=PASS`.

Result: [EXP-012-result-20261111.md](EXP-012-result-20261111.md)

## Rootless evidence before live run

Before EXP-012 registration the implementation passed:

- Python bytecode compilation;
- 8 rootless unit tests for binding projection and fail-closed desired state;
- two-peer UDP relay smoke with independent return-path associations;
- `bash -n` for the live harness.

The available sandbox did not permit `ip netns`
(`mount --make-shared /run/netns: Operation not permitted`). The dedicated Debian 13 live
run subsequently closed that evidence gap: namespace/kernel lifecycle, two-client DTLS,
payload failover, zero-path fail-closed behavior, drift repair barriers and structural
teardown all passed.
