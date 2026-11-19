# VPN-GATE NG3 — Experimental evidence transition

Status: evidence handoff for NG3 requirement decomposition and architecture review
Source ledger: design/vpn-gateway-experiments.md
Scope: RC2 / RC3 / NG1 / NG2 experiments with facts that constrain NG3 assumptions

## 1. Purpose

This document is a cache of already established technical facts.

It is not a migration of old architecture.

Interpretation rule:

    historical experiment
        -> reusable technical evidence or disproved assumption

    reusable evidence
        -> may constrain NG3 decomposition / architecture / implementation

    reusable evidence
        != automatic NG3 product requirement
        != automatic reuse of old component model

If an experimental fact narrows product support or transfers work to the user/admin,
that limitation still has to be represented in the NG3 requirement tree as a Constraint
with explicit Reason/Statement and, when necessary, a compensating child Requirement.

## 2. Evidence classes

PROVEN
: The tested fact/mechanism is materially identical to a current claim and can be reused,
  subject to target-environment compatibility.

PROVEN FACT / SUPERSEDED DESIGN
: The experiment proved a Linux/process/network fact, but the architecture that motivated
  it was later removed. Reuse the fact, not the old design.

PREPARED / UNPROVEN
: The experiment was designed but not completed. This is not positive evidence and NG3
  must not assume the intended behavior.

BACKEND-SPECIFIC
: The evidence is valid only for the tested implementation boundary, for example
  iptables-nft. It must not be generalized to another backend without evidence.

## 3. Cross-generation constraints that should be checked before decomposition

1. Event is not authoritative state.
   Netlink/events wake reconciliation; decisions come from fresh observation.

2. Valid absence is not observation failure.
   A trustworthy snapshot saying "interface absent" is ordinary lifecycle state.
   Failure to obtain/parse authoritative inventory means state is unknown.

3. Interface/process presence is not path liveness.
   This is independently proven for WireGuard and OpenConnect.

4. Interface name is not concrete interface-generation identity.
   Historical concrete identity is (ifname, ifindex).

5. Numeric ifindex is not durable generation identity across missed lifecycle/restart.
   Exact reuse was demonstrated.

6. Fresh interface generation does not necessarily imply fresh conntrack-carried probe
   identity. EXP-025 proved stale marked conntrack inheritance across generation replacement.

7. VPN transport peer is not a generic Linux route-next-hop abstraction.
   In particular, WireGuard peer choice follows AllowedIPs, not arbitrary FIB next-hop.

8. Route metric/order is priority, not health detection.

9. Over-quota discovered interface is not an admitted path.

10. Apply success is not commit.
   State becomes committed only after fresh observation and verification.

11. Existing survivors must not churn because fresh observation order changed.

12. Per-table firewall atomicity does not imply cross-table/routing atomicity.

13. A PASS on an old mechanism does not require NG3 to reuse the old architecture.

14. PREPARED experiment does not establish the intended behavior.

Any NG3 decomposition contradicting these facts needs either an explicit scope/environment
difference or new evidence.

## 4. EXP-001 — fixed firewall/NAT canonical round-trip

Class: PROVEN, backend-specific.

Proved on Debian 13 / iptables-nft:

- repeated identical materialization produces stable canonical iptables-save output;
- save -> restore --noflush -> save is stable for the tested owned subset;
- generated restore payload is not necessarily identical to canonical observed output.

Constraint:

- do not compare generated restore text directly to observed save text;
- if the same backend is used, a universal firewall AST is not justified merely for
  canonicalization.

## 5. EXP-002 / EXP-002A — iproute2 route/address inventory

Class: PROVEN iproute2-boundary evidence.

EXP-002 found an actual wrong assumption: ip -j -4 addr show can omit an existing interface
that has no IPv4 address.

EXP-002A proved the corrected boundary:

- full address inventory can retain an existing interface with an empty IPv4 set;
- point-to-point local address comes from addr_info.local;
- remote/peer address is not the local readiness address;
- iproute2 JSON rendering must be treated as a concrete external contract.

Constraint:

    interface exists with no IPv4
        != interface absent

