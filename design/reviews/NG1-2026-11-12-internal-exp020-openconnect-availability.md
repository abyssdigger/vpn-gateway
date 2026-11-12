# Internal review — EXP-020 OpenConnect availability evidence

Date: 2026-11-12

## Scope

Reviewed the disposable ocserv/OpenConnect topology, corrected harness attempts and final
PASS evidence for the future DeviceManager availability question.

## Findings

### F1 — initial harness failure hid OpenConnect startup diagnostics

Disposition: fixed.

Client startup is now handled explicitly and prints both OpenConnect and ocserv logs on
failure. No availability conclusion was taken from the failed attempts.

### F2 — hosted-runner ocserv worker isolation/runtime permissions were unrelated variables

Disposition: fixed for the experiment only.

The liveness experiment does not test ocserv hardening. Worker isolation was disabled and
ephemeral runtime permissions were adjusted so the harness could reach the transport
outage/recovery hypothesis. Production deployment semantics were not changed.

### F3 — final evidence is sufficient for the stated raw-evidence question

The PASS run proved all observations needed for this experiment:

- OpenConnect process remained alive;
- tunnel interface remained present;
- its ifindex remained unchanged during the outage;
- tunnel-bound active probe failed;
- recovery occurred on the same interface generation.

Therefore binding/process presence cannot be promoted to positive AVAILABLE evidence for
OpenConnect.

The experiment intentionally does **not** prove a production timeout, cadence, failure
threshold, recovery threshold or universal probe target. Inferring those values would
exceed the evidence.

## Cross-transport consequence

EXP-019 (WireGuard) and EXP-020 (OpenConnect) now agree on the architectural boundary:

    binding identity != availability

Both transports can retain one concrete interface generation while payload reachability is
temporarily lost and later restored.

A future DeviceManager availability provider is therefore justified, but its
transport-specific evidence/configuration remains a product-policy decision.

## Rust-alignment review

Availability should remain a normalized enum/value supplied to DeviceEngine/Planner by a
provider boundary. Probe/process/protocol-specific machinery belongs outside the routing
core and can later map to Rust traits/providers without changing TrafficEngine.

## Verdict

CLOSED. EXP-020 PASS is valid for the raw-evidence scope.

The next step is a DeviceManager availability-policy design review requiring human
agreement because it introduces user-visible health-check semantics/configuration.
