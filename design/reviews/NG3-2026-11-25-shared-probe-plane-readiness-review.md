# NG3 shared probe-plane readiness review — 2026-11-25

**Review unit:** C.001 readiness semantics for coexisting A.007 and D.002 probe owners  
**Architecture:** C.001, A.007, C.008, D.002  
**Status:** design clarification; no materialization-status change

## Findings

### F1 — existing subset verification would misclassify legitimate siblings

**Decision:** accepted  
**Resolution:** documented

Both routing and nft comparators inspect the full probe-owned physical scope. Passing only one
semantic owner's desired subset causes accepted sibling physical rows to appear stale.

### F2 — allocation/convergence ownership and readiness ownership are different scopes

**Decision:** accepted  
**Resolution:** documented

Resource allocation and cleanup require the complete current union to avoid collisions and
cross-owner deletion. Whether one consumer may execute a probe is a narrower question and must
be projected for that consumer from fresh state.

### F3 — scoped readiness needs the full accepted union

**Decision:** accepted  
**Resolution:** documented

The verifier needs both full accepted state and requested subset. This permits known sibling
objects, supports physically shared nft rules, and still rejects unattributed owned objects
outside the accepted union.

### F4 — global conflicts remain fail-closed

**Decision:** accepted  
**Resolution:** documented

Owner isolation does not justify ignoring an unknown object in the shared reserved probe
namespace. If an observed owned object cannot be attributed to the accepted union, readiness
must not manufacture success.

## Verdict

**PASS for design boundary.** The next code unit is owner-aware scoped probe comparison/readiness.
Combined alpha assembly and D.002 runtime wiring should follow only after that unit is proven.