Parser assumptions affecting safety require target-version validation.

## 6. EXP-003 — first live end-to-end gateway

Class: PROVEN but narrow topology/path evidence.

Proved a complete real OpenConnect forwarding path with routing, filter and NAT.

Did not prove:

- graceful shutdown cleanup;
- crash recovery;
- runtime drift repair;
- periodic reconciliation;
- Netlink self-healing.

Do not cite EXP-003 for those lifecycle properties.

## 7. EXP-004 family — gateway boundary findings

### EXP-004.1 — complete forwarding ownership

Class: PROVEN safety fact.

When global ip_forward was enabled, unmanaged forwarded traffic could fall through into an
ambient FORWARD ACCEPT policy.

General lesson for NG3:

A component enabling forwarding for its managed domain must establish a terminal safety
decision for traffic in that domain. Safety cannot depend on ambient host policy being
restrictive.

### EXP-004.2 — interface-dependent route disappearance

Class: PROVEN Linux FIB fact; old mechanism optional.

When the VPN interface disappeared:

- the dependent unicast route disappeared;
- an independent blackhole remained;
- lookup did not fall through to ordinary default routing.

This proves one viable fail-closed FIB mechanism. It does not require NG3 to restore old
proto-201/proto-202 architecture.

### EXP-004.3 — ocserv runtime interface family

Class: PROVEN transport behavior.

ocserv can allocate a family of runtime interfaces. Configured device naming is not a
durable exact ifname guarantee.

This supports selector -> concrete binding semantics.

### EXP-004.4 — cleanup transaction

Class: PROVEN, backend-specific.

For tested iptables-nft:

- the exact per-table cleanup transaction worked;
- failure before COMMIT left the table unchanged.

It does not prove cross-table atomicity.

### EXP-004.5 — marker-selective route inventory

Class: PROVEN historical owned-route mechanism.

Protocol-filtered route queries can isolate owned marker routes from unrelated foreign
multipath state.

Boundary:

- selective cleanup may avoid parsing unrelated routes;
- it does not justify silently ignoring unsupported state carrying the owned marker;
- normal reconciliation may remain stricter than cleanup inventory.

## 8. EXP-005 — iptables interface-prefix guard

Class: PROVEN historical iptables-specific mechanism.

Proved:

- trailing plus is textual interface-prefix matching;
- it includes the bare prefix and suffixed names;
- an exact ACCEPT before a broad prefix REJECT works;
- broad prefix matching was appropriate for deny-only pre-binding guard, not binding-specific
  ACCEPT/NAT/routes.

Do not confuse this kernel operand with current human config syntax such as vpns*/N.

## 9. EXP-006 — firewall orchestration

Class: PROVEN, backend-specific.

Proved:

- replacement of existing owned chain contents;
- full -> isolation -> full;
- intended isolation blocks existing ESTABLISHED/RELATED transit;
- narrow INPUT-only repair can preserve active transit;
- FORWARD/NAT-class drift requires a safety barrier;
- failed table transaction did not leave partial table state.

Constraint:

Different drift classes may justify different repair scope only when locality and
postconditions are provable.

## 10. EXP-007 — live daemon lifecycle smoke

Class: PROVEN historical lifecycle evidence.

Proved:

- config boundary;
- startup materialization;
- steady reconciliation;
- graceful cleanup.

Also exposed a useful failure mode:

    configured exact selector vpns0
    actual runtime interface vpns00
        -> not READY
        -> fail closed

Do not "helpfully" broaden selectors at runtime.

## 11. EXP-008 — live runtime drift recovery

Class: PROVEN historical recovery evidence.

Proved live:

- owned route recovery;
- narrow INPUT repair;
- broader FORWARD safety-barrier repair;
- graceful cleanup.

Useful constraint: local repair may be materially smaller than global rebuild only when the
affected domain is provably isolated.

## 12. EXP-009 — interface-centric failover semantics

Class: PROVEN and highly reusable.

OpenConnect findings:

