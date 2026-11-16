# EXP-022 attempt 1 — invalid direct-link control

Date: 2026-11-13

Result: **HARNESS INVALIDATED; architecture hypothesis not failed**

The run passed ordinary-path isolation through Stage 8, then exact-ifindex reuse caused:

```text
EXACT_IFINDEX_REUSE_SUPPORTED=1
EXACT_IFINDEX_REUSED=5
FAIL: exact-ifindex reuse unexpectedly restored full probe plane without probe route
```

Inspection found that the experiment target `203.0.113.22/32` was assigned directly to
both peer veth interfaces. That made `ping -I vpn0` insufficient evidence that the
dedicated probe routing table was actually used: a device-bound ping could reach the
directly attached target even when the intended probe-table route had disappeared.

Therefore PASS C/E/F from this attempt remain useful evidence about interface binding and
alternate-path isolation, but they do **not** prove the dedicated RPDB/table dependency.

Correction:

- move the duplicate target /32 onto peer loopback interfaces;
- route main traffic via `198.18.222.1 dev alt0`;
- route probe traffic in table 6022 via `198.18.221.1 dev vpn0`;
- add a pre-control-plane negative assertion that bound `ping -I vpn0` cannot reach the
  routed target;
- add selector-specific `ip route get ... uid ... ipproto icmp oif vpn0` evidence.

A fresh target run is required.
