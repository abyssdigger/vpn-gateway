# EXP-020 — NG1 OpenConnect availability evidence

**Status:** PREPARED — raw OpenConnect availability evidence  
**Architecture baseline:** NG1 Draft 5 + first production source baseline  
**Type:** real ocserv/OpenConnect-in-netns liveness experiment

## Purpose

Determine what raw evidence can justify normalized OpenConnect `UNAVAILABLE` while an
OpenConnect tunnel interface is still considered bound by DeviceEngine.

This experiment intentionally does not define DeviceManager configuration or policy.

## Questions

1. Does the OpenConnect tunnel interface remain present, with the same ifindex, during a
   short outer-transport outage?
2. Does a tunnel-bound active probe fail during that outage?
3. Does OpenConnect recover the data path without replacing the tunnel-interface
   generation?
4. If the interface is replaced or the client process exits instead, is ordinary binding
   lifecycle already sufficient to express the outage?
5. Which protocol/process observables are useful only as diagnostics versus positive
   availability evidence?

## Disposable topology

Two network namespaces:

```text
oc-srv: s0 192.0.2.1/30 ---- 192.0.2.2/30 c0 :oc-cli

ocserv listens on 192.0.2.1:44443
OpenConnect runs in oc-cli and creates explicit interface oc0
server-side probe target: 10.99.0.1/32, pushed through the VPN
```

The experiment uses an ephemeral self-signed server certificate and ephemeral test
credentials generated inside the CI job. No secret material is persisted.

## Procedure

1. create the two namespaces and underlay veth;
2. generate ephemeral ocserv certificate/password database;
3. start ocserv in oc-srv;
4. start OpenConnect in oc-cli with explicit interface name `oc0`;
5. prove the pushed probe target is reachable through the tunnel;
6. record OpenConnect PID, oc0 ifindex and IPv4 state;
7. break only the outer underlay while leaving both processes untouched;
8. determine:
   - whether OpenConnect remains running;
   - whether oc0 remains present;
   - whether its ifindex is unchanged;
   - whether the tunnel-bound probe fails;
9. restore underlay;
10. wait for reconnect/recovery and determine whether the probe recovers on the same
    interface generation.

## Interpretation

Possible outcomes:

- **same generation survives + probe fails/recoveries**: interface presence is not
  availability evidence; DeviceManager needs a positive path/protocol-specific detector.
- **client exits or interface disappears/replaces promptly**: ordinary binding lifecycle
  may already provide sufficient fail-closed behavior for that outage class.
- **mixed behavior**: availability semantics must account for the reconnect state machine
  explicitly.

## Gate consequence

EXP-020 closes only the raw OpenConnect evidence question. Choosing probe target, cadence,
failure threshold or user-visible DeviceManager configuration remains a separate product
decision requiring human agreement.
