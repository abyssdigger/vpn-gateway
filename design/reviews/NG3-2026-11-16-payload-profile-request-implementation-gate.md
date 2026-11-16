# VPN-GATE NG3 — PayloadProfileRequest projection implementation gate

**Cycle:** `ng3-design-cycle-20261116-post-closure-implementation-readiness-40m`  
**Review unit:** pure Profile-local logical path membership projection

## 1. Scope

Implement the pure projection:

```text
enabled ProfileStructuralIntent set
+
current accepted DeviceBindingProjection
    ->
PayloadProfileRequest set
```

Each request contains exactly:

```text
profile_id
direction
destinations[]
ordered_paths[]
```

No Device NAT/envelope/publication policy and no Linux network rules are part of this unit.

## 2. Requirements

Primary:

- `VPNG-R1.R2.R4.R4`;
- `VPNG-R1.R2.R4.R4.R2`;
- `VPNG-R1.R2.R4.R4.R3`;
- `VPNG-R2.R1.R1`;
- `VPNG-R2.R2`;
- `VPNG-R2.R2.R1`;
- `VPNG-R2.R2.R2`;
- `VPNG-R2.R3`;
- `VPNG-R2.R3.R3`;
- `VPNG-R3.R1`;
- `VPNG-R3.R1.R1`;
- `VPNG-R4.R1`;
- `VPNG-R4.R1.R1`.

All are currently closed with architecture trace.

## 3. Ordering rule

For each enabled Profile, `ordered_paths` follows:

```text
Profile.device_order
    -> selector index within Device.expected_interfaces
        -> stable slot index
```

The global ordering of Device binding output is not policy.

Concrete endpoint identity is not part of the Profile request.

## 4. Membership rule

A logical path is included only when:

- its Device ID is present in this Profile's `device_order`;
- it is currently bound in the accepted binding projection.

No observed unbound/waiting candidate is included.

Availability does not participate in this structural projection.

## 5. Zero-path rule

An enabled Profile is emitted even when no current binding is eligible:

```text
PayloadProfileRequest(
    ...,
    ordered_paths=(),
)
```

This preserves the Profile policy domain for fail-closed lower materialization.

Zero paths is not equivalent to deleting/omitting the Profile.

## 6. Disabled/known-disabled behavior

Disabled Profiles produce no request.

A known disabled Device referenced by an enabled Profile naturally contributes zero current
paths because it has no active `DeviceBindingIntent`/binding projection.

## 7. Component design

This is pure calculation inside the current `PayloadPolicyCalculator` responsibility.

No new component is introduced.

The output type `PayloadProfileRequest` is the complete current architecture contract for
structural Profile membership; it is not a partial `*Intent` value.

## 8. Simplification review

Not introduced:

- availability priority;
- traffic envelope;
- NAT;
- publications;
- route metrics;
- Linux table/rule state;
- Manager/event state;
- history/replay.

Those concerns belong to later independent review units.

## 9. Evidence plan

Rootless unit tests:

- Profile Device order overrides global binding output order;
- selector order precedes slot order inside a Device;
- only Devices named by Profile contribute paths;
- waiting/unbound candidates do not contribute;
- zero-path enabled Profile remains present;
- disabled Profile omitted;
- concrete endpoint replacement does not change logical path membership identity;
- config -> binding -> Profile request seam.

## Verdict

**PASS — pure PayloadProfileRequest projection may be implemented.**
