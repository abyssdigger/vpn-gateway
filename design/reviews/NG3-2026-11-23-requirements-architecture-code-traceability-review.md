# NG3 2026-11-23 — requirements / architecture / code traceability re-check

**Status:** review complete; corrective changes intentionally deferred for owner discussion  
**CDC branch:** `ng3-consistency-traceability-cdc-20261123`  
**Reviewed base:** `26309686ba9b82807496e4799c682c622731fc64`  
**CDC clock:** 2026-11-23 10:56:22 +03

## Scope

Re-check the current NG3 consistency chain in both directions:

1. normative requirements -> accepted architecture;
2. architecture -> production Python implementation;
3. production Python -> architecture -> normative requirements;
4. component-model ownership at suspicious shared lower boundaries;
5. mechanical enforcement of the trace invariants.

No requirement, architecture or implementation correction is applied in this review unit.
Findings are recorded first so the owner can decide the correction scope.

## Baseline PASS facts

### P1 — requirement tree integrity

Current normative inventory contains 214 nodes:

- 203 `closed`;
- 8 `postponed`;
- 3 `permanent`;
- zero `open`, `pending_closure`, `rejected_closure` or statusless nodes.

There are no duplicate requirement IDs and no orphan hierarchical IDs.

The postponed developer-trace branch is recorded in
`design/deferrals/NG3-developer-execution-trace.md`. The postponed resource-suitability
branch is recorded in
`design/deferrals/NG3-raspberry-pi2-resource-envelope.md`; that record explicitly excludes
permanent engineering preference `VPNG-M001-R3.R1` from the postponed scope.

### P2 — closed requirements and architecture references are an exact set match

The structured architecture contains 203 distinct normative requirement references. That set
is exactly the current set of 203 `closed` requirements:

- closed requirement absent from architecture: **0**;
- architecture reference to a non-existent requirement: **0**;
- architecture reference to a postponed/permanent node as if closed: **0**.

The 11 normative nodes not referenced by architecture are exactly the 8 postponed and
3 permanent nodes. This is consistent with the requirement-state model.

### P3 — production-file manifest is exhaustive at file level

Current production package inventory under `design/NG3/code/python/rou/*.py` is 112 files.

`design/NG3/implementation-traceability.md` contains exactly 112 unique file entries:

- untraced production files: **0**;
- duplicate production-file entries: **0**;
- trace entries pointing at absent production files: **0**.

111 semantic units resolve to one or more requirement-bearing component specs.
`rou/__init__.py` is the sole explicit architecture-debt entry and has the existing
packaging-facade reason.

### P4 — the current two-hop code-to-requirement model is semantically sound

For every non-debt production unit the current normative path is:

```text
production file
    -> implementation-traceability component ID(s)
    -> component Implements / Supports implementation of / Constrained by
    -> normative requirement IDs
```

Flattening the current manifest through component requirement ownership gives:

- semantic production units with zero requirement path: **0**;
- semantic production units touching postponed requirements: **0**;
- semantic production units touching any non-closed requirement through normal implementation
  trace: **0**.

This is preferable to storing a second normative file->requirement list, which would duplicate
the component spec as source of truth. A generated/check-only resolved file->requirement view
is safe and useful; a second hand-maintained normative mapping is not.

### P5 — component-local reverse markers are intact

The architecture currently has 26 component-local `Implementation` edges across 17 unique
Python units. Every such unit exists, contains an `Architecture:` marker, and names the
component ID for which the architecture explicitly lists it.

### P6 — no obvious unimplemented-code placeholder was found

The production package contains no `TODO`, `FIXME` or `NotImplementedError`.
The remaining bare `pass` occurrences are exception class bodies, not missing behavior.

The inherited implementation baseline was already green in NG3 Python workflow
`45130648285` (**21/21 jobs SUCCESS**) before this review-only CDC branch was created.

## Findings

### F1 — the full implementation manifest drops seven component-local implementation edges

**Decision:** accepted finding.  
**Resolution:** deferred until owner discussion; no trace mutation in this review unit.

The architecture declares these concrete implementation edges and the corresponding files
already carry the matching reverse `Architecture:` markers, but the authoritative full
manifest does not include the component on that file's trace entry:

- `B.001 -> controller_startup.py`;
- `B.001 -> controller_stop.py`;
- `C.007 -> controller_startup.py`;
- `C.007 -> controller_stop.py`;
- `C.009 -> controller_startup.py`;
- `C.009 -> controller_stop.py`;
- `E.001 -> alpha_runtime.py`.

Example: `alpha_runtime.py` is explicitly listed by both A.001 and E.001 and its module
marker names both, while the full manifest currently maps it only to A.001.

This does not create an untraced file, so the existing "112/112 files present" test cannot
detect it. It is nevertheless a real loss in the exhaustive code-to-architecture edge.

**Recommended correction:** expand the affected manifest headings/entries to include the
already-declared component edges; do not duplicate files as separate manifest rows.

### F2 — C.010 is physically located under Annex D although its ID and Space are C

**Decision:** accepted finding.  
**Resolution:** deferred until owner discussion.

The architecture's own placement rule says the Annex letter belongs to the Space and component
specs are placed in that Annex. Current document order is:

```text
# Annex D. VPN external ends components
... states that Annex D has no VPN-GATE component specs ...

## C.010 ProtectivePayloadGate
```

