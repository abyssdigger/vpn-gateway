# VPN-GATE NG3 — Probe Target Normalization Correction Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-probe-target-normalization-40m`  
**Base checkpoint:** `dff147e6ff5dbcc7800c8376382d948bc042297a`

## Trigger

Recovered prior-chat context clarifies the historical availability target contract:

- user-facing probe `target` was intended to be optional;
- if explicitly supplied, that IPv4 is used;
- before runtime probe execution, normalization produces a concrete `IPv4Address`;
- `AvailabilityProbeRequest` therefore always carries an explicit target;
- target/mechanism/interval belong to the probe side;
- target does not enter `PayloadTrafficManager` or availability hysteresis.

The recovered material explicitly does **not** establish the actual rule used to choose the
default target when the user omits it.

## Finding

The previous NG3 gate-resolution cycle went one step beyond the evidence by selecting:

```text
omitted target
    -> derive from current VPN binding / endpoint network facts
```

That rule was not historically established and was not separately accepted as a new product
decision.

Therefore the architecture closure of that exact refinement was invalid.

This is precisely the kind of semantic overreach the requirements-first process is intended
to detect.

## Corrected product semantics

The accepted contract is now:

```text
external availability check:
    mechanism
    target?          # optional

configuration normalization
    -> concrete target selection

runtime probe demand:
    mechanism
    concrete IPv4 target
```

Explicit target semantics are closed:

```text
user target = X
    -> normalized runtime target = X
```

Omitted target semantics are only partially known:

```text
user target omitted
    -> product must apply a deterministic default-target rule
    -> runtime still receives one concrete IPv4 target
```

The actual default-target rule/source is not currently accepted.

## Corrected architecture boundary

Target-defaulting belongs to configuration normalization, not to:

- `AvailabilityProbeAgent`;
- `ActiveProbeDriver`;
- `VPNPathAdapter`;
- payload availability state.

The probe Agent/Driver receive an already normalized concrete target and do not know whether
it came from explicit user configuration or a defaulting rule.

This preserves the historical probe/payload separation:

```text
probe side:
    target
    mechanism
    cadence

payload availability side:
    path/channel identity
    enabled
    hysteresis
```

## Requirement closure impact

The following previously closed nodes are reopened because their accepted architecture
depended on the invented default-target rule:

- `VPNG-R3`;
- `VPNG-R3.R6`;
- `VPNG-R3.R6.R3`;
- `VPNG-R3.R6.R3.R2`.

The following remain closed:

- user owns the practical check criterion;
- first release supports ICMP only;
- explicit target is preserved exactly;
- probe runtime consumes a concrete target;
- target/mechanism remain outside payload hysteresis;
- stale observation-context rejection;
- bounded availability hysteresis.

## Remaining human/recovery gate

Exactly one product detail remains:

> When the user omits `target`, what deterministic product rule selects the concrete IPv4
> target during configuration normalization?

Possible historical answers must be recovered as evidence or explicitly re-decided.

NG3 must not infer the answer from current VPN binding merely because that is technically
convenient.

## Prior whole-tree closure review

The previous whole-tree closure review/checkpoint remains a historical artifact of its
cycle, but its `83/83 closed` conclusion is superseded on this active branch by this
correction.

This is not a rejection of the entire H1 architecture. It is a re-opening of the one
refinement whose semantics were over-specified.

## Verdict

**PASS — CORRECTION ACCEPTED.**

Current architecture remains closed everywhere except the default-target selection branch.

No implementation of target omission should begin until the exact default-target rule is
recovered or explicitly accepted.
