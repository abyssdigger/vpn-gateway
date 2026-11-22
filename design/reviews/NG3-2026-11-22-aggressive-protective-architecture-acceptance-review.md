# NG3 2026-11-22 — aggressive/protective architecture acceptance review

**Scope:** review the materialized aggressive host-routing and administrative protective-mode
architecture after simplification of the aggressive candidate and source-scoped protective
request refinement.

**Requirements:** `VPNG-U001-R5.R2*`, `VPNG-U004-R5*`  
**Architecture:** `design/NG3/architecture-ng.md`  
**Evidence:** EXP-074 (narrow routing mechanics), EXP-081, EXP-083, EXP-084  
**Baseline reviewed:** `73c4c80be31a075e66d9f5bfdaa2620db54cb802`

## Verdict

**PASS — THE MATERIALIZED ARCHITECTURE IS SUFFICIENT CLOSURE FOR ALL 11 PENDING NODES.**

Implementation is not part of this architecture-closure verdict. Production code remains a
separate development block and must trace to the accepted component specs.

## Findings and dispositions

### F1 — component placement and nesting are minimal and model-compliant

**Decision:** accepted.  
**Resolution:** fixed.

The current decomposition is:

- A.011 `ProtectiveModeManager` — top-level STACK Manager because operator/automation and
  E.003 are independent external clients of its public semantic state;
- C.010 `ProtectivePayloadGate` — top-level Private-network Enforcer because A.011 is an
  external Space client;
- E.003 `AggressiveHostRoutingManager` — top-level managed-host Manager because STACK
  lifecycle/runtime policy assembly is an external client;
- E.004 `AggressiveHostRoutingEnforcer` — child of E.003 because no independent external
  client or lifecycle justifies a separate top-level API.

The EXP-084 escape guard remains an independently verifiable owned Artifact inside E.004,
not a separate component. This follows the component model's explicit rule that one Enforcer
may compose several lower mechanisms when no useful reusable/API boundary exists.

### F2 — aggressive semantic ownership is separated from Linux failure taxonomy

**Decision:** accepted.  
**Resolution:** fixed.

E.003 owns the effective authoritative-delivery guarantee and finite-cadence confirmation.
It does not enumerate every foreign RPDB/routing mechanism capable of violating that
guarantee.

E.004 owns bounded fresh observation/convergence/verification. EXP-081 requires its Linux
realization to prove the effective postcondition rather than only exact VPN-GATE-owned
table/rule objects; the concrete verification mechanism remains a lower implementation
decision.

This closes `VPNG-U001-R5.R2.R1` and `.R2` without requiring a generic administrator
routing-policy analyzer.

### F3 — aggressive transition and failure ordering are fail-closed

**Decision:** accepted.  
**Resolution:** fixed.

E.004 active convergence establishes and verifies escape protection before enabling routing
capture. Inactive convergence removes and verifies routing capture before releasing escape
protection.

EXP-084 demonstrates the essential safety property: a competing earlier RPDB rule can make
the routing decision wrong, but the independent guard prevents managed traffic from escaping
through an ordinary egress during the detection/recovery interval.

If the effective postcondition cannot be restored or confirmed, E.003 retains local
containment and escalates to A.011.

This is sufficient closure for `VPNG-U001-R5.R2.R3` and `.R3.R1`.

### F4 — protective requests must be source-scoped

**Decision:** accepted.  
**Resolution:** fixed.

Operator/automation and E.003 are independent request sources. A global boolean request API
would allow one source to clear protection still required by another.

A.011 therefore owns a source-scoped request set:

- each source may add/update only its own active request;
- each source may clear only its own request;
- C.010 may be disabled only when the request set is empty and the normal release
  precondition is confirmed.

E.003 clears only its own protective request after confirmed aggressive recovery or explicit
aggressive disable. This closes the escalation composition without adding a synchronous
A.011 -> E.003 back-edge.

### F5 — protective lower containment has one coherent owner

**Decision:** accepted.  
**Resolution:** fixed.

C.010 owns one dedicated protective containment Artifact in Private network. EXP-083 proves
the selected Linux lower shape can block:

- ordinary-boundary IPv4 INPUT;
- ordinary-boundary IPv4 OUTPUT;
- all IPv4 FORWARD;

while preserving namespace, interfaces, routes and normal policy state.

The earlier two-barrier EXP-082 shape remains valid feasibility evidence but is not selected.
C.005 `ForwardingGate` retains only its structural-transition responsibility.

This is sufficient closure for `VPNG-U004-R5.R2` and supports the state-preservation
obligation in `.R3`.

### F6 — protective entry, continuous confirmation and leave are explicit

**Decision:** accepted.  
**Resolution:** fixed.

A.011 does not equate command acceptance with protection. Entry succeeds only after C.010 is
freshly confirmed.

While any request source remains active, A.011 periodically starts from fresh observation and
restores C.010 when safe. Lower events may accelerate observation but are not authoritative
truth.

When the final source clears its request, A.011 keeps C.010 active while confirming the
applicable normal release precondition. Failed validation or failed gate removal leaves the
gate active and returns a problem result.

Therefore the architecture closes `VPNG-U004-R5.R1` and `.R4` without relying on
destructive teardown.

### F7 — no unresolved architecture decision remains on the reviewed statements

**Decision:** accepted.

The reviewed requirements are all decomposition-complete. Their remaining work is
implementation and implementation evidence, not a missing architecture choice.

The requirement model explicitly permits `closed` architecture status before implementation
when the accepted component responsibilities, interactions, safety ordering and selected
technical mechanisms are sufficient to explain how the obligation will be realized.

## Status disposition

Move these nodes from `pending_closure` to `closed`:

- `VPNG-U001-R5.R2`;
- `VPNG-U001-R5.R2.R1`;
- `VPNG-U001-R5.R2.R2`;
- `VPNG-U001-R5.R2.R3`;
- `VPNG-U001-R5.R2.R3.R1`;
- `VPNG-U001-R5.R2.R3.R2`;
- `VPNG-U004-R5`;
- `VPNG-U004-R5.R1`;
- `VPNG-U004-R5.R2`;
- `VPNG-U004-R5.R3`;
- `VPNG-U004-R5.R4`.

Release-1 constraints remain unchanged and do not become implementation obligations merely
because the architecture is now closed.
