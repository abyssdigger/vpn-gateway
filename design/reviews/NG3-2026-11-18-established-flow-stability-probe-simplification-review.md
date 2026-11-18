# NG3 2026-11-18 — established-flow stability and probe simplification review

## Verdict

**PASS for requirement/architecture correction.**

The project now distinguishes two very different concerns:

1. payload established-flow path stability, which is product-significant;
2. fresh lower conntrack identity for every ICMP probe generation, which is not by itself a
   Release-1 product postcondition.

## New requirement principle

Added:

- `VPNG0003-R3.R8`
- `VPNG0003-R3.R8.C1`

Accepted semantics:

```text
established managed flow
    + selected logical path remains current and usable
        -> changes to availability/preference/other paths do not migrate the flow

selected logical path disappears or becomes unusable
        -> no promise of buffering, replay, reliable delivery or seamless flow migration
        -> in-flight traffic may be lost
        -> subsequent traffic may use another currently allowed/effective path
```

The Purpose is intentionally scoped to the parent path-preference requirement. The broader
engineering heuristic "VPN-GATE should not make a flow materially less stable than direct use
of its selected VPN path" remains explanatory architecture rationale rather than requirement
ancestry.

## Why route switching matters

A mid-flow route change is dangerous only when the alternate path is not observationally
equivalent to the original path.

The current architecture already has a concrete counterexample: Device-owned outbound NAT.
One path may materialize `MASQUERADE`, another may materialize `NONE`; lower NAT rules are
bound to exact current egress endpoints. Paths may also differ in source-address, remote
stateful firewall/NAT and tunnel-side semantics.

Therefore destination reachability through both paths is insufficient evidence that moving an
established flow is harmless.

Release 1 does not attempt dynamic path-equivalence proofs. It preserves the selected live
logical path.

## Real current gap

The pure route-priority mechanism changes metrics inside one Profile table.

Without per-flow concrete-path affinity:

```text
flow begins through path A
A remains usable
availability/preference makes B preferred
later packet performs ordinary route lookup
    -> B may be selected
```

EXP-062's control phase already proved the generic Linux behavior: a preference change can
move later packets of an established TCP exchange and break the exchange while the original
path remains available.

The current inbound/bidirectional Release-1 case is already protected because:

- remote-initiated flows receive managed-stack routing-domain affinity;
- Release 1 permits at most one eligible logical path for inbound/bidirectional Profiles.

The unresolved case is outbound multi-path.

Availability-driven outbound priority changes therefore remain gated until per-flow concrete
logical-path affinity is materialized.

## EXP-025 / EXP-026 decision

EXP-025 remains a valid target-confirmed lower finding:

- a marked ICMP conntrack entry may survive interface replacement;
- a later probe reusing the same tuple/identifier may inherit that entry.

This proves stale lower probe identity is possible. It does not prove:

- an ICMP reply can be synthesized from nothing;
- payload can be migrated to another logical path;
- payload return-affinity can be selected by a probe mark;
- one stale observation can directly switch availability despite the accepted confirmation
  accumulator.

EXP-026 remains valid mechanism evidence:

- privileged CI showed mark-filtered probe-class cleanup;
- unrelated differently marked conntrack state remained intact;
- reused probe tuple returned to NEW + mark-set.

Current disposition:

```text
EXP-025 -> historical_only lower limitation evidence
EXP-026 -> not_selected for Release 1; optional future hardening
```

Debian 13 confirmation of EXP-026 is deliberately not pursued as a Release-1 gate.

## Probe non-interference boundary

Production ICMP may use the EXP-024-style selective shared-namespace mechanism without
generation-wide conntrack cleanup only if it proves:

```text
probe state cannot select/migrate payload routing

probe routing discriminator/table is disjoint from
payload dispatch and established-flow affinity resources

no generic probe ct-mark -> payload packet-mark restoration exists

accepted result still belongs to current
(Profile, logical path, target) observation context
```

A namespace-wide conntrack flush remains prohibited.

## Artifacts updated

Normative/current:

- `design/NG3/requirements.md`
- `design/NG3/architecture.md`
- `design/deferrals/NG3-probe-local-system-materialization.md`
- `design/NG3/transition-tips.md`
- `design/NG3/release2-evidence-backlog.md`
- `design/NG3/experiment-evidence-transition.md`
- `design/vpn-gateway-experiments.md`

Historical reviews/results were not rewritten.

## Requirement-state inventory

No new `decomp`, `unreal`, `broken` or `[rejected_closure]` link was created.

Existing accumulated review debt remains unchanged.

## Next bounded unit

Design and prove the smallest outbound established-flow affinity mechanism.

The expected Linux shape is:

```text
first ordinary->VPN packet:
    ordinary Profile routing selects actual egress path
    -> after route selection, record that concrete logical path in conntrack state

later packets of same flow entering from host boundary:
    restore only an owned path-affinity discriminator
    -> higher-precedence guarded path-specific lookup
    -> original logical path while it remains usable
```

The still-unproven fact is the first-packet capture boundary: whether the actual selected
egress can be safely captured after normal route selection and reused before subsequent route
lookups without leaking into reverse-direction/probe traffic.

## Conclusion

The availability problem has been simplified, but not by ignoring the important risk. The
unnecessary probe-generation cleanup gate is removed; the real flow-stability gap is now
explicit and becomes the next implementation/evidence unit.
