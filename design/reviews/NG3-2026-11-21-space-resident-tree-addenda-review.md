# NG3-2026-11-21 Space resident-tree / addenda review

## Scope

Reviewed commit: `3c6a7c8f12a6b6024e215526b8d2e592b75e1102`.

Review target:

- `design/NG3/structured-architecture.md`;
- representation of component hierarchy inside a Space;
- separation between hierarchy and component specifications.

This review changes no product behavior and does not re-open the previously accepted
Private-network decomposition.

## Intended rule

The structured architecture uses two different representations for two different facts:

1. `Residents` is the single source of component containment/parenthood inside a Space.
2. `Component addenda` is a flat set of component specs local to that Space.

A component spec describes responsibility/API/decisions; heading level and spec order carry no
containment semantics.

## Checks

### Hierarchy has one source

The Private-network tree now represents:

```text
@NetworkPolicyAdapter
    NetworkPolicyLayoutCalculator
    NetworkPolicyEnforcer

@VPNPathAdapter

@ForwardingGate
    ForwardingGateDriver
```

The same parenthood is no longer duplicated through nested component headings or
`Subcomponents` sections.

**Decision:** accepted.  
**Resolution:** fixed in reviewed baseline.

### Component specs are flat

All Private-network component specs are siblings below one `Component addenda` heading:

- `NetworkPolicyAdapter`;
- `NetworkPolicyLayoutCalculator`;
- `NetworkPolicyEnforcer`;
- `VPNPathAdapter`;
- `ForwardingGate`;
- `ForwardingGateDriver`.

The `@` marker remains attached to the Space occurrence/method export, not to the canonical
component heading.

**Decision:** accepted.  
**Resolution:** fixed in reviewed baseline.

### API visibility remains independent from containment

A deep child can still have a Space-level method marked `@`; this remains a review signal.
Flattening specs therefore does not hide the distinction between containment and external API
visibility.

**Decision:** accepted.  
**Resolution:** no change required.

### F1 — cross-Space `<partial>` addendum ownership is not explicit enough

The methodology says that a `<partial>` marker is explained in the component description,
but it does not yet state where the description lives when the same technical component is
represented in multiple Spaces.

A single global component spec would reintroduce hidden cross-Space structure and make the
meaning of a Space-local partial occurrence ambiguous.

**Decision:** accepted.  
**Resolution:** fix the methodology so each Space contains its own addendum spec for the
portion represented in that Space; the canonical technical identity may be shared, but the
spec explains only that Space's occurrence and why it is partial.

### Historical decomposition review

`NG3-2026-11-21-private-network-decomposition-review.md` uses the word
`subcomponent` while discussing semantic containment. That remains valid historical review
language: the new rule changes how containment is represented in the structured document, not
the accepted containment decision itself.

**Decision:** accepted.  
**Resolution:** no retrospective rewrite.

## Verdict

**PASS after F1.**

The representation is simpler and less ambiguous than nested component specs: tree shape
answers “where does it live?”, while the flat addendum answers “what is it?”.
