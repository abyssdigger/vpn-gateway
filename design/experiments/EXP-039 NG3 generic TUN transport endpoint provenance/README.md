# EXP-039 — generic TUN transport endpoint provenance

## Purpose

Determine whether a transport endpoint/peer address is an organic observable property of a
Linux point-to-point TUN data-plane interface, or whether VPN-GATE needs integration-specific
provenance to associate a current concrete interface with its transport peer.

This experiment is deliberately narrower than OpenConnect/WireGuard integration discovery.
It tests the generic Linux boundary that a shared interface-discovery implementation could
legitimately rely on.

## Requirement/design scope

**Implements evidence for:**
- `VPNG0001-R1.R3.R5`;
- `VPNG0001-R1.R3.R5.C1`;
- `VPNG0001-R1.R3.R5.C1.R1`.

The experiment does not select named-endpoint config syntax and does not make endpoint
provenance a first-release prerequisite.

## Setup

One privileged userspace process:

1. creates and holds a Linux TUN interface through `/dev/net/tun`;
2. configures an inner point-to-point IPv4 peer on that interface;
3. opens a separate connected UDP socket representing a VPN transport connection;
4. observes the TUN interface through normal `ip -j -d link` and `ip -j addr` discovery;
5. replaces only the userspace transport socket's remote endpoint and repeats observation.

TEST-NET addresses are used as transport socket peers; UDP `connect()` does not require a
remote service to exist.

## Hypotheses

- **H1:** the created TUN is observable as a point-to-point data-plane interface;
- **H2:** the configured inner/network-layer peer is observable in interface address state;
- **H3:** the userspace transport peer IP is absent from generic TUN link/address state;
- **H4:** changing only the userspace transport peer leaves the generic TUN interface
  observation unchanged while `getpeername()` changes.

## Decision rule

If H1-H4 pass, transport peer identity is **not** accepted as an organic generic property of
a point-to-point TUN interface. Endpoint provenance must then come from an
integration-specific discovery/onboarding fact and be attached to the exact current path
binding; generic interface discovery must not infer it from TUN point-to-point state.

If generic interface state changes to expose the userspace transport peer, the architecture
must be revisited before accepting the opposite conclusion.