- simultaneous sessions create independent concrete interfaces;
- interface disappearance removes dependent route;
- returning interface does not recreate daemon-owned route automatically;
- direct-device route works;
- an existing preferred route can remain while forwarding behind it is dead.

WireGuard findings:

- Linux route next-hop does not select WireGuard peer;
- peer ownership follows AllowedIPs;
- one target prefix belongs to one peer at a time on one interface;
- handshake/endpoint state does not automatically change prefix ownership.

NG3 constraints:

- concrete interface path is the routing abstraction;
- peer semantics remain transport-specific;
- reconciliation is required after interface return;
- metrics are priority, not liveness.

## 13. EXP-010 — generic transport publication

Class: PROVEN primitive.

Proved host-side UDP publication/relay into a separate network namespace and back.

It proves the publication topology primitive, not WireGuard semantics or final user config.

## 14. EXP-011 — real ocserv/OpenConnect transport publication

Class: PROVEN real-protocol evidence.

Proved:

    external TCP/UDP endpoint
        -> host publication relay
        -> ocserv inside private namespace
        -> vpnsXX only inside that namespace

Both CSTP and DTLS were demonstrated.

Boundary:

- same-port publication is proven;
- generic arbitrary external/internal port translation for endpoint-advertising protocols
  is not proven;
- the experimental relay's single-peer limitation is not production semantics.

## 15. EXP-012 — complete ROU v0 lifecycle/integrity

Class: PROVEN executable-reference evidence.

Live run proved:

- namespace/veth create + teardown;
- real transport publication;
- two real OpenConnect bindings;
- real payload;
- preferred-binding disappearance with survivor behavior;
- fresh reconnect;
- zero-binding fail-closed;
- route/firewall drift repair under protective barrier;
- fatal containment/teardown after structural appliance loss.

Important interpretation:

ROU v0 was intentionally hard-coded. The lifecycle/kernel facts are reusable; its object
model is not.

## 16. EXP-013 — unavailable-path common-metric fallback

Class: PROVEN FACT / SUPERSEDED DESIGN.

Proved FIB mechanics for:

- direct-device routes;
- same-metric multipath behavior;
- ordinary prefixes and default;
- interface disappearance/return;
- real OpenConnect payload;
- a present interface whose path is actually dead.

Superseded:

- persistent shadow UNAVAILABLE payload tier;
- UNAVAILABLE_METRIC as current architecture.

Reuse only the tested FIB facts if NG3 later needs the materially same mechanism.

## 17. EXP-014 — remote-initiated multi-path flow pinning

Class: PREPARED / UNPROVEN; deferred Release 2 evidence.

The intended experiment would prove connmark/fwmark return steering and fail-closed mark
retirement for multiple inbound paths.

It was not completed.

Release 1 no longer depends on this experiment because it explicitly rejects
`inbound`/`bidirectional` Profiles whose configured maximum eligible logical-path capacity
exceeds 1.

EXP-014 is retained as the historical predecessor for Release-2
multi-path inbound/bidirectional return-path evidence. It has now been superseded as the active
experiment vehicle by EXP-062, whose scope is narrower because EXP-053/EXP-061 already proved
the host-boundary and Profile-routing-domain continuity layers separately.

Constraint:

Do not claim safe INBOUND/BIDIRECTIONAL capacity greater than one until requirements are
revised and EXP-062 or materially equivalent target evidence is accepted.

## 18. EXP-015 — MTU/MSS real TCP

Class: PREPARED / UNPROVEN.

No evidence currently justifies any of these as production policy:

- always clamp TCP MSS;
- never clamp;
- use a fixed/device-specific MSS.

Do not invent MTU/MSS config or implementation policy without evidence.

## 19. EXP-016 — ECMP hash policy

Class: PROVEN FACT / currently non-required.

Proved namespace-local fib_multipath_hash_policy=1 behavior:

- a repeated 5-tuple remains deterministic;
- L4 variation can spread flows;
- the sysctl is namespace-local.

The architecture needing persistent ECMP fallback was later removed.

Do not make this an NG3 prerequisite unless NG3 deliberately reintroduces ECMP.

## 20. EXP-017 — ifindex-aware nft admission

