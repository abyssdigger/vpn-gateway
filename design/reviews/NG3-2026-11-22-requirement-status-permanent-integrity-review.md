# NG3 2026-11-22 — requirement-status and permanent-conformance integrity review

**Scope:** review the mandatory requirement-status model, synchronize current terminology,
validate all NG3 Requirement/Constraint statuses and establish current-architecture conformance
for the newly introduced `permanent` status.

**Reviewed branch:** `ng3-requirement-status-permanent-20261122`  
**Reviewed implementation head:** `329a0e38ce48fa633692f429ce0346e6a14483a6`  
**Authoritative requirements:** `design/NG3/requirements.md`  
**Authoritative architecture:** `design/NG3/architecture-ng.md`  
**Requirement model:** `design/requirements-model.md`

## Findings and dispositions

### F1 — requirement status is now the single mandatory state enum

**Decision:** accepted.  
**Resolution:** fixed.

The model now requires every normative Requirement/Constraint to have exactly one of:

```text
open | pending_closure | closed | rejected_closure | postponed | permanent
```

`open` is explicit rather than represented by absence of a label. It means that the accepted
node remains in the active frontier but has no sufficient closure candidate yet. This preserves
a valid state for newly accepted requirements while making missing status mechanically
detectable.

The enum remains independent from `decomposition: complete|incomplete`. `permanent` remains
non-inherited and is not a closure state.

### F2 — transition semantics remain total after making status mandatory

**Decision:** accepted.  
**Resolution:** fixed.

The previous model could remove a status after semantic change or leave a re-entered postponed
node without a representable active state. The revised rules send such nodes to `open` when
no concrete closure candidate exists, or to `pending_closure` when one does.

A rejected candidate may likewise be explicitly abandoned into `open`; a replacement
candidate uses `pending_closure`; a deliberate frontier exclusion uses `postponed`.

No intermediate Git commit is required merely to represent `open` or `pending_closure`
when creation/candidate/acceptance occur in one review unit.

### F3 — current NG3 status inventory is complete and mutually exclusive

**Decision:** accepted.  
**Resolution:** fixed.

Mechanical parsing of the current normative tree finds 207 unique normative nodes and exactly
one status on every node:

- 190 `closed`;
- 14 `postponed`;
- 3 `permanent`;
- 0 `open`;
- 0 `pending_closure`;
- 0 `rejected_closure`;
- 0 statusless nodes;
- 0 nodes with multiple status labels.

There are no active `decomp`, `unreal` or `broken` links that conflict with these states.

### F4 — all current closure references remain valid

**Decision:** accepted.  
**Resolution:** fixed.

All 190 current `closed` nodes have an exact current backtick ID reference in
`design/NG3/architecture-ng.md`. Every requirement ID referenced by that architecture resolves
to a current normative node. The status-model changes therefore do not invalidate any accepted
closure.

The project-level guard is aligned with the generic model: a future `closed` node may also
use the model's aggregate closure rule when it is decomposition-complete, has immediate
normative children and every immediate child is `closed`.

### F5 — every postponed node has an explicit postponement basis

**Decision:** accepted.  
**Resolution:** fixed.

All 14 `postponed` nodes have current review/deferral records:

- per-path Device firewall/configuration: Release-1 constraint-backed review plus
  `design/deferrals/NG3-user-facing-policy-grammar.md`;
- aggressive host-routing helper and administrative protective mode:
  `design/reviews/NG3-2026-11-22-postponed-status-constraint-review.md`;
- developer execution trace:
  `design/deferrals/NG3-developer-execution-trace.md`;
- weak-device/Raspberry Pi 2 resource suitability:
  `design/deferrals/NG3-raspberry-pi2-resource-envelope.md`.

The resource deferral now explicitly covers parent `VPNG-M001-R3` while excluding
`VPNG-M001-R3.R1` from the postponed scope.

### F6 — the three permanent classifications are semantically appropriate

**Decision:** accepted.  
**Resolution:** fixed.

The permanent nodes are:

- `VPNG-D001` — project-wide development/change/maintenance cost discipline;
- `VPNG-M001` — project-wide administration/diagnosis/operation cost discipline;
- `VPNG-M001-R3.R1` — prefer lower steady-state CPU, memory, allocation and state-tracking
  cost among behaviorally equivalent solutions.

None can be finitely closed without losing its intended future applicability. Their status is
therefore correctly `permanent`, and it does not propagate to parents or descendants.

Current architecture is conformant for the reviewed baseline:

- development-cost conformance is supported by explicit component/boundary decomposition,
  traceability and the architecture rule against unrequired generic mechanisms;
- operational-cost conformance is supported by the accepted lifecycle, current-status,
  operational-logging and administrator-boundary decisions while mandatory safety semantics
  remain independently enforced;
- resource-efficiency conformance is supported by bounded/current-only state, absence of
  generic event/replay machinery and hidden retry queues where not required, change-driven
  status publication, and explicit avoidance of unnecessary generic lower mechanisms.

This is a conformance finding, not architecture closure. Future applicable architecture changes
must be checked again against these permanent statements.

### F7 — the mandatory status rules are executable guards

**Decision:** accepted.  
**Resolution:** fixed.

`test_architecture_traceability.py` now checks:

- exactly one recognized requirement status on every normative node;
- exact structured-architecture references for `pending_closure`;
- direct or model-valid aggregate closure for `closed`;
- explicit review/deferral records for `postponed`;
- explicit review/deferral records for `rejected_closure` when such nodes exist.

The `unit` job of NG3 Python run `45035632600` passed on the reviewed test head.

## Terminology integrity

Current normative/process documents use **requirement status** rather than the retired
`closure/frontier status` / optional `closure label` terminology. Historical review and
research artifacts retain their original wording and are not rewritten retroactively.

## Verdict

**PASS — the mandatory requirement-status model, the current 207-node status inventory,
postponement evidence, closure traceability and current conformance of all three permanent
requirements are internally consistent.**
