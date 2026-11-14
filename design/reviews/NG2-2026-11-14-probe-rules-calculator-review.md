# NG2 — ProbeRulesCalculator semantic slice review

**Дата:** 2026-11-14  
**Тип:** autonomous focused semantic review  
**Scope:** explicit ICMP availability intent -> common NetworkRulesSpec

## Boundary

This slice implements only pure ProbeRules calculation.

It does not:

- execute probes;
- manage timing/hysteresis;
- materialize LOCAL_PROCESS in Linux;
- publish availability state;
- create ProbeRulesState.

Those require separate executable/observable units.

## Input contract

`AvailabilityProbeSetRequest` is a full explicit runtime probe snapshot.

Current first mechanism:

```text
probe_id
concrete InterfaceIdentity
IPv4 target
ICMP mechanism
```

This is not user configuration grammar. It is the internal normalized request consumed by
AvailabilityProbeManager machinery.

Runtime construction validates explicit enum/address/interface types rather than relying on
Python annotations.

## Derived network semantics

Each unique physical ICMP probe plane derives:

- one owner-local routing domain;
- exact target /32;
- one concrete ordered path;
- LOCAL_PROCESS dispatch;
- explicit ICMP dispatch protocol;
- explicit bound output interface;
- outbound traffic allow restricted to ICMP echo-request to the target;
- reverse traffic allow restricted to ICMP echo-reply from the target;
- flow initiation only LOCAL_PROCESS -> interface;
- no source NAT.

Thus the calculator does not widen the EXP-021/024 admission to arbitrary ICMP.

## Review finding R1 — NetworkRules lacked ICMP message-type semantics

**Disposition:** fixed.

A selector with only `protocol=ICMP` would admit every ICMP type, broader than the
experimentally validated probe plane.

Added generic `IcmpType` selector values and nft predicate compilation for exact ICMP
message types.

The primitive is generic NetworkRules semantics, not probe-specific Linux machinery.

## Review finding R2 — logical probe IDs are not physical network-plane identity

**Disposition:** fixed.

Two availability conditions may have different correlation `probe_id` values while using
the same target, interface generation and mechanism.

Generating one routing domain/dispatch per logical id would create duplicate physical
dispatch selectors and make composition fail.

ProbeRulesCalculator therefore deduplicates by:

```text
(mechanism, InterfaceIdentity, target)
```

and derives a stable selector-based routing-domain name.

Logical probe correlation remains AvailabilityProbeManager responsibility.

Permutation regression proves request ordering does not change the resulting NetworkRules.

## Review finding R3 — same target on different interface generations must remain distinct

**Disposition:** covered.

The semantic dispatch selector includes bound output interface and protocol. Therefore
primary/secondary probes to the same target remain separate physical planes.

## Lower backend status

The concrete Linux backend now materializes the target-proven ICMP LOCAL_PROCESS probe
plane through the same common NetworkRulesAdapter. It uses explicit Linux-only process
identity configuration, exact RPDB observation and selective nft OUTPUT/INPUT with
conntrack-carried reverse-flow identity.

Broader LOCAL_PROCESS protocols/predicates remain fail-closed.

## Rules-state comparison

The prior evidence gate is now satisfied: production ProbeRules-derived NetworkRules have
passed physical apply and exact renew.

`ProbeRulesStateCalculator` is therefore the next required unit. Only after that concrete
state model exists should PayloadRulesState and ProbeRulesState be compared for a possible
common type.

## Evidence gate

Post-review branch evidence:

- NG2 unit suite: PASS;
- NG1 regression suite: PASS;
- privileged Linux integration: PASS;
- production nft compiler output with exact and negated ICMP message-type selectors:
  kernel `nft -c` PASS.

## Final verdict

**PASS for the pure ProbeRulesCalculator semantic slice.**

No user-policy decision is required by this unit.
