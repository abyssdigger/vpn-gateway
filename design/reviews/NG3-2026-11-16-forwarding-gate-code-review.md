# VPN-GATE NG3 — Managed-Netns ForwardingGate Code Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-structural-barrier-40m`  
**Reviewed commit:** `c92d0049776d516f10e2ce09a7c64b6c11a23c73`  
**Live evidence:** EXP-030

## Scope

The unit implements the root structural forwarding barrier selected by the preceding
architecture review.

Semantic boundary:

```text
observe managed-netns forwarding gate
optional set desired gate state
fresh observe
exact desired postcondition
```

Linux realization:

```text
ip netns exec <managed-ns> sysctl -n net.ipv4.ip_forward
ip netns exec <managed-ns> sysctl -w net.ipv4.ip_forward=<0|1>
```

## Requirement / safety gate

PASS.

The implementation is below NetworkPolicyAdapter and does not expose `ip_forward` as user
configuration.

It directly supports:

- `VPNG-U004-R4.R2` — command intent is not treated as active state;
- `VPNG-U004-R4.R3.R2` — structural work can establish a restrictive root barrier;
- `VPNG-U004-R4.R4` — startup can require confirmed forwarding disablement;
- `VPNG-U004-R4.R5` — post-failure state is re-observed before the caller proceeds;
- `VPNG-U004-R4.R6.R1` — the sysctl is changed only inside the managed network namespace.

## Executor semantics

PASS.

`converge_forwarding_gate_once()` has no hidden retry loop.

### Initial observation failure

No mutation is attempted.

This matters because an unknown initial gate state is not permission to issue an enabling
write.

### Normal mutation

A lower write is followed by a fresh observation. Process exit success is not confirmation.

### No-op

Even if the first observation already equals desired state, the executor obtains a second
fresh observation before returning success.

This prevents an initial snapshot from being promoted directly into a structural barrier
proof.

### Write exception with independently confirmed postcondition

Accepted.

If the lower write wrapper raises but a subsequent independent observation already proves the
exact desired state, the result is `SUCCESS` and retains the write failure as a diagnostic.

This is correct for the safety boundary: the kernel state is the postcondition; subprocess
success is not a product requirement.

### Unconfirmed final state

A wrong or unreadable final value never returns `confirmed=true`.

## Linux backend

PASS.

The backend:

- uses argv execution rather than shell interpolation;
- requires a non-empty explicit namespace;
- accepts only exact observed values `0` and `1`;
- does not parse/write host-namespace sysctl state;
- does not hide verification inside the write primitive.

The Executor owns the write/reread protocol, keeping observation semantics reviewable.

## Live evidence

GitHub Actions run:

```text
run:      43837565943
commit:   c92d0049776d516f10e2ce09a7c64b6c11a23c73
unit:     228 tests, OK
EXP-030 packet-path barrier: PASS
NG3 forwarding-gate Linux backend integration: PASS
linux-route-priority: PASS
linux-policy-platform / EXP-028: PASS
linux-structural-inventory-shape / EXP-029: PASS
overall:  success
```

EXP-030 independently proves that the effective `0` value actually blocks transit IPv4
packets in the disposable managed namespace.

The backend integration separately proves that the accepted implementation reaches and
confirms both states against a real namespace.

## Residual boundary

ForwardingGate establishes the root structural barrier only.

It does not yet implement:

- nft filtering/NAT desired state;
- nft authoritative observation;
- guarded route-table preparation;
- RPDB activation;
- release of the barrier after complete route+nft verification.

The next safe lower unit is nft ownership and authoritative observation. It must remain
read-only until the final nft desired-policy semantics are sufficiently resolved.

## Final verdict

**PASS.**
