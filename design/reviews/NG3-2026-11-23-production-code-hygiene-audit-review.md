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

The first cleanup slice is implemented through code head
`b40762103dcc6ebb184d3236dc6e6dcfe9373654`. Full CI is still running at the time this
review record is written, so this audit is not yet a completed development block.

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

### F8 — repeated IP port bounds are a real magic-value duplication

**Decision:** accepted.  
**Resolution:** open cleanup finding.

The literal bounds `1..65535` are independently encoded in at least:

- `port_bundle.py`;
- `local_integration_policy.py`;
- `local_publication_policy.py`;
- `host_publication_policy.py`;
- `release1_config.py`;
- `linux_host_publication.py`;
- `linux_device_firewall.py`.

The next cleanup unit should introduce one canonical port-bound definition/validator without
creating reverse dependencies between semantic and Linux-lower modules.

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

### F10 — remaining unused-symbol and one-call-site audit is not yet complete

**Decision:** unresolved within this cycle slice.

Module-level production caller inventory is complete. Symbol-level call-site classification
is only partially complete; therefore this review does not yet claim that every unused
private/public symbol, local constant or single-caller function has been eliminated.

The next CDC should continue from this finding rather than repeating the module inventory.

## Requirement / architecture impact

No product requirement semantics changed.

The implemented cleanup only removes unreachable/superseded production surfaces, aligns
implementation naming with the already accepted component model, and deduplicates an existing
fail-closed check.

No architecture change is currently required; the removed prototype was not part of current
architecture.

## Current requirement-state inventory

No requirement status is changed by this audit.
