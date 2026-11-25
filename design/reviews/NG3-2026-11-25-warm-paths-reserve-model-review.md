# NG3 warm_paths / reserve managed-presence model review — 2026-11-25

**Review unit:** configuration-driven managed Device presence after projectholder clarification
that reserve membership is not warm capacity.  
**Normative target:** `VPNG-U001-R1.R3.R7.R3*`.  
**Architecture target:** A.002, A.004, A.012, new A.013, C.004 and D.001.

## Scope

Accept or reject a general managed-presence model that:

1. keeps warm redundancy config-driven;
2. counts only ordinary memberships in the warm target;
3. treats reserve as a temporary exception after ordinary convergence;
4. keeps ordinary recovery demand active while reserve is present;
5. preserves external Device ownership and the availability boundary;
6. does not require traffic-triggered wake/idle machinery.

## Findings and dispositions

### F1 — canonical field is `warm_paths = 0 | N | "all"`

**Decision:** accepted.  
**Resolution:** fixed.

The name describes what the user actually controls: the number of ordinary paths kept warm.
It does not pretend to configure a number of reserve paths.

Omission means `"all"` ordinary memberships. Numeric N larger than configured enabled
ordinary capacity is invalid. Reserve capacity cannot validate an impossible warm target.

### F2 — reserve does not satisfy warm capacity

**Decision:** accepted.  
**Resolution:** fixed.

Only fresh ordinary PathBindings reduce regular deficit. Externally prepared and managed
ordinary paths count equally for satisfaction, but only explicitly managed Devices are
actuation subjects.

A present reserve path is usable by the existing payload/availability machinery but leaves the
regular deficit unchanged.

### F3 — ordinary selection remains sticky/cardinality-oriented

**Decision:** accepted.  
**Resolution:** fixed.

Numeric `warm_paths` is a cardinality goal, not continuous best-identity rebalance. If enough
ordinary paths are already present, a sleeping higher-baseline ordinary Device is not started
solely to replace a living lower-baseline path.

When there is a deficit, absent managed ordinary candidates are selected deterministically by
the existing Profile/Device baseline hierarchy. Surplus managed ordinary presence may lose
demand, but actual removal remains behind A.012 dependency release.

### F4 — reserve is a second phase, not a parallel startup race

**Decision:** accepted.  
**Resolution:** fixed.

A.012 must first attempt ordinary convergence. Existing reserve presence is retained during
that intermediate phase. After a fresh C.004 observation, a still-existing regular deficit may
create the minimal reserve exception needed for fallback.

This prevents normal startup from needlessly starting an expensive/limited reserve at the same
time as an ordinary managed Device that has not yet been given a chance to converge.

### F5 — regular recovery naturally retires reserve

**Decision:** accepted.  
**Resolution:** fixed.

Reserve presence does not reduce regular deficit and therefore never suppresses ordinary
recovery demand. Once ordinary paths recover, the fresh final projection removes the reserve
exception; A.012 then releases reserve only after its existing owned-dependency gate permits
absence.

No separate lifecycle failback state machine is required.

### F6 — one Device may satisfy different Profile roles

**Decision:** accepted.  
**Resolution:** fixed.

Per-Profile ordinary/reserve demands are OR-aggregated by Device. The same Device may be
ordinary in one Profile and reserve in another. One Profile withdrawing its reason can never
stop a Device still demanded by another.

### F7 — traffic and availability remain outside lifecycle demand

**Decision:** accepted.  
**Resolution:** fixed.

Packet presence, first-packet arrival, idle timeout and availability verdicts are not inputs to
A.013. Availability continues to reorder existing paths only.

The previously researched traffic-driven presence model remains optional future work indexed
by `design/future-possibilities.md`.

### F8 — R7.R3 decomposition is now complete

**Decision:** accepted.  
**Resolution:** fixed.

The new children separate:

- canonical warm target;
- ordinary demand/aggregation;
- reserve exception/recovery;
- independence from payload/availability evidence.

A.002 owns normalization, A.013 owns pure demand projection, A.012 owns ordered lifecycle
convergence, C.004 supplies fresh presence and D.001 remains the bounded integration-specific
actuator. This is sufficient architecture closure even though current Python materialization
is still incomplete.

## Requirement disposition

- `VPNG-U001-R1.R3.R7.R3` -> `decomposition: complete`, `closed` by immediate-child closure;
- `...R3.R1` -> `closed`;
- `...R3.R2` -> `closed`;
- `...R3.R3` -> `closed`;
- `...R3.R4` -> `closed`.

No other Requirement/Constraint changes status in this unit.

## Implementation frontier

The next implementation block is bounded:

1. current-only `warm_paths` normalization without changing frozen Release-1 grammar;
2. pure A.013 Calculator and unit evidence;
3. A.012 explicit desired-set input and two-phase ordinary/reserve composition;
4. runtime status truth for current desired managed Devices;
5. live/integration evidence for ordinary failure -> reserve -> ordinary recovery -> reserve
   release.

## Verdict

**PASS.** Warm redundancy and reserve now form one coherent model: ordinary paths define the
configured warm goal, reserve temporarily substitutes for a remaining regular deficit without
ever satisfying that goal, and ordinary recovery therefore removes reserve demand naturally.
