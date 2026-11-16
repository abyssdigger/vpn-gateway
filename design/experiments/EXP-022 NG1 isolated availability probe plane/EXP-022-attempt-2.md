# EXP-022 attempt 2 — invalid weak-host ARP control

Date: 2026-11-13

Result: **HARNESS INVALIDATED; architecture hypothesis not failed**

The corrected topology moved `203.0.113.22/32` to peer loopback interfaces and installed
gateway routes, but the pre-control-plane negative assertion still failed:

```text
STAGE 3: prove bound probe has no usable vpn0 route before control plane
FAIL: bound probe unexpectedly reached routed target before probe plane existed
```

Root cause: Linux IPv4 uses weak-host ARP behavior by default. With
`net.ipv4.conf.*.arp_ignore=0`, a host may answer an ARP request arriving on one interface
for any local IPv4 address configured on another interface. Therefore the peer could answer
ARP for the target /32 assigned to `lo`, making the supposedly routed target directly
reachable at L2.

Correction:

- set `net.ipv4.conf.all.arp_ignore=1` in both peer namespaces;
- retain the target /32 on peer loopback;
- keep normal and probe routes through explicit peer gateway addresses;
- assert that the target never appears as a direct neighbor on `vpn0`.

A fresh target run is required.
