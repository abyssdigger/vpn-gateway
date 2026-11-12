# EXP-019 — NG1 WireGuard availability evidence

**Status:** PREPARED — future DeviceManager evidence  
**Architecture baseline:** NG1 Draft 5 + EXP-016  
**Type:** real WireGuard-in-netns liveness experiment

## Purpose

Determine which observable can justify normalized WireGuard `UNAVAILABLE` while the bound
WireGuard interface itself remains present.

The experiment intentionally does not define user-facing DeviceManager configuration. It
tests raw evidence only.

## Questions

1. Does `wg0` remain present/up when the UDP underlay path is broken?
2. Does an active probe to the peer's tunnel address fail specifically during that break and
   recover without replacing the WireGuard interface generation?
3. What happens to `wg show ... latest-handshakes` during a short outage/recovery?
4. Is latest-handshake age alone sufficient for a prompt availability decision, or must
   DeviceManager use an active/protocol-specific probe?

## Topology

Two disposable namespaces:

```text
wg-a: a0 192.0.2.1/30 ---- 192.0.2.2/30 b0 :wg-b
      wg0 10.23.0.1/30      10.23.0.2/30 wg0
```

WireGuard peers use the underlay addresses as UDP endpoints. The tunnel addresses create a
normal connected route, so the active probe does not require Profile routing tables.

## Procedure

1. create both namespaces, veth underlay and WireGuard interfaces;
2. configure reciprocal peers and PersistentKeepalive;
3. prove tunnel ping and record A's wg0 ifindex + latest successful handshake;
4. break B's underlay while leaving both wg0 interfaces untouched;
5. prove A's wg0 identity remains unchanged and tunnel ping fails;
6. record latest-handshake evidence during the outage;
7. restore underlay;
8. prove tunnel ping recovers without replacing A's wg0 generation;
9. record post-recovery handshake evidence.

## Decision boundary

A positive production UNAVAILABLE trigger must be based on evidence that actually proves
the particular Device path unavailable.

If short outage/recovery does not force a new successful WireGuard handshake, handshake age
alone is not a sufficient fast liveness signal. An active probe may be suitable evidence,
but its target/admission semantics would then require a separate DeviceManager design
decision and human agreement because that changes user-facing configuration.

## Artifact

`exp-019-wireguard-availability-ci.sh`
