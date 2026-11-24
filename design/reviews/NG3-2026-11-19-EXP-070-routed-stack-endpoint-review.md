# VPN-GATE NG3 — EXP-070 routed stack endpoint review

**Date:** 2026-11-19  
**Cycle branch:** `ng3-exp070-routed-stack-endpoint`

## Scope

Review of EXP-070 evidence for presenting the managed stack as a routed host-visible endpoint while
keeping Profile policy and optional ordinary-side SNAT inside the managed stack.

The review does not select a replacement architecture. Registry disposition remains
`pending_decision`.

## Evidence reviewed

Primary modern-runner evidence:

- `netkit L3`: device-only host route **PASS**;
- `netkit L3` stack-side SNAT/reverse-NAT **PASS**;
- neighboring no-SNAT flow **PASS**;
- `meta mark` across netkit with explicit `scrub none` **PASS**;
- IPvlan L3S external-to-stack reachability **PASS**, but the tested host-sibling/device-route and
  stack-SNAT shapes **FAIL**;
- routed veth without Proxy ARP: device-only route **FAIL** with unresolved neighbour state;
- routed veth with explicit peer next-hop: **PASS**;
- routed veth with device-only routes + Proxy ARP: **PASS**, both unnumbered and /32-peer forms.

Debian 12 portability evidence:

- guest OS: Debian GNU/Linux 12 (bookworm);
- guest kernel: `6.1.0-56-cloud-amd64`;
- guest iproute2: `6.1.0`;
- no-Proxy-ARP device-only route: **EXPECTED FAIL**, neighbour `INCOMPLETE`;
- unnumbered routed veth + Proxy ARP: **PASS**;
- host route remained `10.70.0.2 dev vpng0 scope link`;
- stack reverse route remained `192.0.2.2 dev stack0 scope link`.

Privileged Debian-12 run:

- workflow run `44574019867`;
- job `linux-debian12-routed-veth` / `135736626574`;
- guest probe result: `EXP070_D12_RESULT=PASS`.

## Distinguishing value

The routed-veth result is distinguishing rather than a generic connectivity success.

Without Proxy ARP, the host reaches the exact expected failure point: Ethernet neighbour resolution
for the routed remote destination remains `INCOMPLETE`/`FAILED`.

With Proxy ARP enabled, the route syntax remains device-only while the opposite veth endpoint
answers neighbour discovery for prefixes that are actually routed behind it. End-to-end IP
forwarding then succeeds without userspace forwarding or NAT in that phase.

The Debian 12 guest repeats the same negative/positive distinction on an actual Linux 6.1 kernel,
so the result is not an artifact of the newer hosted-runner kernel.

## Scope limits

- The IPvlan negative results reject only the tested EXP-070 shapes; they are not a general IPvlan
  impossibility claim.
- IPv6 NDP/proxy-NDP has not yet been exercised in this experiment.
- Performance comparison between routed veth, IPvlan L3 and netkit L3 is not part of this result.
- No architecture selection is implied by the experiment result.
- The QEMU/cloud-init defects encountered while preparing the Debian 12 run were harness packaging
  defects and occurred before guest network evidence; the final guest run is clean.

## Requirement-state inventory

No requirement semantics are changed by EXP-070.

- active `unreal`: none observed;
- active `broken`: none observed;
- active `rejected_closure`: none observed;
- accumulated resolved `decomp`: unchanged.

## Verdict

**ACCEPT.**

EXP-070 supplies sufficient lower-level evidence that a Debian-12-compatible host-visible
`vpng0` can be realized as an ordinary routed veth with device-only host routes when Proxy ARP
provides the required Ethernet neighbour-resolution facade. The modern `netkit L3` candidate is
also technically proven. Choosing between them, or retaining the existing behavior-lane design,
is a separate architecture disposition.
