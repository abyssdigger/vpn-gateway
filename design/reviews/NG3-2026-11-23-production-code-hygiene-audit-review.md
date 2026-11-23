# NG3 2026-11-23 — production Python code-hygiene audit

**Status:** complete  
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

The production-Python hygiene audit is complete for the requested scope. The pass found real
cleanup debt, but no broad unreachable-code or non-terminating-loop problem. Findings F1-F11
are resolved, or explicitly retained where a low call count corresponds to a real
architecture/evidence API.

The final tree removes superseded production surfaces, centralizes the duplicated port
invariant, aligns technical boundaries with the accepted component model, and documents the
non-trivial lower Machinery contracts without adding ritual comments to obvious data
carriers. No unresolved hygiene finding remains in the audited scope.

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

**Decision:** accepted.  
**Resolution:** closed by the completed mechanical and symbol/call-site passes.

A mechanical source pass over all production modules found no literal dead constructs such as
`if False`, `while False`, `if 0` or `while 0`.

The only production `while True` convergence loops found are in:

- `structural_policy_transaction.py`;
- `probe_routing_convergence.py`.

Both have explicit terminal returns for confirmed/failure/regression conditions and require a
strictly decreasing distance/rank after every successful mutation step. They are not
unbounded retry loops.

This finding does not claim compiler-grade whole-program reachability proof. The completed
F10 symbol/call-site pass supplied the structural follow-up and found no additional
unreachable private helper/constant layer beyond the explicitly resolved findings.

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

### F9 — useful code-level documentation boundary was incompletely materialized

**Decision:** accepted.  
**Resolution:** fixed.

The audit rejected a blanket "docstring every enum/dataclass" rewrite. The applied boundary is:

- architecture-facing component/Machinery classes and public callable contracts require local
  responsibility/semantic documentation;
- non-obvious algorithms require invariant/failure-semantics documentation;
- trivial immutable data carriers and obvious one-line lower delegates may rely on names and
  type contracts.

The first pass documented the upper architecture-facing gaps, including
`AvailabilityManager`, `ProtectiveModeManager`, `AggressiveHostRoutingManager`,
aggressive E.004 build/activation/deactivation operations, `LinuxStructuralPolicyBackend`,
`LinuxCompositeNftBackend`, and host-managed-routing Driver/convergence operations.

The closing bounded pass covered the remaining meaningful lower boundary: fresh-observation
Readers/Drivers, owned-scope mutation Drivers, composed lower Backends, and non-trivial
`observe`/`apply`/`replace`/`cleanup` operations. In particular it documented the
forwarding-gate, nft scaffold/namespace, VPN-path observation, probe routing/execution,
Device firewall, local publication/integration/probe, protective gate, aggressive escape
guard, host publication/routing and stack-return-affinity boundaries.

The pass intentionally did not add comments to self-evident data carriers or trivial
`add/delete` delegation methods.

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

### F11 — superseded per-owner convergence APIs remained after live-evidence migration

**Decision:** accepted.  
**Resolution:** fixed.

The current runtime converges nft policy through the unified structural
`NetworkPolicyEnforcer` / `StructuralPolicyTransaction`. The three obsolete orchestration
entry points have now been removed:

- `converge_device_firewall_step_once()`;
- `converge_payload_nat_step_once()`;
- `converge_composite_nft_step_once()`.

The cleanup retained the real lower technical primitives while removing the duplicate
convergence ownership:

1. `DeviceFirewallPhysicalSnapshot`, `PayloadNatPhysicalSnapshot` and
   `CompositeNftPhysicalSnapshot` moved beside their actual Linux Driver/Backend
   observation implementations;
2. composite nft step dispatch moved into the structural Enforcer implementation boundary;
3. the three superseded orchestration modules, their old unit tests and their dedicated
   Device/NAT integration tests were removed;
4. the two redundant workflow steps were removed while the migrated combined
   Profile + Device firewall + NAT + local-publication structural integration remains;
5. package exports and implementation traceability were cleaned accordingly.

The first workflow publication exposed a YAML line-join introduced while deleting a workflow
step; it was corrected immediately in `3cfeac0dc34966eb3e9e626c3b16532e84f018f9`.
The resulting F11 tree then passed the full NG3 Python workflow
`45130205311`.

After the closing F9 documentation pass, full NG3 Python workflow `45130648285` on head
`f99e2e56948493c1809f7234b282545885bdbd70` completed **SUCCESS, 21/21 jobs**.
This includes `unit`, `linux-payload-nat`, `linux-payload-forward`,
`linux-alpha-smoke`, `linux-debian12-routed-veth` and the migrated structural live
evidence.

## Final implementation review

The final implementation was checked against current requirements, `architecture-ng.md`
and the accepted component model.

- **Requirement semantics:** unchanged. The audit removed implementation debt and did not
  change user-visible policy semantics or requirement status.
- **C.003 ownership:** preserved and clarified. Desired-state convergence, safety barriers,
  strict progress and postcondition verification remain in the structural Enforcer.
- **Lower technical boundary:** Drivers/Readers/Backend compositions only observe or execute
  already-selected technical operations; the deleted per-owner modules no longer duplicate
  convergence ownership.
- **Evidence:** current combined structural integration exercises the surviving path, and the
  final full workflow is green.
- **Scope control:** the branch delta against the pre-audit `main` contains only the audit,
  its tests/evidence/workflow adjustments, traceability update and this review artifact.

No review finding remains open.

## Requirement / architecture impact

No product requirement semantics changed.

The implemented cleanup only removes unreachable/superseded production surfaces, aligns
implementation naming with the already accepted component model, and deduplicates an existing
fail-closed check.

No architecture change is currently required; the removed prototype was not part of current
architecture.

## Current requirement-state inventory

No requirement status is changed by this audit.
