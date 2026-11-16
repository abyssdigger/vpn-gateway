# Production implementation review 17 — supervised publications

Role: external expert review focused on TCP/UDP relay lifecycle, server-start ordering,
socket ownership, teardown integrity and Rust migration.

## Scope

Reviewed `publication.py`, publication tests, runtime health integration and the
EXP-010/011/v0 publication evidence.

## Findings

### F1 — absent UDP target must not kill the publication worker

A server Device publication is expected to exist before the VPN process/listener may
start. A connected UDP association can receive an error while that internal listener is
absent.

Severity: high, lifecycle correctness.

Disposition: fixed. Send/receive errors drop only the peer association; the publication
worker remains healthy.

### F2 — TCP upstream source selection should match UDP publication topology

The first TCP implementation connected without an explicit source bind while UDP binds
the host-side veth address. Explicit source selection is preferable and matches the
verified v0 topology.

Severity: medium, routing determinism.

Disposition: fixed by binding TCP upstream to the configured source address.

### F3 — normalized publication ownership must not depend only on TOML parser

Programmatically constructed ActiveConfig could bypass publication collision checks.

Severity: medium, domain boundary.

Disposition: fixed in concrete endpoint projection: external endpoint uniqueness is
always checked, and internal endpoint ownership may overlap only within the same Device.

### F4 — successful supervisor teardown must verify worker/session termination

The first close path used bounded joins but discarded worker objects even if a worker
remained alive; TCP per-session daemon threads were not tracked to a verified stop.

Severity: medium, lifecycle integrity.

Recommendation: track active TCP session threads, close their sockets, wait for exit, and
raise PublicationError if worker/session termination cannot be verified. Do not claim
successful teardown while relay execution remains live.

Disposition: fixed.

## Whole-scope review

- all external sockets are pre-bound before any worker is started, preventing partial
  publication on bind collision;
- TCP target absence is session-local and does not kill listener worker;
- UDP maintains per-external-peer connected internal association;
- UDP association expiry is bounded;
- supervisor can be restarted after verified close;
- worker death is exposed through check_health;
- runtime checks supervisor health before reconciliation and any health failure exits
  through fail-closed containment;
- publications are active-Device scoped, not bound-interface scoped, preserving the
  server-before-client lifecycle.

## Rust-alignment review

Concrete endpoints are immutable values; supervision is separate from projection.
Protocol-specific workers are small and replaceable. A Rust port can use task ownership
and JoinHandle verification while preserving the same supervisor contract.

## Verdict

Approved after F1–F4 corrections. No remaining recommendation in publication scope.
