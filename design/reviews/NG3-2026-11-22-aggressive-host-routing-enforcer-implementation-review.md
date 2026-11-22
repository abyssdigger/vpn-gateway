# NG3 2026-11-22 — E.004 aggressive host-routing Enforcer implementation review

**Scope:** production implementation of accepted E.004 `AggressiveHostRoutingEnforcer`.

**Baseline:** main `2f72034f9feeefabceaffe2133cfa3b021ca6f2e`  
**Reviewed implementation head:** `9a7aa252fab4d49c8fbee2f80a25319ccb1dfbb3`

## Verdict

**PASS — E.004 IS MATERIALIZED AND ITS `<partial>` MARKER IS CORRECTLY REMOVED.**

## Findings and dispositions

### F1 — composite activation ordering is fail-closed

**Decision:** accepted.  
**Resolution:** fixed.

Production activation establishes and freshly confirms the independently owned escape guard
before mutating aggressive routing. Routing convergence then reuses the strict existing
host-managed-routing owner. Final success requires a new owner observation, a new RPDB
authority observation and an exact guard observation.

A routing or authority failure therefore leaves the guard in place instead of rolling back
into an ordinary-path leak.

### F2 — authority verification closes the EXP-081 blind spot

**Decision:** accepted.  
**Resolution:** fixed.

The production authority verifier no longer treats exact VPN-GATE-owned RPDB/table state as
sufficient. Before the aggressive dispatch priority it permits only:

- the canonical kernel local-delivery rule;
- the exact VPN-GATE managed-boundary bypass.

Any other rule able to execute before aggressive dispatch makes authority unconfirmed. The
verifier does not delete or rewrite that foreign state; E.004 fails closed through the
independent guard.

The live integration inserts the EXP-081-style earlier `lookup main` rule and confirms:

- E.004 no longer reports active success;
- local containment remains confirmed;
- host-originated and forwarded managed traffic cannot escape via the ordinary uplink.

### F3 — full-tunnel guard preserves the EXP-085 exemptions

**Decision:** accepted.  
**Resolution:** fixed.

The production guard is a dedicated owner-marked nft table. For `0.0.0.0/0` it does not
materialize a meaningless destination predicate; it applies the egress guard directly while
retaining explicit exemptions for:

- host-local delivery;
- traffic arriving from the exact managed boundary toward the ordinary network.

Its observer classifies absent, exact, owned drift and ownership conflict, and mutations are
limited to absent or proven-owned state.

### F4 — deactivation ordering is safe under partial state

**Decision:** accepted.  
**Resolution:** fixed.

Deactivation first restores/reconfirms the guard, then removes and verifies routing capture,
and only then removes the guard. If routing cleanup fails, containment remains active. The
live integration confirms that successful deactivation restores the ordinary path only after
the aggressive routing owner is gone.

### F5 — implementation trace is complete

**Decision:** accepted.  
**Resolution:** fixed.

The three production units trace only to E.004:

- `aggressive_host_routing_enforcer.py`;
- `linux_aggressive_escape_guard.py`;
- `linux_aggressive_routing_authority.py`.

E.004 now contains its concrete `Implementation` block and the Residents occurrence is no
longer marked `<partial>`.

## Evidence

NG3 Python workflow `45053892114` on the reviewed implementation lineage:

- compile/unit and architecture traceability: PASS;
- EXP-074: PASS;
- EXP-081: PASS;
- EXP-084: PASS;
- EXP-085: PASS;
- production E.004 integration: PASS;
- peaceful EXP-078/079/080 regressions: PASS.

The first two live attempts exposed integration-fixture omissions (per-interface
`rp_filter` and the host-boundary return route) relative to EXP-085. Those omissions were
fixed in the fixture; no E.004 product semantics were weakened to make the test pass.
