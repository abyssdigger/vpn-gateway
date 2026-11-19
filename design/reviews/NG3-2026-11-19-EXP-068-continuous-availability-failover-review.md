# NG3 EXP-068 continuous availability failover review

**Date:** 2026-11-19  
**Scope:** privileged two-path evidence for the assembled Release-1 ICMP availability loop.

## Finding

The first real run exposed one representation portability defect in the probe-local observer:
Ubuntu 26.04 / nftables 1.1.6 serializes the IPv4 protocol constant as symbolic `"icmp"`,
while the prior EXP-066-era observer accepted only numeric `1`.

The actual nft rule semantics were correct. Probe routing converged exactly, but the local
readiness verifier correctly refused to execute probes because its observer could not classify
the current rules exactly.

## Disposition

Accepted and fixed.

`probe_local_observation._icmp_match` now accepts exactly the two semantically equivalent
JSON values:

```text
1
"icmp"
```

All other protocol values remain conflicts.

Focused unit coverage was added for symbolic ICMP JSON.

## Physical evidence

GitHub Actions run `44508182776`, job `linux-probe-runtime`
(`135505297700`), source `15f8c735d1c0fd667487fe2ff6258d33a934a5d7`:

```text
EXP068_HEALTHY_METRICS={'path0': 1, 'path1': 2}
EXP068_FAILOVER_METRICS={'path1': 1, 'path0': 2}
EXP068_RECOVERY_STICKY_METRICS={'path1': 1, 'path0': 2}
EXP068_RESULT=PASS
```

The same source run also passed:

- unit;
- linux-structural-inventory-shape;
- linux-probe-runtime (EXP-067 + EXP-068).

## Architecture consequence

No requirement or component responsibility changes.

The experiment confirms the already accepted chain:

```text
probe evidence
    -> bounded confirmation
    -> effective order
    -> existing make-before-break route-priority convergence
```

and confirms the Release-1 ordinary-path sticky recovery semantics on real Linux route state.

## Requirement-state inventory

### decomp

All accumulated occurrences remain resolved:

- `VPNG0005-R5 -> VPNG0005-R5.R6`
- `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`
- `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`
- `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`

### unreal

none

### broken

none

### rejected_closure

none

## Verdict

**ACCEPT.**

EXP-068 supplies real two-path evidence for failover and sticky recovery. The representation
defect discovered by the first run is resolved and covered by both focused unit evidence and
the successful privileged rerun.
