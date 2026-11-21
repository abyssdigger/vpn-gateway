# VPN-GATE NG3 — requirement-driven VPN evidence CD checkpoint

**Date:** 2026-11-17  
**Cycle:** `ng3-design-cycle-20261117-requirements-development-evidence-35m`  
**CYCLE_INTERVAL:** 35m  
**CYCLE_START_COMMIT:** `8991da8aa2e91edccd2530fc502ef2e16e126565`  
**T0:** 2026-11-17T06:35:30Z

## Cycle boundary

The coherent requirements/method/evidence-planning block completed before the nominal interval.

Last pre-checkpoint logical commit:

`78fb1067122058d0231bfd22be0598bf91e1a2f7` at
`2026-11-17T06:38:48Z`.

Elapsed logical-development interval before checkpoint: approximately **3m18s**.

## Completed unit

### Requirements methodology

`design/requirements-model.md` now requires:

- derived `Purpose` to correlate causally with the immediate parent `Statement`;
- substantial development/experiments to be driven by exact accepted R/C;
- new causal link:
  `[broken: <R/C-ID>, <R/C-ID>, ...]`.

`broken` means the target R/C itself has become a wrong normative decision because other
accepted R/C broke its premise. It is distinct from `unreal` and
`[rejected_closure]`.

### Continuous Development

`CONTINUOUS-DEVELOPMENT.md` now:

- checks immediate-parent Purpose correlation;
- blocks speculative development without an R/C trace;
- defines `broken` handling;
- carries active `broken` links through implementation gates, reviews and checkpoints.

### NG3 development requirement branch

Added and closed on accepted documentary architecture/evidence planning:

- `VPNG-U007-R7.R7`;
- `VPNG-U007-R7.R7.R1`;
- `VPNG-U007-R7.R7.R1.R1`.

The branch requires:

```text
requirement-driven development
    ->
basic real-VPN in-stack applicability evidence
    ->
dependent lifecycle/aggressive-config evidence
    ->
only then lifecycle/ownership semantic decision
```

### VPN evidence sequence

EXP-049 remains the prerequisite basic applicability gate.

Created:

`design/experiments/EXP-050 NG3 bounded VPN lifecycle applicability/README.md`

Status:

**BLOCKED — execute only after EXP-049 PASS.**

EXP-050 requires the exact integration that passed EXP-049 and covers:

- start;
- stop;
- restart with unchanged VPN-specific config;
- restart with changed VPN-specific config;
- stale-generation absence;
- aggressive VPN-specific hooks/equivalent mutations of routes, RPDB, NAT/firewall, sysctl
  or other managed-domain network state.

### Architecture correction

Removed the unsupported extrapolation that
`VPNG-U001-R1.R3.C1` makes external VPN process lifecycle administrator-owned.

C1 only establishes administrator ownership of VPN provisioning and VPN-specific
configuration.

Current architecture now leaves in-stack VPN process lifecycle/ownership undecided until:

```text
EXP-049 PASS -> EXP-050 -> requirement/architecture decision
```

The existing controller-stop proof remains scoped to currently implemented VPN-GATE-owned
resources.

## Review

`design/reviews/NG3-2026-11-17-requirement-driven-development-vpn-evidence-review.md`

Verdict: **PASS**.

Human decisions required: **none**.

## Mechanical requirement/architecture check

Current tree:

```text
normative R/C nodes:                    148
closed:                                 148
pending_closure:                          0
rejected_closure:                         0
open:                                     0
malformed normative lines:                0
closed without architecture reference:    0
```

No runtime code changed in this unit.

## Requirement-state inventory

### `decomp`

Six accumulated links, all resolved.

Pending: **none**.

### `unreal`

**none**

### `broken`

**none**

### `[rejected_closure]`

**none**

## Open evidence gates

- EXP-049 — **PLANNED/PENDING execution**;
- EXP-050 — **BLOCKED on EXP-049 PASS**.

## Next intended logical unit

Execute/review **EXP-049** for one concrete Release-1 candidate VPN integration.

Do not implement bounded-VPN lifecycle ownership or EXP-050 mechanics before EXP-049 PASS.

## Checkpoint verdict

**PASS — REQUIREMENT/DEVELOPMENT EVIDENCE-SEQUENCING UNIT COMPLETE.**


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U007-R7.R7` -> `VPNG-D001-R1.R1.R7`
- `VPNG-U007-R7.R7.R1` -> `VPNG-D001-R1.R1.R7.R1`

The original IDs in the historical body are intentionally preserved.
