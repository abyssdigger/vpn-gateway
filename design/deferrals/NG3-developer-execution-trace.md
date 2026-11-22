# NG3 — developer execution trace decision gate

**Status:** BLOCKED — descendant contracts require explicit project-holder decision  
**Created:** 2026-11-22  
**Requirement:** `VPNG-D001-R2`

## Accepted need and current decomposition

VPN-GATE needs a separately enableable developer execution trace capable of reconstructing
internal execution paths more deeply than the ordinary DEBUG operational log.

The intended distinction is:

```text
INFO   = what materially changed in the environment/lifecycle
DEBUG  = how a component reacted at semantic component level
TRACE  = how execution proceeded inside the component
```

TRACE is not an operational log level. It is explicitly enabled through configuration and
uses a separately specified external trace file.

The parent requirement is now decomposition-complete at the decision-boundary level:

- `VPNG-D001-R2.R1` — instrumented code/function/control-flow/state coverage boundary;
- `VPNG-D001-R2.R2` — argument/result/internal-state representation and data safety;
- `VPNG-D001-R2.R3` — external trace-file lifecycle, sink failure and backpressure semantics;
- `VPNG-D001-R2.R4` — ordering/correlation, format-stability and performance-perturbation contract.

Each child remains intentionally `decomposition: incomplete`.

## Blocking rule

Architecture and implementation remain blocked until whoever explicitly removes this decision
gate performs the further requirement decomposition needed for R1-R4 and obtains the
project-holder decisions required by that refinement.

The blocker must not be bypassed by silently choosing:

- exact function/control-flow/state-transition coverage;
- secret/redaction/truncation behavior;
- file create/append/rotation/failure behavior;
- ordering/correlation/stability/performance guarantees.

The choice of manual, generated, runtime-assisted or mixed instrumentation is an architecture
decision after the requirements above are sufficiently decomposed.

## Re-entry condition

Resume trace architecture/implementation only after the project holder explicitly removes the
gate or authorizes the next decomposition pass. Operational DEBUG must not grow TRACE semantics
as an accidental workaround.

## Requirement-state inventory

- `VPNG-D001-R2`: `decomposition: complete`, intentionally without architecture closure;
- `VPNG-D001-R2.R1`–`R4`: `decomposition: incomplete`, intentionally without architecture
  closure;
- active `decomp`: none introduced;
- active `unreal`: none;
- active `broken`: none;
- `rejected_closure`: none.
