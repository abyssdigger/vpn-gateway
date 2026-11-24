# NG3 review — Release-1 scoped peaceful host-routing implementation

**Date:** 2026-11-20  
**Branch:** `ng3-design-cycle-20261120-helper-routing-finalize-30m`  
**Implementation baseline reviewed:** `4b8e14cce729786225460a8eed4346ae43b01a28`  
**Base main snapshot:** `f67322385e6f5ac25bd817067d3dc68d45d443bb` (snapshot 142)  
**Verdict:** **ACCEPTED — DEVELOPMENT BLOCK COMPLETE**

## Scope

Final review of the Release-1 peaceful ordinary-host routing helper after the source-scope
correction, absolute managed-boundary bypass hardening and the review-discovered
preserve-main non-interference defect.

Also revalidates the development-language boundary after the project-holder decision that
host-routing helper implementations may remain Python beyond the first release.

## Requirements

**Implements / closes:**

- `VPNG-U001-R2`;
- `VPNG-U001-R2.R2`.

**Constrained / revalidated by:**

- `VPNG-U007-R7.R8`;
- `VPNG-U007-R7.R8.C1`;
- `VPNG-U007-R7.R8.C2`;
- `VPNG-U007-R7.R8.C3`;
- `VPNG-U007-R7.R8.R3`.

## Accepted configuration contract

```toml
helper_routing_interfaces = ":none"   # default
helper_routing_policy = "peaceful"    # default / only Release-1 value
```

Canonical selector scopes:

- `:none` — no helper contribution;
- `:local` — host-originated traffic;
- `:external` — all non-local ingress;
- `:any` — local + external;
- exact interface names — exact ingress;
- `:local` may be unioned with exact interface names.

The old `host_routing = "auto" | "manual"` surface is no longer current.

The default is deliberately non-invasive. Peaceful helper does not own
`net.ipv4.ip_forward`; external ingress with forwarding disabled is diagnostic-only.

## Final Linux lowering

For every effective selector:

```text
<selector> lookup main suppress_prefixlength 0
<selector> lookup <peaceful-helper-table>
```

The managed HOST↔STACK ingress has a higher-priority absolute jump:

```text
iif <managed-boundary> goto <after-helper>
...
<after-helper>: nop
```

This gives explicit non-default administrator `main` routes precedence **inside selected
scope** without reordering unrelated administrator RPDB policy outside that scope.

Multiple selectors receive deterministic preserve/dispatch pairs. Selector order is not
product policy. Helper routes remain in a dedicated table and ordinary `main` routes are not
rewritten.

## Review findings and dispositions

### F1 — global preserve-main changed unselected host routing

**Finding:** confirmed during this final review.

The earlier implementation scoped helper dispatch but left
`lookup main suppress_prefixlength 0` global. An unselected packet could therefore resolve
an explicit `main` route before a later administrator RPDB rule that normally precedes
ordinary kernel `main`.

**Evidence:** EXP-080 reproduced the interference and proved the selector-scoped correction.

**Disposition:** **fixed** in `4b8e14cce729786225460a8eed4346ae43b01a28`.

### F2 — managed-boundary lookup-main was not an absolute bypass

**Finding:** discovered in the preceding CD.

**Evidence:** EXP-079 proved that `goto <post-helper nop>` skips helper capture even when
ordinary routing has no result.

**Disposition:** **fixed** before this review baseline.

### F3 — helper scope had to fail before dependent network mutation

Exact selection of the managed boundary itself is rejected by pure candidate-policy scope
validation before managed-domain creation/convergence.

**Disposition:** **fixed** in the preceding CD.

### F4 — Rust boundary conflicted with the new helper exception

The former absolute language text would have required every host-side network-state actor to
move to Rust and `R7.R8.R3` unconditionally described Python as reference-only.

**Disposition:** **fixed**. `VPNG-U007-R7.R8.C3` now narrowly permits the host-routing helper
responsibilities under `VPNG-U001-R2.R2` / `R2.R3` to remain Python after the first release
and after non-exempt runtime cutover. Moving the helper itself to Rust requires a separate
explicit project holder decision. The integration mechanism between a future Rust core and a
Python helper is intentionally not invented now.

No compensating user/admin requirement is needed: this constraint transfers no deployment
work to an external product participant.

## Evidence

Selected lower evidence:

- EXP-077 — peaceful lifecycle/main-first/non-destructive cleanup evidence;
- EXP-078 — `:local`, `:external`, `:any`, exact ingress and selector union;
- EXP-079 — absolute managed-boundary no-recapture;
- EXP-080 — old global-preserve counterexample + scoped preserve-main correction.

Current implementation evidence on workflow run `44772969324`:

- compile/unit — PASS;
- `linux-host-managed-routing` — PASS, including EXP-074/078/079/080;
- `linux-alpha-smoke` — PASS on installed Debian 13/systemd alpha with explicit
  `:local` opt-in.

The preceding full baseline run `44762191809` was also SUCCESS before F1 was found; it is
retained only as historical regression evidence, not as proof of the corrected F1 lowering.

## Simplification review

No mark/nft classifier, route-copying into `main`, per-flow state, routing daemon, or
periodic peaceful ownership is needed.

The minimum lower state is:

- one dedicated helper route table;
- one absolute managed-boundary bypass + post-helper exit;
- one preserve+dispatch pair per selected scope;
- helper-owned routes only;
- lifecycle-only convergence/cleanup.

The future aggressive helper remains a separate postponed capability and is not silently
implemented by the peaceful path.

## Requirement-state disposition

- `VPNG-U001-R2.R2` -> [`closed`].
- `VPNG-U007-R7.R8.C3` -> [`closed`].
- `VPNG-U007-R7.R8.R3` -> [`closed`] after revalidation against C3.
- Existing aggressive/containment/reload pending nodes remain unchanged.

No active `unreal`, `broken` or `rejected_closure` relationship is introduced by this
block.

## Final verdict

**ACCEPTED — DEVELOPMENT BLOCK COMPLETE.**

The current tree is suitable for ordinary snapshot publication once the current workflow
state is checked and main lineage remains unchanged.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U007-R7.R8` -> `VPNG-D001-R1.R1.R8`
- `VPNG-U007-R7.R8.C1` -> `VPNG-D001-R1.R1.R8.C1`
- `VPNG-U007-R7.R8.C2` -> `VPNG-D001-R1.R1.R8.C2`
- `VPNG-U007-R7.R8.C3` -> `VPNG-D001-R1.R1.R8.C3`
- `VPNG-U007-R7.R8.R3` -> `VPNG-D001-R1.R1.R8.R3`

The original IDs in the historical body are intentionally preserved.
