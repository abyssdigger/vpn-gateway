# NG3 2026-11-19 — probe-local structural integration correction review

## Status

**PASS — structural probe-local composition defect repaired and verified.**

This correction was found during the next availability integration review after main snapshot
106.

## Defect

Snapshot 104 integrated the probe-local owner into:

- `CompositeNftDesiredState`;
- composite nft comparison;
- composite nft planning/mutation;
- `LinuxCompositeNftBackend`.

However the outer structural transaction boundary was not updated completely.

Two omissions remained:

1. `StructuralPolicyMutationBackend` / `LinuxStructuralPolicyBackend` did not expose
   `apply_probe_local_step`;
2. `structural_policy_distance()` did not count probe-local missing/stale differences.

Consequences:

```text
whole structural transaction selects APPLY_PROBE_LOCAL
    -> apply_composite_nft_step(StructuralPolicyMutationBackend, ...)
    -> backend lacks apply_probe_local_step
    -> runtime failure
```

and even where a backend supplied the method dynamically, strict-progress accounting could
ignore the probe-local difference.

Standalone probe-local and composite-owner tests therefore passed while the whole structural
integration seam remained incomplete.

## Fix

The structural mutation protocol now includes:

```text
apply_probe_local_step(ProbeLocalMutationStep)
```

`LinuxStructuralPolicyBackend` delegates that operation to its existing
`LinuxCompositeNftBackend`.

`structural_policy_distance()` now includes:

```text
probe_local.missing
probe_local.stale
```

Probe-local conflicts were already lifted into composite nft conflicts and therefore already
participated in the conflict boundary.

## Regression coverage

Added coverage for:

- Linux structural backend -> composite probe-local Driver delegation;
- structural comparison with one missing probe-local rule;
- structural distance accounting including that missing rule;
- whole one-step structural repair selecting probe-local full-diff;
- fresh exact postcondition;
- forwarding activation only after the probe-local owner is exact.

## Safety / semantics

No product semantics change.

The correction only restores the already intended physical composition:

```text
Composite nft owner
    includes probe-local

Structural policy transaction
    owns the whole composite nft owner
    therefore must be able to execute and count probe-local repair
```

No new Manager, rule ordering or availability state is introduced.

## Requirement-state inventory

No normative R/C changed. Active:

- `decomp`: none pending;
- `unreal`: none;
- `broken`: none;
- `[rejected_closure]`: none.

## Verification

Current correction run:

```text
GitHub Actions run: 44466431431
head: 517e220eab1f961a1d41d7d9f6f1586b931070ba

unit: PASS — 772 tests
linux-probe-runtime: PASS
linux-structural-inventory-shape: PASS
```

The new whole-structural regression tests therefore exercise the previously missing
`apply_probe_local_step` path and strict-distance accounting directly.

Known unrelated privileged EXP-057/060/063 failures remain unchanged and outside this
correction.
