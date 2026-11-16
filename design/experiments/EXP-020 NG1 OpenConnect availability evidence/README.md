# EXP-020 — NG1 OpenConnect availability evidence

> **Current interpretation:** this experiment proves that OpenConnect process/interface
> presence is insufficient as a path-liveness condition. It does not define global
> interface availability. In the current model an active probe may be one condition used
> to decide whether a concrete OpenConnect binding is AVAILABLE in a particular Profile.

**Status:** PASS — raw OpenConnect availability evidence  
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


## Attempt history

### Attempt 1 — HARNESS DIAGNOSTIC GAP

The first GitHub run failed while starting OpenConnect, but the harness used `set -e` and
redirected the client log, so it exited before printing the actual failure.

No availability hypothesis was exercised. Safe stage markers and explicit client-start
error reporting were added.

### Attempt 2 — CI OCSERV WORKER/TLS ENVIRONMENT ISSUE

The instrumented run reached ocserv and TCP connect, then OpenConnect failed TLS with:

```text
Connected to 192.0.2.1:44443
SSL negotiation with 192.0.2.1
SSL connection failure: Error in the pull function.
```

ocserv was listening, but the disposable runtime used a root-private temporary directory
and default worker isolation. The hypothesis had still not been exercised.

For this liveness-only experiment the harness:

- made the ephemeral runtime directory traversable by the configured daemon group;
- made ephemeral credential material readable where required;
- disabled ocserv worker isolation to remove an unrelated hosted-runner/seccomp variable;
- enabled detailed ocserv logging.

This does not change production ROU or ocserv hardening policy.

### Attempt 3 — PASS

The corrected disposable topology reached the intended experiment.

Observed:

```text
PASS A: OpenConnect tunnel established ifindex=2 pid=4935
OUTAGE_CLIENT_ALIVE=1
OUTAGE_INTERFACE_PRESENT=1
OUTAGE_OLD_IFINDEX=2
OUTAGE_CURRENT_IFINDEX=2
PASS B: tunnel-bound active probe failed during outer outage
RECOVERY_IFINDEX=2
OBSERVATION: recovery reused the same OpenConnect interface generation
PASS C: active tunnel probe recovered
EXP_020_OPENCONNECT_AVAILABILITY_EVIDENCE=PASS
```

## Result and architectural consequence

The experiment establishes for the tested OpenConnect reconnect behavior:

1. OpenConnect process presence is not positive path-liveness evidence;
2. tunnel-interface presence is not positive path-liveness evidence;
3. a short outer-transport outage can leave the same concrete `(ifname,ifindex)`
   generation bound while the payload path is unusable;
4. the same interface generation can recover when outer transport returns;
5. a tunnel-bound active path probe distinguished live -> unavailable -> live in exactly
   that retained-generation window.

Together with EXP-019, both current first-class transports therefore demonstrate the same
architectural need: normalized availability is logically independent from binding
presence.

Neither experiment chooses production cadence, timeout, failure threshold, recovery
threshold or probe target. Those are DeviceManager product-policy/configuration semantics
and require a separate reviewed decision.
