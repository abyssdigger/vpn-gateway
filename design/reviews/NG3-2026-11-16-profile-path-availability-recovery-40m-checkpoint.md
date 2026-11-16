# VPN-GATE NG3 — Profile/Path Availability Recovery Checkpoint

**Cycle:** `ng3-design-cycle-20261116-probe-target-normalization-40m`  
**CYCLE_INTERVAL:** 40m  
**Base:** `dff147e6ff5dbcc7800c8376382d948bc042297a`

## Cycle clock

```text
first correction commit:
ad75c7c2891cd7a74fcb6fbb3aadee3e96485b1b
2026-11-15T23:45:57Z
NG3: correct optional probe target semantics

closure-restored head:
65494d6abcacbf51a0451fb6b5a609047e368474
2026-11-15T23:55:47Z
NG3: restore complete architecture closure status

elapsed:
9m 50s
```

The cycle completes early because the recovered historical semantics fully resolve the one
remaining gate. No unrelated design unit is started merely to consume the interval.

## Historical semantics recovered

The old design distinguished two user-facing forms:

```text
bare icmp
    -> derive one path-specific target from existing Profile/path topology semantics

icmp/<explicit-ip>
    -> use exactly that IPv4 target
```

The exact old field/string grammar is historical UI evidence, not a new NG3 normative syntax.

Key recovered rule:

> There is no universal default probe IP.

Bare ICMP means that target is deterministically derived from already configured
Device/interface/peer/Profile/path semantics.

## Availability identity correction

Availability is not a property of a physical interface alone.

```text
availability subject
    = policy/traffic context + logical VPN path
```

Therefore one physical interface may have different availability for different subjects.

Evidence and hysteresis are subject-specific.

Equivalent lower physical probes may still be shared/deduplicated where
mechanism/path/target are identical.

## Normalization architecture

External configuration:

```text
AvailabilityCheckConfig:
    availability_subject_id
    policy_context_id
    logical_path_id
    mechanism
    target = explicit IPv4 | omitted
```

Pure normalization:

```text
AvailabilityTargetCalculator
    explicit target -> same IPv4
    omitted target  -> deterministic subject-specific derivation
                       from accepted topology semantics
```

Runtime:

```text
AvailabilityProbeIntent:
    availability_subject_id
    logical_path_id
    mechanism
    target = concrete IPv4
```

Probe runtime never receives an unresolved target and does not know whether target was
explicit or derived.

## First-release scope

The existing first-release constraint remains:

```text
mechanism = ICMP echo
```

Future TCP/UDP/HTTP checks remain future extensions.

## Closure restored

Reviewed in:

`design/reviews/NG3-2026-11-16-profile-path-availability-target-recovery-review.md`

Verdict: **PASS**.

Current tree:

```text
R/C nodes:          83
closed:             83
pending_closure:     0
rejected_closure:    0
open:                0
```

Traceability:

```text
unique architecture requirement refs: 83
closure errors:                       0
stale target-gap statements:          0
```

## Important correction history

The earlier whole-tree closure checkpoint was temporarily invalidated because it had
over-specified bare-ICMP target derivation as "derive from VPN endpoint".

This cycle corrected that overreach, reopened only the affected R3 chain, restored the
historically accepted Profile/path-specific semantics, and then re-closed the chain after
review.

The final 83/83 closure is therefore semantically stronger than the earlier one despite
having the same node count.

## Verdict

**PASS — COMPLETE CURRENT NG3 REQUIREMENT/ARCHITECTURE CLOSURE RESTORED.**

The next cycle may proceed to bounded implementation/evidence planning.
