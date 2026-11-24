# EXP-072 — NG3 managed-L3 endpoint host bootstrap

Status: **PASS** — production device-only host bootstrap semantics confirmed on routed veth + Proxy ARP and netkit L3

## Question

Can the selected paired-RPDB host-bootstrap semantics use a device-only managed-L3 endpoint
without a peer gateway IP, and do the routed-veth/Proxy-ARP and netkit-L3 backends expose the
same observable routing behavior?

## Why this experiment

EXP-070 proved device-only point routing for both candidate endpoint shapes. EXP-071 found no
material dataplane-cost difference. Release-1, however, needs the stronger existing bootstrap
semantics:

- broad managed destination including `0.0.0.0/0`;
- strictly-more-specific ordinary `main` route preservation;
- less-specific ordinary route not overriding a more-specific managed destination;
- immediate recognition of a newly-added more-specific ordinary `main` route;
- stack-ingress bypass so packets already leaving STACK are not captured back into STACK;
- exact owner cleanup without mutation of ordinary `main`.

## Compared backends

1. `routed-veth-proxy-arp` — unnumbered veth pair, Proxy ARP on both endpoints.
2. `netkit-l3` — L3 netkit pair, no BPF program.

The host-bootstrap desired state is built by the production `build_linux_host_bootstrap_desired`
with `inner_gateway=None`, and converged by the production `LinuxHostBootstrapBackend`.

## Topology

```text
LAN -- HOST -- managed L3 endpoint -- STACK -- REMOTE
        |
        +-- ordinary uplink/GW
        |
        `-- ordinary static network
```

REMOTE owns test destinations reached through STACK. STATIC and GW own ordinary destinations
used to prove `main` specificity preservation.

## Required result

For each supported backend:

- `8.8.8.8` under managed `/0` resolves through the host boundary device with no gateway;
- an ordinary `203.0.113.0/24` main route beats managed `/0` for `203.0.113.9`;
- managed `203.0.113.128/25` beats that less-specific ordinary `/24` for `203.0.113.129`;
- a runtime-added ordinary `/32` immediately beats managed `/0`;
- actual LAN -> REMOTE ping succeeds and its return traffic is not reflected back into STACK;
- cleanup removes only the bootstrap owner and leaves ordinary main state identical.

Netkit unsupported on a runner is reported separately; it does not invalidate routed-veth
evidence, but the dual-backend equivalence claim requires at least one successful netkit run.

## Result

See `EXP-072-result-20261119.md`. Workflow run `44598508737`, job
`linux-managed-l3-host-bootstrap` (`135823381254`) completed with `EXP072_RESULT=PASS netkit=True`.
