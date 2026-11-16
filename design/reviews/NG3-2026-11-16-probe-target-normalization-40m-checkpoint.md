# VPN-GATE NG3 — Probe Target Normalization 40m Cycle Checkpoint

**Cycle:** `ng3-design-cycle-20261116-probe-target-normalization-40m`  
**CYCLE_INTERVAL:** 40m  
**Base:** `dff147e6ff5dbcc7800c8376382d948bc042297a`

## Trigger

Recovered prior-chat context showed that the preceding whole-tree closure over-specified one
availability detail.

Historically accepted:

```text
external target may be omitted
explicit target is preserved
normalization always produces a concrete IPv4 target
probe runtime always receives concrete target
```

Not historically established:

```text
which target is selected when external target is omitted
```

The previous NG3 choice "derive from current VPN endpoint/network facts" therefore had no
sufficient requirement evidence.

## Correction completed

Requirements corrected:

- `VPNG-R3.R6.R3.R2` now requires optional external target + concrete normalized runtime
  target;
- it no longer claims that the default comes from VPN endpoint/binding facts;
- R3 ancestry dependent on this semantics has been reopened.

Architecture corrected:

- target defaulting belongs to configuration normalization;
- `AvailabilityProbeAgent` receives normalized concrete target;
- `ActiveProbeDriver` receives normalized concrete target;
- `VPNPathAdapter` no longer owns availability target inference;
- payload availability still contains no target/mechanism/cadence.

## Current contract

```text
external AvailabilityCheckConfig:
    logical_path_id
    mechanism
    target?   # optional

configuration normalization:
    explicit target -> preserve exactly
    omitted target  -> apply accepted default-target rule

runtime AvailabilityProbeIntent:
    logical_path_id
    mechanism
    target: concrete IPv4
```

First-release mechanism remains ICMP.

## Current tree state

```text
R/C nodes: 83
closed:    79
open:       4
```

Open chain:

```text
VPNG-R3
└── VPNG-R3.R6
    └── VPNG-R3.R6.R3
        └── VPNG-R3.R6.R3.R2
```

Mechanical validation:

```text
closed without architecture ref: 0
broken decomposition links:       0
stale VPN-endpoint derivation:     0
```

## Remaining human/recovery gate

Exactly one semantic question remains:

> When the user omits availability probe target, what deterministic product rule selects the
> concrete IPv4 target during configuration normalization?

This rule may be recovered from historical discussion/evidence or explicitly decided again.

Until then, NG3 must not:

- infer the target from VPN endpoint simply because it is convenient;
- move defaulting into AvailabilityProbeAgent/Driver;
- expose an unresolved target to runtime probe execution;
- change payload availability contracts.

## Prior whole-tree checkpoint

The previous `83/83 closed` checkpoint remains a valid historical artifact for its cycle,
but is superseded for the active branch by this correction.

## Verdict

**PASS — CORRECTION COMPLETE; ONE HUMAN/RECOVERY GATE OPEN.**

No additional autonomous architecture work is justified until the default-target rule is
recovered or accepted.
