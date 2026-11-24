# EXP-071 — managed-boundary dataplane race

Status: **PASS** — two independent CI runs found no material netkit/veth dataplane difference

## Question

After EXP-070 proved two product-compatible host-visible managed-stack endpoints, is the
Debian-12-compatible `routed veth + Proxy ARP` dataplane materially more expensive than
plain `netkit L3` when both are used only as the managed L3 boundary?

The experiment deliberately compares steady-state forwarding cost, not lifecycle/configuration cost.

## Candidates

1. **netkit L3**
   - HOST primary `vpng0`;
   - STACK peer `stack0`;
   - device-only routes on both sides;
   - no BPF program and default scrub behavior.

2. **routed veth + Proxy ARP**
   - ordinary veth pair `vpng0 <-> stack0`;
   - unnumbered boundary;
   - device-only routes on both sides;
   - Proxy ARP only supplies Ethernet neighbour resolution.

3. **routed veth + explicit peer next-hop** — control
   - same veth pair;
   - /30 boundary addresses;
   - routes use `via <peer>`.
   - This separates ordinary veth packet cost from Proxy-ARP/device-only representation cost.

## Topology

```text
SRC namespace
  192.0.2.2
      |
HOST namespace
  192.0.2.1
      |
  boundary candidate
      |
STACK namespace
  198.51.100.1
      |
DST namespace
  198.51.100.2
```

SRC and DST attachment veths are identical for every candidate. Only the HOST<->STACK boundary
changes.

## Workload

For every candidate:

- warm-up reachability before measurement;
- TCP iperf3;
- 1 stream and 4 parallel streams;
- forward and reverse directions;
- three measured repetitions per case;
- same hosted runner/job;
- median throughput and iperf-reported endpoint CPU are retained.

This is a **relative CI microbenchmark**, not an absolute production throughput claim.
Hosted-runner scheduling noise and iperf userspace cost can obscure small dataplane differences.

## Acceptance / interpretation

The experiment does not require a particular winner.

- If routed veth is close to netkit within run-to-run noise, platform availability dominates.
- If netkit has a stable material advantage, `auto` backend selection may prefer netkit on supported kernels.
- The explicit-next-hop veth control indicates whether Proxy ARP changes steady-state cost versus
  the veth primitive itself.

No architecture or config semantics are changed until the result is reviewed.