Class: PROVEN nftables mechanism fact.

Proved numeric nft meta iif/oif can bind policy to a same-name/new-ifindex interface
generation.

Also exposed a verifier trap:

- live numeric interface references may render symbolically as ifname;
- stale references may remain numeric.

Therefore verification must not reconstruct exact generation identity only from rendered
right-hand operands.

Compiler-owned exact generation markers/comments were demonstrated as one observable
strategy.

## 21. EXP-018 — systemd deployment lifecycle

Class: PREPARED / UNPROVEN.

A real Debian 13 systemd/PID1 crash/restart/hardening lifecycle was designed but not run.

GitHub syntax/kernel tests are not proof of:

- actual capability bounding under target systemd;
- Restart=on-failure recovery;
- boot recreation;
- hardened-unit behavior.

Do not mark those deployment claims proven without target-systemd evidence.

## 22. EXP-019 — WireGuard availability evidence

Class: PROVEN raw-evidence fact.

Proved:

- wg0 can remain present with the same ifindex while remote path is unusable;
- a tunnel-bound active probe detects live -> dead -> live;
- recovery can occur without a new successful handshake timestamp;
- latest-handshake age is not a sufficient prompt short-outage liveness signal.

Does not choose target, cadence, timeout or hysteresis.

## 23. EXP-020 — OpenConnect availability evidence

Class: PROVEN raw-evidence fact.

Proved:

- OpenConnect process may remain alive;
- tunnel interface may remain present with the same ifindex;
- payload path can still be unusable;
- the same interface generation can recover;
- a path-bound probe distinguishes this condition.

Together EXP-019/020 prove that availability is independent from binding presence for both
first-class transports.

## 24. EXP-021 — ICMP probe generation boundary

Class: PROVEN mechanism fact with a critical limitation.

Proved:

- ICMP ping socket works in the tested setup without CAP_NET_RAW using namespace-local
  ping_group_range;
- narrow nft admission can constrain one target/protocol/current interface generation;
- an interface-bound probe does not escape through an alternate Device path;
- same-name/new-ifindex fails closed against stale numeric rules.

Also proved:

    fresh interface reusing the same numeric ifindex
        can match stale numeric admission

Therefore numeric ifindex is a current kernel selector, not a durable generation identity
across missed lifecycle or daemon restart.

## 25. EXP-022 — isolated Profile-binding probe plane

Class: PROVEN mechanism fact.

Proved an isolated probe control plane using the tested combination of:

- uidrange;
- ipproto;
- exact target;
- bound oif;
- dedicated routing table;
- narrow nft admission;
- terminal failure route.

A probe can test a concrete binding even while that binding has no Profile payload route.

Also reconfirmed the stale-selector risk after exact ifindex reuse.

Does not define config grammar, cadence, hysteresis or condition composition.

## 26. EXP-023 — real OpenConnect Profile-binding probe plane

Class: PROVEN real-VPN validation.

With two live OpenConnect bindings reaching the same endpoint, proved:

- one path-specific condition can fail while session/interface remains alive;
- the alternate path remains healthy;
- the primary probe does not escape through the alternate path;
- the condition recovers on the same binding.

Strong evidence for Profile/path-specific availability.

## 27. EXP-027 — route-priority bubble

Class: PROVEN and directly reusable for current NG3 priority-only transition.

Proved for both ordinary prefix and default:

    add moving path at unused metric
    delete old route copy

At every checked step:

- complete eligible path set remained present;
- exactly one path temporarily had two route copies;
- deleted metric became the next free slot;
- terminal blackhole remained;
- all-live steady state required no persistent configured gap.

Current NG3 implication:

- no eligible path is intentionally removed as scratch space;
- no staging table is needed for pure priority permutation;
- one priority transaction per Profile/routing domain completes and verifies before another
  desired order is materialized.

## 28. EXP-024 — selective shared-namespace probe-process isolation

Class: PROVEN, target-confirmed.

The experiment exists on the active NG2 development line even though it was missing from the
central experiment ledger and default-branch search.

