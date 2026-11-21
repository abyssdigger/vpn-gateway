# NG3 probe architecture stale-defect correction review

**Date:** 2026-11-19  
**Cycle:** `ng3-design-cycle-20261119-probe-continuous-orchestration-35m`  
**Scope:** consistency audit of active probe architecture after main snapshot 121.

## Finding

Main snapshot 121 correctly contains the repaired path discriminator and the continuous
availability loop, but two active architecture paragraphs still described the pre-repair state:

1. `LinuxIcmpProbeDriver` was said to omit `ping -I <current-ifname>`;
2. `probe_policy.py` was said to omit the RPDB `oif` discriminator.

Those statements contradicted the executable implementation, snapshot 110+, and EXP-068.

## Disposition

**ACCEPTED and fixed.**

Active architecture now states the current implementation:

```text
RPDB:
    uid + ICMP + target + exact oif
        -> dedicated probe table

Driver:
    ping -I <current-ifname> <target>
```

The historical broken-review artifact remains preserved as evidence of the defect and its
recovery. It is no longer described as an active implementation state.

No requirement, configuration grammar, runtime behavior or lower mechanism changed.

## Probe-focused audit result

The Release-1 ICMP probe path currently has:

- concrete Device-default/Profile-override resolution;
- one `(Profile,path)` subject per current logical path;
- distinct same-target multi-path selection via RPDB `oif` + bound Driver execution;
- exact probe-local nft ownership;
- fail-closed route/RPDB convergence;
- exact execution readiness;
- stale-context rejection;
- bounded multi-subject observation;
- confirmation/hysteresis;
- sticky/reserve effective-order projection;
- existing make-before-break route-priority convergence;
- continuous alpha orchestration;
- real two-path failover and sticky-recovery evidence from EXP-068.

No open Release-1 probing implementation seam was found by this audit.

## Remaining work classification

The following are not current Release-1 ICMP probing blockers:

- production Rust migration;
- stable external status/API packaging;
- future TCP/UDP/HTTP checks;
- optional EXP-026 probe-generation conntrack cleanup unless new evidence re-enters it.

## Requirement-state inventory

### decomp

All accumulated occurrences remain resolved:

- `VPNG-U005-R5 -> VPNG-U005-R5.R6`;
- `VPNG-U004-R4.R6 -> VPNG-U004-R4.R6.R1`;
- `VPNG-U001-R1.R3 -> VPNG-U001-R1.R3.R2`;
- `VPNG-U001-R1.R2 -> VPNG-U001-R1.R2.R2`.

### unreal

none

### broken

none

### rejected_closure

none

## Verdict

**PASS.**

The only defect found was stale active documentation. After correction, no unresolved
Release-1 ICMP probing blocker remains.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005-R5` -> `VPNG-M001-R1.R1`
- `VPNG-U005-R5.R6` -> `VPNG-M001-R1.R1.R6`

The original IDs in the historical body are intentionally preserved.
