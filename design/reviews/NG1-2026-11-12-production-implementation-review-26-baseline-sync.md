# Production implementation review 26 — baseline documentation synchronization

Date: 2026-11-12

Role: internal expert review under CONTINUOUS-DEVELOPMENT.md.

## Scope

Reviewed the production README and newest CHANGELOG entry against the current code,
architecture, EXP-017 result and privileged CI baseline.

## Findings

### F1 — README described an obsolete production backend/gate state

Severity: medium documentation/operational correctness.

The README still described iptables filter/NAT kernel integration as the current backend
evidence and listed EXP-017 as a future gate even though:

- production Planner/runtime/lifecycle use nftables;
- EXP-017 is PASS;
- the full disposable production cycle is PASS on nft.

Disposition: fixed.

The README now:

- identifies nftables as the sole production packet-policy backend;
- retains legacy iptables explicitly as regression/historical evidence;
- records generation-safe nft verification;
- records lifecycle + ROUTE_ADDITIVE incremental repair;
- records the full production-cycle integration stages and PASS result;
- removes EXP-017 from the deferred/gated list.

### F2 — current production-cycle acceptance was not visible at the top of CHANGELOG

Severity: low/medium project-state discoverability.

Disposition: fixed with a newest-first entry describing:

- nft production backend;
- EXP-017 PASS;
- route-additive reassessment correction;
- full privileged production-cycle PASS;
- current future gates/postponements.

## Consistency review

The updated docs correctly separate:

- current production baseline;
- postponed EXP-014 future extension;
- EXP-015 final real-TCP evidence gate;
- EXP-016 prerequisite before a real UNAVAILABLE trigger;
- future DeviceManager work after the core baseline is otherwise complete.

No new product semantics are introduced by this documentation update.

## Verdict

Approved. No remaining recommendation in this review unit.
