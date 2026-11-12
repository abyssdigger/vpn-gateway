# Final whole-project review — NG1 first production implementation

Date: 2026-11-12

## Scope

Reviewed the current NG1 Draft 5 production baseline after:

- external safety review and corrections;
- nftables production migration;
- generation-safe ifindex verification;
- deployment/systemd corrections;
- RPDB JSON correction;
- incremental binding and route-additive transition work;
- full disposable production-cycle PASS;
- EXP-016 ECMP prerequisite PASS;
- EXP-019 raw WireGuard availability-evidence PASS.

Review scope covered:

- schema-v1 router and instance configuration;
- Device/Profile domain and validation;
- DeviceEngine and TrafficRuntimeState;
- routing/RPDB/blackhole/shadow-fallback projection;
- transition classification;
- nftables INPUT/FORWARD/OUTPUT/NAT policy;
- generation-safe nft observation;
- Planner/runtime/durable state;
- publication supervisor;
- namespace lifecycle and status;
- CLI/systemd/installer;
- active experiment/deferral boundaries.

## Evidence baseline

Current GitHub validation proves:

- rootless NG1 suite PASS;
- RC3 regression suite PASS;
- instance lifecycle PASS;
- lifecycle route diff PASS;
- EXP-017 numeric-ifindex same-name/new-ifindex isolation PASS;
- production nft policy round-trip PASS;
- EXP-016 ECMP hash-policy PASS with selected production value 1;
- full production cycle PASS:
  - initial reconcile;
  - same-name/new-ifindex incremental replacement;
  - verified-removal metric release and route-additive promotion;
  - ordinary member disappearance without global barrier;
  - structural foreign-nft drift with barrier and repair;
  - final durable-state equality.

## Review findings

### F1 — no unresolved source-level correctness finding in the current production scope

Disposition: CLEAN.

The current code and documented architecture agree on:

- nftables as the only production packet-policy backend;
- legacy iptables as regression/historical evidence only;
- INBOUND/BIDIRECTIONAL capacity exactly 1;
- restrictive default-DROP Device envelope for remote-initiated Profiles;
- bound-interface-only state acceptance;
- default-DROP INPUT/FORWARD/OUTPUT;
- explicit Device NAT;
- persistent shadow fallback;
- ordinary lifecycle/route-additive incremental repair;
- structural/unknown global barrier;
- namespace-owned fib_multipath_hash_policy=1.

No accepted review finding remains unfixed in those areas.

### G1 — real systemd/PID1 deployment evidence remains external

Status: BLOCKED ON TARGET EVIDENCE, not on source implementation.

EXP-018 is prepared and requires a disposable Debian 13 systemd-as-PID1 host. GitHub CI
cannot faithfully prove the final capability/sandbox/restart interaction of the installed
template service.

This does not block further source work but remains a release/deployment acceptance gate.

### G2 — real payload MTU/MSS evidence remains external

Status: BLOCKED ON REAL VPN TOPOLOGY.

EXP-015 is prepared. No MSS clamp is guessed in source code.

Final real-TCP production signoff requires the OpenConnect/WireGuard live experiment and a
documented decision among no clamp / clamp-to-PMTU / justified explicit MSS policy.

### D1 — multi-interface remote-initiated flow pinning

Status: POSTPONED BY PRODUCT DECISION.

Schema-v1 capacity==1 is production-complete. EXP-014 is not part of the first production
baseline and should be revisited only after that baseline is operating and there is a real
need for capacity>1 INBOUND/BIDIRECTIONAL.

### F2 — availability mechanism vs trigger

The routing mechanism for UNAVAILABLE is implemented and EXP-016 has closed the ECMP
prerequisite.

EXP-019 has additionally closed the raw WireGuard evidence question:

- interface presence is not liveness;
- latest-handshake age is not a prompt liveness trigger;
- active path probing can distinguish live/unavailable/live without replacing interface
  generation.

What remains is not a kernel ambiguity but a future DeviceManager product-policy decision:
probe target, cadence, threshold, admission model and Device-specific evidence mapping.

That decision changes user-facing configuration/semantics and therefore requires human
agreement before implementation.

## Rust-alignment assessment

The first production baseline remains suitable for migration:

- normalized immutable domain values;
- explicit transition enum;
- pure desired-state projection;
- command/backend isolation;
- versioned durable state;
- generation identity by ifindex;
- events as wakeups only;
- explicit experiment gates rather than implicit assumptions.

No Python-only architectural dependency was found that should be removed before the first
working baseline is exercised on a real Debian/VPN stand.

## Post-review correction and revalidation

The review found one documentation-only drift in `design/NG1/rou-concept.md`:

- publication/envelope grammar was still described as open;
- return-path wording still implied marks were unnecessary without stating the
  schema-v1 remote-initiation capacity restriction.

The concept document was aligned to the already normative Draft 5 implementation:

- schema-v1 publication and traffic-envelope grammar are fixed;
- OUTBOUND requires no flow pinning;
- INBOUND/BIDIRECTIONAL require active capacity exactly 1 plus restrictive envelope;
- capacity>1 remains gated by EXP-014.

No executable source or policy semantics changed. The corrected baseline was reviewed again
against the architecture and current passing production-cycle evidence. No further finding
was produced.

Human product decisions recorded after the review:

- legacy iptables remains regression/historical evidence only;
- EXP-014 / capacity>1 remote-initiation is POSTPONED until after the first production
  baseline is exercised and a practical need appears;
- future DeviceManager/availability experimentation may proceed after completion of the
  first baseline.

## Verdict

**FIRST PRODUCTION IMPLEMENTATION SOURCE BASELINE: CLEAN.**

No unblocked required source function or unresolved review finding remains for the current
scope.

Remaining work categories are:

1. external release evidence: EXP-018 and EXP-015;
2. explicitly postponed extension: EXP-014;
3. future DeviceManager/availability policy, now unblocked at the evidence level by
   EXP-016 and EXP-019 but requiring human agreement on product semantics.

Per CONTINUOUS-DEVELOPMENT.md, the current source scope therefore satisfies the completion
criterion. Future DeviceManager work is a new product review unit rather than unfinished
baseline implementation.