It proved on privileged CI and Debian 13 target that probe-process identity can be captured
where it is observable and carried into the reverse flow without imposing global
INPUT/OUTPUT default-DROP on unrelated local processes.

The rejected attempt is itself evidence:

```text
INPUT meta skuid
    != usable receiving-socket discriminator
```

The accepted mechanism was:

```text
OUTPUT:
    probe uid + exact oif + target + protocol
        -> set dedicated conntrack mark
        -> accept

INPUT:
    exact iif + remote source + reply protocol + conntrack mark
        -> accept
```

Other proved properties:

- unrelated local traffic remains ordinary;
- unbound probe traffic cannot escape through an alternate path;
- probe target admission remains narrow;
- capability-free ping-socket model works with the tested setup.

Constraint:

Linux uid is a lower-domain process selector, not an availability semantic field.

The conntrack-carried identity created a separate generation question, answered negatively by
EXP-025.

## 29. EXP-025 — stale probe conntrack generation

Class: PROVEN NEGATIVE FINDING, target-confirmed.

Status:

```text
TARGET-CONFIRMED FINDING — STALE-INHERITANCE
```

The result is not a PASS of the isolation mechanism. It proves a failure mode.

On both privileged CI and Debian 13 target:

- generation A created a marked ICMP conntrack entry;
- vpn0 was deleted and recreated with a new ifindex;
- the marked conntrack entry survived;
- generation B deliberately reused the same tuple / ICMP identifier;
- the new probe took the ESTABLISHED path carrying the stale mark rather than NEW+mark-set;
- deleting that exact conntrack entry restored NEW+mark-set.

Therefore:

```text
fresh interface generation
+ regenerated exact RPDB/nft selectors
    !=
fresh conntrack-carried probe identity
```

This is a strong NG3 constraint.

Interface-generation replacement alone is insufficient to invalidate probe flow identity.

Any probe design carrying local process identity through conntrack must define a narrow
generation-boundary invalidation/remediation strategy.

Global conntrack flush was explicitly rejected as an unreviewed remediation.

## 30. EXP-026 — probe-class conntrack cleanup boundary

Class: PROVEN ON PRIVILEGED CI / TARGET CONFIRMATION OPEN.

Current experiment README status:

```text
PRELIMINARY PASS on privileged GitHub Linux CI;
Debian 13 target confirmation required
```

The tested remediation:

```text
conntrack -D -p icmp -m <dedicated-probe-mark>
```

proved in privileged CI that:

- two probe-class entries carrying the dedicated mark are removed;
- unrelated differently marked conntrack state remains;
- after cleanup and interface-generation replacement, fixed-id probe takes NEW+mark-set;
- unrelated control traffic remains usable.

Interpretation:

This proves a **narrow mechanism candidate** for breaking EXP-025 stale inheritance without a
namespace-wide conntrack flush.

It does **not** yet establish production/target evidence on Debian 13.

It also does not by itself decide product/architecture policy:

- whether all in-flight probe-class flows may be invalidated together;
- whether mark-wide cleanup is the minimal accepted generation boundary;
- when exactly cleanup runs relative to binding-generation replacement.

Until target confirmation or an explicit evidence-policy decision is accepted, NG3 must not
describe EXP-026 as target-confirmed PASS.

**Current NG3 decision, 2026-11-18:** the evidence-policy decision has now been made. EXP-026
remains non-target-confirmed, but Release 1 deliberately does not require its cleanup mechanism.
Fresh lower conntrack identity for every probe generation is not itself a product postcondition.
The selected implementation must instead prove current subject/path isolation and strict
non-interference with payload routing/established-flow affinity. EXP-026 is re-entered only if
material observable harm from stale probe conntrack state is demonstrated.

## 31. Experiment-ledger/search gap

EXP-024, EXP-025 and EXP-026 were not missing from the development history.

They exist in the NG2 development chain and later descendant branches, but were absent from:

- repository default branch `main`;
- central `design/vpn-gateway-experiments.md` ledger.

That combination caused normal default-branch code search to report them as absent.

This is a tooling/indexing gap, not lost evidence.

