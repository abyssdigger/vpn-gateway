# NG3 WireGuard peer-probe executor review — 2026-11-25

**Review unit:** D.002 production peer-probe execution port  
**Source reviewed:** `a3ec1d1cb2705d87883c9e9b292ac85c0f7e7b66`  
**Requirement:** `VPNG-U001-R1.R3.R8`  
**Architecture:** C.001, C.008, D.002  
**Stable evidence:** `EV-00130`

## Findings

### F1 — D.002 cannot bypass C.001 readiness

**Decision:** accepted  
**Resolution:** clean

`WireGuardPeerProbeExecutor` receives a fresh `ProbeExecutionPrecondition` and constructs
the exact peer-owner execution key before any physical call. An unconfirmed or absent key
raises before C.008 I/O.

### F2 — current interface generation remains part of the physical identity

**Decision:** accepted  
**Resolution:** clean

The execution key includes the exact `InterfaceIdentity` from the current path. A stale
ifindex under the same `wg0` name does not satisfy readiness and cannot reach the Driver.

### F3 — peer identity remains distinct from availability subjects

**Decision:** accepted  
**Resolution:** clean

The executor requires `WireGuardPeerProbeOwner` and `ManagedWireGuardPeerConfig`; it never
constructs `ProbePolicyOwner`, `AvailabilityProbeIntent` or an extra `LogicalPathId`.

### F4 — physical mechanism remains C.008

**Decision:** accepted  
**Resolution:** clean

After readiness, the executor passes only `IcmpProbePhysicalContext(endpoint, target)` to the
shared physical Driver. It does not duplicate ping command rendering, timeout policy or
technical result classification.

### F5 — shared-plane runtime composition remains open

**Decision:** accepted  
**Resolution:** open by design

The executor solves only one current peer attempt. Alpha still needs one combined lower probe
convergence containing A.007 and D.002 owner demands, with separate readiness verification for
each semantic subset. Reusing the current global availability precondition for the union would
incorrectly let one peer-owner defect block unrelated Profile availability attempts.

## Verification

GitHub Actions run `45554729474`, `unit` job `139003923124` — PASS, including full
architecture traceability and executor rejection tests.

## Verdict

**PASS for the production peer-probe port.** D.002 remains partial until shared-plane
composition, trigger/status publication and A.007 generation invalidation are materialized.
