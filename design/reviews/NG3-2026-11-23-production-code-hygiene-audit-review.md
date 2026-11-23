# NG3 2026-11-23 — production Python code-hygiene audit

**Status:** in progress  
**Scope:** current NG3 production Python under `design/NG3/code/python/rou/`, excluding
tests and experiment scripts.

**Audit categories requested by the owner:**

1. unneeded executable code;
2. unused types/classes/variables/constants;
3. unreachable code, including dead loops/branches;
4. single-call functions;
5. duplication and magic values;
6. component-model mismatches;
7. undocumented code.

**Audited production modules:** 116 at cycle entry.

## Current verdict

The pass found real hygiene debt, but no evidence of a broad unreachable-code problem.

The cleanup has continued beyond the first slice. F8 and the direct F10 finding are now
implemented; F9 documentation work and F11 superseded-convergence evidence migration remain
open, so this audit is still not a completed development block.

## Findings and dispositions

### F1 — superseded `selected_host_boundary.py` was dead production code

**Decision:** accepted.  
**Resolution:** fixed.

The module described itself as a postponed aggressive authoritative host-routing prototype,
had no production caller, was not referenced by current architecture, and every exported
symbol was referenced only by its own test or historical reviews.

Current E.003/E.004 aggressive routing implementation supersedes that prototype.

Removed:

- `rou/selected_host_boundary.py`;
- `tests/test_selected_host_boundary.py`;
- its implementation-traceability entry.

Historical reviews remain unchanged.

### F2 — two compatibility modules were retained only by current tests

**Decision:** accepted.  
**Resolution:** fixed.

`nft_scaffold_executor.py` and `route_priority_executor.py` were compatibility shims for
pre-Enforcer terminology. No active NG3 experiment script imports either module.

Tests now import the canonical Enforcer modules directly and the stale test filenames were
renamed accordingly. Both compatibility production modules and their trace entries were
removed.

### F3 — not every historical alias is dead

**Decision:** accepted.  
**Resolution:** retain only where current evidence still consumes it.

The audit explicitly distinguished unused compatibility surface from aliases still imported by
active NG3 experiment scripts. Aliases such as `LinuxPayloadNatBackend`,
`LinuxProbeLocalBackend`, `LinuxNftScaffoldBackend`,
`LinuxNftNamespaceBackend` and `LinuxHostManagedRoutingBackend` remain because current
experiment/evidence code still imports them.

By contrast test-only or completely unreferenced aliases were removed for local integration,
local publication, Device firewall and route-priority code. Current tests use canonical
`Driver` / `Enforcement` names.

### F4 — three narrow Protocol types still violated the accepted component terminology

**Decision:** accepted.  
**Resolution:** fixed.

The following Protocols represented narrow technical Driver boundaries, not Backend
compositions:

- `PayloadNatMutationBackend`;
- `PayloadNftScaffoldBackend`;
- `DeviceFirewallMutationBackend`.

They were renamed to the corresponding `*Driver` types. No compatibility alias was kept
because no external/current evidence consumer used these Protocol names.

Broad composition types such as `CompositeNftMutationBackend`,
`StructuralPolicyMutationBackend`, `ProbeRoutingConvergenceBackend` and
`StackReturnAffinityBackend` remain legitimate Backend contracts.

### F5 — identical forwarding-gate loss logic was duplicated three times

**Decision:** accepted.  
**Resolution:** fixed.

`composite_nft_mutation.py`, `device_firewall_mutation.py` and
`structural_policy_mutation.py` each had the same private `_gate_lost()` implementation.

The fail-closed semantic now lives once in `forwarding_gate.py` as
`forwarding_gate_is_lost()`:

> return lost unless a fresh observation proves `DISABLED`; observation failure is lost.

The three callers use the shared owner-level function.

### F6 — one true single-call helper had no independent semantic value

**Decision:** accepted.  
**Resolution:** fixed.

`release1_config._is_enabled()` had one call site and only returned
`body.get("enabled") is True`. It was inlined.

Other one-production-caller functions reviewed in this pass were not automatically inlined
when they represent a real architecture/calculation boundary or are also direct evidence API.
Single call count alone is not treated as sufficient deletion criterion.

### F7 — no literal dead branches or non-terminating convergence loops were found

**Decision:** accepted current evidence; continue structural reachability review.

