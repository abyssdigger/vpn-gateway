# NG3 continuous availability loop / alpha integration review

**Date:** 2026-11-19  
**Cycle:** `ng3-design-cycle-20261119-probe-continuous-availability-loop-35m`  
**Scope:** continuous Release-1 ICMP availability orchestration from shared probe policy through
bounded observation, confirmation/effective order, make-before-break route priority, alpha
lifecycle and current status.

## Reviewed contracts

- `VPNG0003-R3.R2`
- `VPNG0003-R3.R3`
- `VPNG0003-R3.R4`
- `VPNG0003-R3.R5.R1`
- `VPNG0003-R3.R5.R2`
- `VPNG0003-R3.R6` subtree
- `VPNG0003-R3.R7`
- `VPNG0003-R3.R8`
- `VPNG0004-R4.R3.R1`
- `VPNG0004-R4.R5`
- `VPNG0005-R5.R2.R1`
- `VPNG0006-R6.R2`
- `VPNG0006-R6.R3`
- architecture §4.3/4.4, §5, §7, §8, §10.1, §13.

No product requirement or user-facing config was changed.

## Resulting runtime path

The Python alpha now composes the already accepted pieces into one externally paced loop:

```text
periodic Manager audit
        |
        v
fresh binding/path realization
        |
        v
Device-default/Profile-override availability resolution
        |
        v
shared payload + probe NetworkPolicyLayout
        |
        +--> payload structural desired
        |       + probe-local nft owner
        |       -> guarded structural convergence
        |
        +--> probe route/RPDB desired
                -> fail-closed probe-routing convergence
                -> fresh exact readiness
                -> <=1 ICMP attempt per current subject
                -> fresh ProbeEvidence
                -> bounded confirmation state
                -> sticky/reserve effective order
                -> existing make-before-break route-priority convergence
                -> RuntimeStatusAgent current snapshot
```

The alpha uses its existing one-second audit wakeup as the local cadence. There is no
independent scheduler framework and no user timing/hysteresis surface.

Current alpha reference policy uses finite local thresholds 2/2 and a one-second ICMP reply
timeout. These are implementation values, not user-facing policy.

## Findings and dispositions

### F1 — structural reconcile would otherwise undo availability failover

The structural desired-state builder originally consumed baseline Profile order. If route
priority changed after availability evidence, the next structural audit would classify those
metrics as drift and restore baseline before availability changed them again.

**Disposition:** accepted and fixed. `AlphaPreparedPolicy.build_current()` now builds the
shared probe assembly from baseline membership, synchronizes current availability Manager
state, and constructs payload structural desired state from the resulting **effective**
Profile order. Baseline Profile order is retained separately as policy input only.

A regression test establishes A->B failover, rebuilds current structural desired state, and
verifies metrics remain B=1/A=2 rather than reverting.

### F2 — probe-local nft must share the composite owner transaction

Materializing probe-local admission through a second nft writer would violate the accepted
single shared nft ownership boundary.

**Disposition:** fixed. `build_payload_network_policy_desired_state` accepts the already
normalized `ProbeLocalRuleSpec` set and includes it in `CompositeNftDesiredState`.
Existing structural convergence remains the sole writer for that nft namespace.

### F3 — probe routing needs separate owner-safe convergence

Probe tables/RPDB rules are not payload structural dispatch state and have their own
fail-closed ordering proof.

**Disposition:** fixed. `linux_availability_cycle.py` runs the existing
`converge_probe_routing` owner before readiness verification. It does not route probe rows
through payload structural mutation.

### F4 — local probe-plane defects must not become remote negative evidence

An unready RPDB/nft precondition must block attempts without degrading a path.

**Disposition:** preserved end-to-end. Readiness failure returns an unconfirmed availability
cycle and the observation tick performs zero probe I/O / zero negative evidence.

### F5 — the alpha previously rejected canonical availability_check

The config grammar and lower probe mechanisms were accepted, but the executable alpha still
failed fast on `availability_check`.

