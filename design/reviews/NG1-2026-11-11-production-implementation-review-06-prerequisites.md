# Production implementation review 06 — namespace payload prerequisites

Role: external expert review focused on Linux sysctl semantics, asymmetric routing,
IPv4-only containment, interface lifecycle and Rust-oriented implementation boundaries.

## Scope

Reviewed:

- `namespace_prereq.py`
- extended EnvironmentSnapshot sysctl collection
- prerequisite tests
- Draft 4 invariants 6 and 59.

## Kernel-detail verification

Linux documentation states that source validation uses the maximum of
`conf/all/rp_filter` and `conf/<interface>/rp_filter`. Therefore per-interface zero is
not sufficient if `all` remains strict. The implementation correctly owns both global
and per-interface values.

procps/systemd sysctl syntax supports slash-form keys, which preserve dots in interface
names such as `eth0.100`. The implementation uses that form for writes and direct procfs
paths for reads.

## Findings

No corrective finding remains for the target production contract.

## Safety observations

- `all` and `default` rp_filter are forced to zero;
- IPv6 forwarding remains disabled globally/default;
- future interfaces inherit `default.disable_ipv6=1`;
- host0 and every currently bound payload interface are individually verified with
  `rp_filter=0` and `disable_ipv6=1`;
- over-quota/unbound interfaces are not admitted payload interfaces and therefore do not
  need per-interface admission verification;
- verification is phase-aware and checks whether IPv4 forwarding is expected open or
  closed.

A kernel lacking the IPv6 sysctl surface is not specially treated as success. Under the
current Draft 4 contract, inability to observe/verify required prerequisite state is
fail-closed. This is acceptable for the Debian production baseline.

## Rust-alignment review

Prerequisites are represented as deterministic command/value projections and a typed
verification result. No shell or implicit global mutable state is used.

## Verdict

Approved. No recommendation remains in this scope.