C.010 is consistently referenced elsewhere as
`Private network.@ProtectivePayloadGate`. Therefore the heading is structurally misplaced,
not semantically an Annex-D component.

**Recommended correction:** move the complete C.010 spec immediately before Annex D; no
component ID or requirement mapping change is needed.

### F3 — the §2.9 Annex-C example is stale

**Decision:** accepted finding.  
**Resolution:** deferred until owner discussion.

The methodology example currently shows:

```text
## C.001 NetworkPolicyAdapter
## C.002 NetworkPolicyEnforcer
```

The canonical specs are C.001 `NetworkPolicyAdapter`, C.002
`NetworkPolicyLayoutCalculator`, and C.003 `NetworkPolicyEnforcer`.

This is explanatory prose, not the canonical spec, but it contradicts the same document.

**Recommended correction:** update the example to the current IDs/names.

### F4 — shared host-routing implementation is under-traced for E.004 and retains stale postponed wording

**Decision:** accepted trace/documentation finding; no component-model violation proven.  
**Resolution:** final edge set deferred until owner discussion.

Current E.004 implementation directly consumes the shared host-routing lower layer:

- `host_managed_routing.py`;
- `linux_host_managed_routing.py`;
- `linux_host_managed_routing_backend.py`.

Those units are currently traced only to E.002 even though
`aggressive_host_routing_enforcer.py` imports and uses their plan, Linux desired/allocation,
Driver and convergence/cleanup functions.

The strongest mismatch is `release1_host_boundary.py`: its own module text says it is an
aggressive-host-routing evidence path, while the current manifest traces it to E.002
peaceful `HostRoutingContribution`.

Several current production docstrings also still call the aggressive helper `postponed`.
That wording predates the explicit re-entry and current E.003/E.004 architecture.

The earlier lower-boundary review is still useful here: it explicitly classified
`LinuxHostManagedRoutingDriver` as a Driver and required convergence to remain outside the
Driver object. Current code satisfies that class boundary. The free
`converge_host_managed_routing_once()` helper performs technical owner-state convergence and
is reused by the peaceful E.002 lifecycle and the composite E.004 Enforcer. Nothing found in
this re-check proves that this helper must become a new architecture component.

**Recommended correction:** treat the shared lower files as multi-target implementation where
they genuinely serve both E.002 and E.004, move the explicitly aggressive
`release1_host_boundary.py` trace away from E.002 to its current aggressive/evidence owner,
and remove obsolete `postponed` wording. Re-check the exact file set before editing rather
than blindly adding E.004 to every E.002 file.

### F5 — current mechanical tests cannot detect F1/F2 and do not materialize the resolved code->requirement view

**Decision:** accepted finding.  
**Resolution:** deferred until owner discussion.

`test_architecture_traceability.py` correctly enforces file presence, requirement statuses,
closed requirement architecture coverage, reverse markers for locally declared implementation
files, valid component targets, partial-component declarations and postponement records.

It does not currently enforce:

1. every component-local `Implementation` edge is contained in the full manifest;
2. component Annex placement agrees with its stable ID letter;
3. every normal manifest edge resolves through the target component to valid current
   requirement IDs/statuses;
4. a mechanically inspectable resolved `file -> component(s) -> requirement IDs` view.

F1 survived specifically because the test checks that a locally declared file has a reverse
marker, not that the same component edge exists in the full manifest.

**Recommended correction:** add invariant tests for (1)–(3). For (4), prefer a generated or
test diagnostic view over another hand-maintained normative artifact.

## Non-findings / boundaries

### N1 — closed requirements do not imply complete code implementation

The requirement model defines `closed` as accepted architecture closure, not "all code is
implemented". Therefore the explicit A.011 `<partial>` implementation status is not a
requirements-state contradiction. It remains a visible implementation frontier: periodic
protective-mode scheduling and supported operator/control wiring are not yet materialized.

This review does not claim that every accepted requirement has complete production code merely
because every production file has a requirement path.

### N2 — permanent resource preference is not missing closure

`VPNG-M001-R3.R1` is `permanent`, not `closed`, and therefore correctly has no required
exact architecture closure edge. Its deferral record explicitly keeps it active. No current
architecture/code decision found in this review contradicts its preference against unnecessary
CPU/memory/allocation/per-flow bookkeeping.

### N3 — a direct normative file->requirement table would be the wrong repair

The architecture explicitly assigns normative requirement ownership to component specs.
Duplicating those IDs beside every implementation file would create two manually maintained
sources of truth.

The useful strengthening is mechanical composition of the existing two-hop relation plus
tests that prove the relation is complete.

## Review verdict

**CONSISTENT CORE WITH CORRECTABLE TRACE/DOCUMENTATION GAPS.**

The strongest invariants are healthy:

- normative requirement tree is internally well-formed;
- the 203 closed requirements are exactly the 203 architecture-referenced requirements;
- all 112 production Python files are represented exactly once in the implementation
  manifest/debt inventory;
- every semantic production file resolves to closed requirement-bearing architecture.

The review nevertheless found real defects that the current tests allow:

1. seven component-local implementation edges are missing from the full manifest;
2. C.010 is physically under the wrong Annex;
3. the Annex-C example has stale C.002 naming;
4. the shared/aggressive host-routing implementation trace and wording still contain
   pre-re-entry assumptions;
5. traceability tests need stronger edge-level and resolved-path invariants.

No corrective architecture/code change has been made yet. The next CDC step should be chosen
after owner discussion of these findings.