A mechanical source pass over all production modules found no literal dead constructs such as
`if False`, `while False`, `if 0` or `while 0`.

The only production `while True` convergence loops found are in:

- `structural_policy_transaction.py`;
- `probe_routing_convergence.py`.

Both have explicit terminal returns for confirmed/failure/regression conditions and require a
strictly decreasing distance/rank after every successful mutation step. They are not
unbounded retry loops.

This finding does not claim compiler-grade whole-program reachability proof; remaining
symbol/call-site review continues under the same audit.

### F8 — repeated IP port bounds were a real magic-value duplication

**Decision:** accepted.  
**Resolution:** fixed.

The same IP transport-port invariant had been independently encoded as literal `1..65535`
checks across configuration, semantic policy, observation and Linux-lower code.

A small technical primitive `ip_port.py` now owns:

- `IP_PORT_MIN`;
- `IP_PORT_MAX`;
- `is_ip_port()`.

Callers keep their context-specific diagnostics and policy semantics; only the scalar range
invariant is shared. This avoids both magic-value drift and a larger artificial utility
abstraction. The new production unit is explicitly traced to the component scopes that
consume the invariant.

### F9 — code-level documentation is systematically incomplete

**Decision:** accepted.  
**Resolution:** open cleanup finding.

Implementation traceability is strong at module level, but the mechanical public-symbol pass
found missing docstrings across almost every production module. This is not confined to
obvious data holders; multiple public architecture-facing functions/classes lack local API
documentation.

A blanket "docstring every enum/dataclass" rewrite is not justified. The next documentation
pass should define and apply a useful boundary:

- architecture-facing component classes and public callable contracts require local
  responsibility/semantic docstrings;
- non-obvious algorithms require invariant/failure-semantics documentation;
- trivial immutable data carriers may rely on field names/type contracts when the meaning is
  already unambiguous.

### F10 — symbol-level reachability and one-call-site audit found one test-only production API

**Decision:** accepted.  
**Resolution:** fixed for the direct finding; follow-up superseded-convergence finding split
out below.

The audit covered all current production modules and classified low-occurrence top-level
functions/classes/constants against local callers, production imports, current evidence use
and architecture-facing API contracts.

`config.parse_structural_config()` was the clear production/test leakage: its own docstring
said it existed for isolated structural tests, while the canonical human-facing
ConfigurationAdapter is `release1_config.py` and production normalization already calls the
lower `_parse_structural_root()` directly.

The wrapper was moved to test support and removed from the production package/export facade.

Low production caller count alone was not used as a deletion rule. In particular,
`restart_controller_once()` remains because `restart` is an explicit A.001
ProductLifecycleControl API even though the current alpha does not call it internally.

No additional unused private helper/constant layer was found by the completed symbol pass.

### F11 — superseded per-owner convergence APIs remain coupled to historical live evidence

**Decision:** accepted.  
**Resolution:** open cleanup finding; do not delete before evidence migration.

The current runtime converges nft policy through the unified structural
`NetworkPolicyEnforcer` / `StructuralPolicyTransaction`. The following older orchestration
APIs have no current production caller:

- `converge_device_firewall_step_once()`;
- `converge_payload_nat_step_once()`;
- `converge_composite_nft_step_once()`.

They survive because dedicated unit/integration evidence still invokes them. Their modules
also contain lower primitives that current code still reuses, notably physical snapshot types
and `apply_composite_nft_step()`.

Deleting these modules wholesale would therefore both break current Drivers and discard live
NAT/Device-firewall evidence. The safe cleanup sequence is:

1. move/retain the genuinely current lower snapshot/dispatch primitives at their proper
   Driver/structural boundary;
2. migrate the dedicated live NAT and Device-firewall convergence evidence to the current
   structural Enforcer path (the present structural integration does not exercise those
   desired owners);
3. remove the superseded per-owner orchestration types/functions/tests and obsolete workflow
   steps;
4. rerun full structural/live evidence.

This is a component/evidence migration, not a mechanical dead-code deletion.

## Requirement / architecture impact

No product requirement semantics changed.

The implemented cleanup only removes unreachable/superseded production surfaces, aligns
implementation naming with the already accepted component model, and deduplicates an existing
fail-closed check.

No architecture change is currently required; the removed prototype was not part of current
architecture.

## Current requirement-state inventory

No requirement status is changed by this audit.
