# NG3 2026-11-18 — sticky/reserve 35m CD checkpoint

**Cycle:** `ng3-design-cycle-20261118-sticky-reserve-35m`  
**CYCLE_INTERVAL:** 35m  
**Cycle start:** `a00e66a84d182e3c1dc2d054402cab562355c11d`

## Verdict

**PASS — safe logical boundary reached.**

The cycle converted the outbound availability discussion into a smaller Release-1 policy and
working reference code without introducing per-flow state. Autonomous implementation now ends
at the already known Linux availability probe-plane evidence/materialization gate; no new
probe mechanism or integration-specific target derivation is invented in this cycle.

## Snapshot sequence

### Main snapshot 93 — sticky active-route / reserve semantics

`001c41bd111a017c5777fe46502830923ac8fbb2`

The previous combination of immediate recovery failback plus mandatory established-flow
concrete-path affinity was replaced by:

```text
ordinary active path remains usable
    -> recovery of another path does not preempt it

recovered path
    -> returns to baseline position among standby paths

active membership marked reserve
    -> a usable higher-baseline path may preempt it
```

Canonical Profile-local membership syntax:

```text
<deviceid>
<deviceid>:reserve
```

`reserve` is a property of the Device membership inside one Profile, not of the Device
globally. Unsuffixed membership is sticky by default.

Outbound Release-1 availability no longer requires per-flow concrete-path affinity,
conntrack-like flow state, source-identity preservation or transport migration across a real
active-path failure. Managed-stack return affinity for remote-initiated traffic remains a
separate unchanged responsibility.

The weak-device/resource-efficiency preference was recorded in
`design/NG3/declarations.md` deliberately as a **non-normative declaration**, not as a
Requirement or Constraint.

### Main snapshot 94 — sticky/reserve reference code

`a26b80ed2376f5f4944f98b6f8969eca06e89981`

Canonical parsing now normalizes:

```text
device_order = ["primary", "backup:reserve"]

->
structural device_order = ("primary", "backup")
reserve_device_ids = {"backup"}
```

Unknown membership suffixes and duplicate underlying Device memberships are rejected.

`calculate_effective_path_order()` implements ordinary sticky recovery and reserve failback
using Profile-local reserve Device IDs. A review correction changed the initial
`reserve_paths` draft to `reserve_device_ids`, preventing impossible partial-reserve state
inside one Device membership.

The pure integration test covers:

```text
canonical :reserve config
    -> normalized reserve_device_ids
    -> Device binding
    -> logical paths
    -> reserve failback order
```

The reviewed unit lane passed.

### Main snapshot 95 — active workflow consolidation

`43f4ed017838ad576722925b4967834b4d4f30f3`

The active-lineage guard expected exactly:

- `.github/workflows/actual-main-hygiene.yml`;
- `.github/workflows/ng3-python.yml`.

The tree still contained obsolete `ng3-host-bootstrap.yml`, so normal pushes failed the
guard. EXP-060 was first moved into the canonical NG3 workflow, then the redundant workflow
was removed.

Verification:

- `Actual main lineage guard` run `44398497228`: **PASS**;
- EXP-060 remains visible in canonical CI;
- its historical
  `host bootstrap fresh postcondition does not match desired state` failure remains
  unchanged and was not hidden by consolidation.

### Main snapshot 96 — bounded Profile active-route state

`4a7ed32b8b3acf909e077b05c65eef257fe21ef2`

`availability_routing_state.py` adds exactly one optional current
`LogicalPathId` per Profile and projects:

```text
confirmed problem paths
+ previous Profile active path
+ reserve_device_ids
    -> effective order
    -> next Profile active path
```

Covered transitions:

- initial active selection;
- failover when active becomes problematic;
- sticky ordinary recovery;
- reserve recovery preemption;
- disappearance of a previously active structural path;
- all-paths-problematic / empty membership.

The reviewed unit lane passed. No flow table, timer/GC lifecycle, packet history or transport
session state was added.

## Requirement correction and closure

Changed and re-reviewed:

