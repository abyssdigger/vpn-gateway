# VPN-GATE NG3 — EXP-071 managed-boundary dataplane race review

**Date:** 2026-11-19  
**Cycle branch:** `ng3-exp071-boundary-dataplane-race`

## Scope

Review of relative steady-state dataplane cost for the two EXP-070 managed-L3-endpoint candidates:

- plain `netkit L3`;
- routed `veth + Proxy ARP`.

An explicit-peer-next-hop veth variant is retained as a control for the cost of Proxy-ARP
representation versus the veth primitive itself.

No architecture selection is made here.

## Evidence

Two independent CI executions completed the full matrix:

- 1 TCP stream / 4 TCP streams;
- forward / reverse;
- three repetitions;
- alternating backend order.

Run A used Linux `7.0.0-1019-azure`.  
Run B used Linux `7.0.0-1016-aws`.

Absolute throughput differed substantially between runners, but relative backend ratios remained
near unity.

### netkit / veth+Proxy-ARP

Run A:

- `0.977 / 1.029 / 1.000 / 0.995`.

Run B:

- `1.005 / 1.006 / 1.001 / 0.995`.

No workload shows a stable material netkit advantage.

### veth+Proxy-ARP / veth+explicit-via

Run A:

- `1.013 / 0.985 / 1.007 / 0.998`.

Run B:

- `0.997 / 0.995 / 0.997 / 1.007`.

Therefore the tested Proxy-ARP representation does not impose a measurable steady-state
dataplane penalty relative to ordinary routed veth with an explicit peer IP.

Endpoint CPU medians were likewise effectively equal for matched workloads. The four-stream cases
saturated the hosted runner and are useful as throughput saturation points, not fine-grained
CPU-efficiency measurements.

## Architectural meaning

The result removes performance as a demonstrated reason to prefer `netkit L3` over
`routed veth + Proxy ARP`.

Together with EXP-070, both mechanisms can plausibly implement one product-level
`managed L3 endpoint` contract:

- stable HOST-visible `vpng0`;
- device-directed managed routes;
- Profile policy, firewall and optional gateway NAT remain inside STACK;
- backend selection can be a platform realization detail.

This review does not yet decide whether `auto` selects netkit when available or whether routed
veth should simply be the universal backend. That is a separate architecture decision.

## Scope limits

- This is a local CI microbenchmark, not a production capacity benchmark.
- Tail latency and VPN-crypto interaction are not measured.
- IPvlan L3 is deliberately not ranked because it cannot realize the same peer topology without
  changing the packet path.
- No requirement semantics are changed by this experiment.

## Requirement-state inventory

- active `unreal`: none observed;
- active `broken`: none observed;
- active `rejected_closure`: none observed;
- accumulated resolved `decomp`: unchanged.

## Verdict

**ACCEPT.**

EXP-071 demonstrates that, at the resolution of two materially different hosted runners, plain
netkit L3 and routed veth + Proxy ARP have effectively identical steady-state forwarding cost for
the tested managed-boundary workload.
