# NG3 — Raspberry Pi 2 resource-envelope future target

**Status:** POSTPONED FUTURE TARGET / not a current release gate  
**Created:** 2026-11-22  
**Requirements:** `VPNG-M001-R3`, `VPNG-M001-R3.R2`, `VPNG-M001-R3.R2.R1`

## Accepted future target

The project keeps one concrete weak-device target so resource suitability does not degrade
into an untestable statement about an abstract "small gateway".

The future representative workload is:

```text
target platform: Raspberry Pi 2
enabled Devices: 2
enabled Profiles: 1
managed traffic: 100 Mbit/s aggregate

steady CPU: <= 10%
steady RAM: <= 30 MiB
peak CPU: <= 80%
peak RAM: <= 50 MiB
```

These values are an accepted future resource target, not a current alpha/beta/release
readiness gate.

## Current decision

Do not spend current development/evidence capacity building the missing benchmark harness,
traffic mix, VPN implementation matrix or measurement methodology solely to close this target.

`VPNG-M001-R3.R1` remains an active engineering preference: equally correct designs should
still avoid unnecessary steady-state CPU, memory, allocation and bookkeeping cost.

The broader `VPNG-M001-R3` resource-constrained suitability obligation is also postponed:
there is no current accepted resource-suitability acceptance envelope independent of the
Raspberry Pi 2 target. This deferral covers its unproven weak-device suitability and
associated acceptance work, **not** the active engineering preference in
`VPNG-M001-R3.R1`, which remains permanently applicable to relevant design decisions.
The concrete Raspberry Pi 2 acceptance branch remains intentionally incomplete and deferred.

## Re-entry

Resume decomposition/evidence for `VPNG-M001-R3` and `VPNG-M001-R3.R2*` only after an explicit project-holder
decision that weak-device acceptance has become useful enough to justify the work.

The re-entry pass must define at least:

- representative traffic mix inside the 100 Mbit/s aggregate load;
- the two Device VPN implementations/integration shape;
- availability-check workload, if any;
- CPU accounting method and steady-state window;
- RAM accounting method;
- peak interval/measurement semantics;
- reproducible target-environment setup.

If Raspberry Pi 2 hardware is no longer practically available when this work is resumed, do
not silently substitute emulation or a newer board. The project holder must explicitly select
a replacement resource-constrained target and decide whether the numerical envelope is
retained, translated or replaced.

## Requirement-state inventory

- `VPNG-M001-R3`: `decomposition: incomplete`, [`postponed`];
- `VPNG-M001-R3.R1`: `decomposition: complete`, [`permanent`];
- `VPNG-M001-R3.R2`: `decomposition: incomplete`, [`postponed`];
- `VPNG-M001-R3.R2.R1`: `decomposition: incomplete`, [`postponed`];
- active `decomp`: none introduced;
- active `unreal`: none;
- active `broken`: none;
- `rejected_closure`: none.