- `VPNG-U003-R3`;
- `VPNG-U003-R3.R4`;
- `VPNG-U003-R3.R5.R2`;
- `VPNG-U003-R3.R7`;
- `VPNG-U003-R3.R8`;
- `VPNG-U003-R3.R8.R1`;
- `VPNG-U003-R3.R8.C1`.

Added:

- `VPNG-U003-R3.R4.R1` — explicit Profile-local reserve failback;
- `VPNG-U003-R3.R4.R1.R1` — canonical `:reserve` grammar and scope.

Current mechanical state:

```text
normative R/C nodes:              172
closed:                           172
pending_closure:                    0
rejected_closure:                   0
open:                               0

requirement IDs with arch refs:   172
architecture requirement IDs:    172
missing exact architecture refs:   0
extra architecture refs:           0
```

## Accumulated requirement-state inventory

### `decomp`

Six historical decomposition-link occurrences remain resolved:

1. `VPNG-U005-R5 -> VPNG-U005-R5.R6`;
2. `VPNG-U004-R4.R6 -> VPNG-U004-R4.R6.R1`;
3. `VPNG-U001-R1.R3 -> VPNG-U001-R1.R3.R2`;
4. `VPNG-U001-R1.R2 -> VPNG-U001-R1.R2.R2`;
5. second occurrence of `VPNG-U004-R4.R6 -> VPNG-U004-R4.R6.R1`;
6. second occurrence of `VPNG-U001-R1.R3 -> VPNG-U001-R1.R3.R2`.

Pending `decomp`: **none**.

### `unreal`

Active: **none**.

### `broken`

Active: **none**.

### `[rejected_closure]`

Active: **none**.

Historical repaired closure rejection:

- `VPNG-U001-R1.R3.C1.R1.R1` was rejected by EXP-049 when the terminal managed-local policy
  blocked a real in-stack OpenVPN transport;
- later supported-integration/systemd onboarding work repaired that closure and restored the
  node to `[closed]`.

## Current implementation boundary

The first alpha runtime still rejects `availability_check` rather than accepting an
unimplemented capability.

The remaining end-to-end availability chain requires work below the now implemented
sticky/reserve policy:

```text
normalized Profile/path availability subject
    -> concrete target normalization
    -> AvailabilityProbeAgent / ICMP Driver
    -> Linux probe-plane materialization
    -> fresh evidence
    -> existing bounded confirmation state
    -> implemented Profile active-route state
    -> implemented effective-order calculator
    -> existing route-priority convergence
```

Two existing boundaries prevent honest autonomous activation now:

1. Linux probe-plane materialization remains behind its previously accepted
   evidence/target-platform gate.
2. Bare `availability_check = "icmp"` has a closed product contract requiring deterministic
   subject-specific target derivation, but exact Device/integration formulas are intentionally
   implementation/evidence specializations. They must not be replaced by an arbitrary global
   target or by convenient VPN-endpoint inference without evidence.

Therefore the cycle does not create a speculative ProbeAgent/Driver or invent target formulas
just to make the alpha accept `availability_check`.

## CI/evidence state

Relevant positive evidence:

- sticky/reserve parser + priority calculator `unit`: **PASS**;
- bounded active-route state `unit`: **PASS**;
- active-lineage workflow guard after consolidation: **PASS**.

Existing privileged evidence failures remain visible and are not regressions introduced by
this cycle:

- EXP-057 nft-marked host bootstrap;
- EXP-060 selected host-bootstrap backend;
- EXP-063 profile gateway-NAT association.

They remain separate evidence/runtime work and do not invalidate the pure/config
sticky/reserve slices.

## Simplification result

The design question that started this cycle has become a bounded policy:

```text
default
    = keep a healthy active route

explicit :reserve
    = allow failback to a higher-baseline healthy route
```

That policy removes the Release-1 need for outbound per-flow route affinity while preserving
an explicit escape hatch for expensive/limited backup links.

The next availability implementation work should resume at the existing probe
target/materialization evidence boundary, not by reintroducing flow tracking or another
routing-state framework.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005-R5` -> `VPNG-M001-R1.R1`
- `VPNG-U005-R5.R6` -> `VPNG-M001-R1.R1.R6`

The original IDs in the historical body are intentionally preserved.