**Disposition:** fixed. Availability-enabled canonical config is now accepted, projected into
probe-local desired state, and driven through startup plus periodic runtime cycles.
`+snat` remains independently rejected because that capability is still not fully
materialized in this alpha.

### F6 — lower probe identity needed one selected alpha/reference allocation

Probe UID and conntrack mark are Linux realization resources, not user config.

**Disposition:** selected in `linux_policy_platform.py` as
`NG3_PROBE_LOCAL_PLATFORM(process_uid=4242, conntrack_mark=0x20000001)`.
UID 4242 is the current EXP-067-proven non-root worker identity; the mark is in a namespace
separate from managed-stack affinity marks. This choice does not create a product-level
numeric contract.

### F7 — runtime status remained "unconfirmed" after successful monitoring

After continuous availability became real, `RuntimeStatusAgent` still retained the old
placeholder `unconfirmed` availability state even on a confirmed loop.

**Disposition:** accepted and fixed. Current alpha status now reports:

- `disabled` — availability not configured;
- `unconfirmed` — current runtime/reconcile truth is not confirmed;
- `monitoring` — current availability machinery is confirmed and no established problem
  owner exists;
- `problem` — at least one current `(Profile,path)` owner has established availability
  problem state.

`monitoring` intentionally does not claim universal positive remote health.

### F8 — stale documentation still described repaired blockers

Several architecture/README lines still described the path discriminator as broken, target
derivation as pending, outbound per-flow affinity as a Release-1 gate, availability runtime
assembly as absent, and RuntimeStatusAgent as disconnected.

**Disposition:** fixed in-cycle. Historical defect/review artifacts remain preserved; active
architecture now describes the current implementation.

## Evidence

Current successful descendant workflow evidence before the final status-only strengthening:

NG3 Python run `44506638238`:

- `unit`: PASS;
- `linux-probe-runtime`: PASS;
- `linux-structural-inventory-shape`: PASS;
- `linux-route-priority`: PASS;
- `linux-alpha-smoke`: PASS.

A later workflow on the status strengthening is used for final unit/status confirmation.

Focused new coverage includes:

- confirmation/recovery thresholds;
- ordinary sticky recovery and reserve failback;
- context replacement reset and stale-evidence rejection;
- effective-order -> existing route-priority metric mapping;
- multi-destination route-priority consistency;
- bounded one-attempt-per-subject tick;
- no probe I/O / no fabricated failure when readiness is unconfirmed;
- alpha accepts availability and includes probe-local desired rules;
- structural rebuild preserves an established failover order;
- status monitoring/problem/unconfirmed transitions.

## Simplification review

Deliberately not introduced:

- separate availability routing Manager;
- separate availability metric/table namespace;
- second nft writer;
- generic scheduler framework;
- task queue, retry journal or missed-tick replay;
- user timing/hysteresis knobs;
- probe result history;
- per-flow outbound affinity for ordinary sticky failover.

The runtime is paced by the existing alpha Manager audit and every physical action reuses an
already accepted owner/convergence boundary.

## Requirement-state inventory

### decomp

All accumulated links remain resolved:

- `VPNG0005-R5 -> VPNG0005-R5.R6`
- `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`
- `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`
- `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`

Repeated occurrences in the requirements tree have the same resolved status.

### unreal

none

### broken

none

### rejected_closure

none

## Verdict

**ACCEPT**, subject to the final descendant unit/status CI remaining green.

The Release-1 ICMP availability path is now assembled continuously in the Python alpha from
canonical config through probe policy, physical observation, bounded confirmation, effective
route order and status. Remaining work is no longer the basic probing loop itself; future work
should be classified separately (for example production Rust migration, stronger status API,
or additional probe mechanisms).


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG0005-R5` -> `VPNG9101-R1.R1`
- `VPNG0005-R5.R2.R1` -> `VPNG9101-R1.R1.R2.R1`
- `VPNG0005-R5.R6` -> `VPNG9101-R1.R1.R6`
- `VPNG0006-R6.R2` -> `VPNG9101-R2.R1.R2`
- `VPNG0006-R6.R3` -> `VPNG9101-R2.R1.R3`

The original IDs in the historical body are intentionally preserved.