The central ledger should carry explicit entries for all three experiments so future evidence
review does not depend on branch-aware search.

## 32. Device/config evidence boundary relevant to current recovery

Historical material confirms that Device was a transport-capability concept with:

- stable user-visible ID;
- enabled;
- ordered expected_interfaces;
- NAT intent;
- traffic-envelope concept;
- publication concept.

However the evidence level differs.

Stable/implemented config surface:

- Device/Profile named TOML tables;
- ID grammar;
- explicit enabled;
- exact/prefix expected-interface expectations and quota semantics;
- Profile destinations/device order/direction;
- strict validation/refusal of ambiguity.

Conceptually accepted but human-facing grammar explicitly unresolved in NG1:

- Device publications;
- Device traffic_envelope.

The old parser was required to reject guessed publication/envelope syntax rather than
invent it.

Therefore NG3 may recover their product meaning, but must not treat one historical TOML
example as automatically normative schema.

NAT is a stronger candidate for recovered Device policy, but exact current grammar still
needs to be reviewed together with the final config surface rather than inferred from
internal types.

## 33. Current evidence map to NG3 areas

| NG3 area | Primary evidence |
| --- | --- |
| Managed isolated domain / bootstrap | EXP-010, EXP-011, EXP-012 |
| Runtime interface discovery/binding | EXP-004.3, EXP-007, EXP-009, EXP-012 |
| Unknown vs absent safety | EXP-004 family, EXP-006, EXP-008, EXP-012 |
| Fresh observation / reconciliation / commit | EXP-007, EXP-008, EXP-012 |
| Profile zero-path safety | EXP-004.2, EXP-012 |
| Concrete interface routing abstraction | EXP-009 |
| Availability independent from binding | EXP-019, EXP-020 |
| ICMP/path-specific probe mechanism | EXP-021, EXP-022, EXP-023, EXP-024 |
| Current interface-generation firewall enforcement | EXP-017, EXP-021, EXP-022 |
| Selective shared-namespace probe process isolation | EXP-024 |
| Current probe RPDB uidrange/ipproto/target representation | EXP-065 |
| Probe conntrack stale-generation risk | EXP-025 — target-confirmed negative finding |
| Probe-class conntrack cleanup candidate | EXP-026 — CI PASS, target confirmation open; Release-1 adoption not selected |
| Pure route-priority transition | EXP-027 |
| ECMP only if reintroduced | EXP-013, EXP-016 |
| Multi-path inbound return pinning | EXP-014 — UNPROVEN |
| MTU/MSS production policy | EXP-015 — UNPROVEN |
| Target systemd crash/restart lifecycle | EXP-018 — UNPROVEN |

## 34. How to use this document during decomposition

For every proposed child Requirement/Constraint or architecture mechanism:

1. state the technical assumption;
2. check this transition document before inventing a new assumption;
3. if a materially identical PASS exists, reuse it as evidence and cite the original
   experiment in review;
4. if the old design was superseded, import only the fact;
5. if the relevant experiment is PREPARED/unproven, keep the assumption open or create an
   evidence gate;
6. if evidence narrows product support, lift the limitation into a Constraint rather than
   hiding it in architecture;
7. if reconciling the evidence makes Purpose/Reason non-obvious, stop autonomous
   decomposition and escalate that requirement ancestry for human discussion.

## 35. Re-run criteria

Historical evidence should be re-run or replaced when:

- NG3 selects a different kernel/backend primitive;
- target OS/kernel/tool behavior materially changes;
- the NG3 claim is stronger than the old experiment;
- the old result proved only a PoC while current requirements demand production behavior;
- topology is no longer materially equivalent;
- an unproven gate becomes implementation-blocking.

Do not re-run an experiment merely because component names changed.

## 36. Canonical source hierarchy

When this summary is not precise enough:

1. start from design/vpn-gateway-experiments.md;
2. open the experiment README/result;
3. inspect the review/architecture revision that consumed the result to see whether the
   design was retained or superseded;
4. use implementation/tests only to clarify the exact tested contract.

This document is an evidence cache, not a replacement for the original artifacts.
