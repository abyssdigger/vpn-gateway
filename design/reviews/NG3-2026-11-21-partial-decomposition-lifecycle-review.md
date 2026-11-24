# NG3 review — partial-component decomposition, lifecycle and implementation tracing

**Date:** 2026-11-21  
**Branch:** `ng3-partial-decomposition-lifecycle-cd`  
**Base main snapshot:** `c4188de692f0d2123ea034cfe506798577dc2890` (snapshot 150)  
**Implementation baseline reviewed:** `b35095144ceffa74265ce3b2e34a1680546903f2`  
**Evidence:** GitHub Actions `NG3 Python` run `44932489415`  
**Verdict:** **ACCEPTED — DEVELOPMENT BLOCK COMPLETE**

## Scope

This block tested the structured-architecture method against two previously explicit
`<partial>` findings rather than merely renaming them:

1. the combined managed-network-domain lifecycle crossing `Private network` and
   `Ordinary-side transition`;
2. the host-publication occurrence of `NetworkPolicyAdapter` crossing from
   `Private network` into `VPN-GATE-managed host state`.

The block carried the resulting decisions through canonical architecture, structured
architecture, Python reference implementation, unit/integration evidence and a mechanically
checkable implementation-trace convention.

No new product capability is introduced. The work changes decomposition, lifecycle ownership,
recovery semantics for already-owned lower state, and architecture-to-code traceability.

## Requirement boundary

The decomposition is driven by the existing requirement tree, chiefly:

- `VPNG-U004-R4.R6` — host-state/non-interference safety boundary;
- `VPNG-U005-R5.R1`, `R5.R2`, `R5.R4`, `R5.R5` — bounded lifecycle, observation,
  cleanup and independent cleanup-domain behavior;
- `VPNG-U001-R1.R3.R6.R1` and `VPNG-U001-R4.R4.R6.R3` — Device server publication;
- `VPNG-U007-R7.R3`, `R7.R3.R3`, `R7.R7` — localized architecture, traceability and
  implementation/evidence discipline.

Historical managed-domain mechanism-specific requirement IDs are not revived. The current
mechanism-neutral requirement tree remains authoritative.

## Accepted decomposition

### F1 — combined managed-domain lifecycle crossed Space ownership

**Finding:** confirmed.

The former `ManagedNetworkDomainLifecycle <partial>` owned one technical transaction spanning
three different architectural postconditions.

**Resolution:** accepted decomposition:

```text
Private network
    ManagedNetworkEnvironmentLifecycle
        namespace + loopback

Ordinary-side transition
    ManagedL3BoundaryLifecycle
        reciprocal boundary endpoints
        routed-veth / backend invariants
        host-side service reachability contribution

Private network
    OrdinarySidePortalLifecycle
        stack-local IPv4 identity
        ordinary-side default routing state
```

The three lifecycles are dependency-ordered but independently observable and cleanable.
Physical location of the veth endpoints does not define ownership.

**Disposition:** **RESOLVED.**

### F2 — valid lifecycle state was previously rejected as "partial"

**Finding:** confirmed.

An exact Private-network environment without the ordinary-side transition was previously
classified together with unsafe partial Linux realization.

**Resolution:** an exact environment with absent transition is now a valid recoverable state.
The controller can establish the missing transition and then converge the portal. By contrast,
an orphan host-side boundary endpoint without the managed environment remains a conflict:
name presence alone does not prove ownership.

**Evidence:** final privileged integration reports
`MANAGED_ENVIRONMENT_WITHOUT_TRANSITION_RECOVERED=PASS`.

**Disposition:** **RESOLVED.**

### F3 — portal drift was coupled to whole-domain refusal

**Finding:** confirmed.

The stack-local service address and ordinary-side default route are independently owned
Private-network state and do not require reconstruction of the transition.

**Resolution:** `OrdinarySidePortalLifecycle` may converge its exact address/default state
after the transition itself is verified exact and forwarding is protectively contained.

**Evidence:** `MANAGED_DOMAIN_PORTAL_DRIFT_REPAIRED_FAIL_CLOSED=PASS`.

**Disposition:** **RESOLVED.**

### F4 — cleanup needed independent attempts and stronger terminal postconditions

**Finding:** confirmed.

A single combined destroy path obscured which cleanup domain failed and made it difficult to
state when a later stronger postcondition supersedes an earlier lower diagnostic.

**Resolution:** normal cleanup now attempts, in dependency-reverse order:

```text
host-side lifecycle contributions/exposure
    ->
ordinary-side portal
    ->
ordinary-side transition
    ->
Private-network environment
```

One cleanup-area failure does not suppress later independent attempts. If the managed
environment is subsequently proven absent, an earlier portal/transition cleanup exception is
retained as `cleanup_diagnostic` but no longer prevents the stronger terminal absence
postcondition from succeeding. Independent host-routing cleanup failure remains material.

**Disposition:** **RESOLVED.**

### F5 — host publication was not a Private-network Adapter occurrence

**Finding:** confirmed.

The lower implementation already had a distinct host owner/backend, while structured
architecture described it as `NetworkPolicyAdapter <partial>`.

**Resolution:** `HostPublicationAdapter` is now a separate Adapter in
`VPN-GATE-managed host state`. `NetworkPolicyAdapter` remains confined to
`Private network`.

One Device publication intent still requires two ordered postconditions:

```text
managed local admission exact
    ->
host publication mapping exact
```

Removal reverses exposure first. No additional Manager or Agent was introduced.

**Disposition:** **RESOLVED.**

## Implementation review

### Lifecycle composition

The Python reference now exposes separate lifecycle functions for environment, transition and
portal. `controller_startup.py` calls those contracts independently and inserts stop
checkpoints between lifecycle stages. `controller_stop.py` invokes the reverse cleanup
domains independently.

The old `ensure/preflight/destroy_managed_network_domain` functions remain only as a
compatibility orchestration façade for retained tests/experiments and are no longer the
runtime ProductLifecycleControl boundary.

**Decision:** accepted.

### Host-publication boundary

`host_publication_adapter.py` now owns the semantic observe/apply/cleanup boundary.
`alpha_runtime.py` no longer calls the Linux host-publication convergence primitive directly.

**Decision:** accepted.

### Product-readiness composition

The review found an important naming/composition boundary:

- `start_controller_once()` may return its lower `ControllerStartupStatus.READY` after
  managed-domain/lower-policy activation;
- the current Release-1 product does not publish systemd `READY=1` until availability startup
  and `HostPublicationAdapter` have also reached their required postconditions.

This is safe in the current alpha because product READY is published only by the outer
`alpha_runtime.py` composition. It does mean the inner status name is stronger than the
subassembly actually promises.

**Decision:** accepted for the current implementation, retained as a discussion topic rather
than hidden by documentation.

## Implementation traceability experiment

The structured method now defines the following minimum reverse trace:

```text
code
    -> Architecture: Annex X.YYY
    -> component spec
    -> Implements / Constrained by
    -> requirement
```

and the opposite direction:

```text
requirement
    -> component spec
    -> Implementation block
    -> code
```

Normative requirement trace remains in the component spec. Requirement IDs inside code comments
are optional convenience and are not a second authoritative mapping.

A generic unit test now parses every Python path declared by structured
`Implementation` blocks and verifies that:

1. the file exists;
2. it contains an `Architecture:` marker;
3. the marker points back to the declaring component spec ID.

This supports one implementation file serving several explicit component occurrences without
making directory layout or import topology an implicit architecture.

**Decision:** accepted as the first mechanically enforced traceability layer.

## Evidence

Final run `44932489415` on implementation baseline `b35095144ceffa74265ce3b2e34a1680546903f2`
completed **SUCCESS**.

Relevant evidence includes:

- unit suite — **786 tests, PASS**, including lifecycle decomposition,
  `HostPublicationAdapter` and generic architecture-trace tests;
- managed-domain lifecycle integration — **PASS**;
- bounded controller startup integration — **PASS**;
- `MANAGED_DOMAIN_PORTAL_DRIFT_REPAIRED_FAIL_CLOSED=PASS`;
- `MANAGED_ENVIRONMENT_WITHOUT_TRANSITION_RECOVERED=PASS`;
- installed Debian-13 alpha smoke — **PASS**;
- host-publication DNAT integration — **PASS**;
- OpenVPN/systemd applicability/lifecycle — **PASS**;
- Debian-12 routed-veth portability — **PASS**;
- the remaining NG3 Python privileged matrix — **PASS**.

The earlier failing run exposed stale test seams and one misleading compatibility
`created` flag; both were corrected before this reviewed baseline.

## Deliberate compatibility boundary

The compatibility `ManagedNetworkDomain*Result` façade still compresses richer lifecycle
states. Its `existing: bool` can mean either completely absent or a recoverable incomplete
composition, although `created` now means actual environment/boundary creation rather than
portal repair.

The production controller no longer depends on this compressed state model.

**Decision:** acceptable compatibility debt; do not expand new runtime design around it.

## Topics for discussion

1. **What should `READY` mean at each layer?**  
   Rename the inner controller result to an activation/subassembly term, or move host
   publication/other required outer readiness into one ProductLifecycleControl contract?

2. **Should the compatibility managed-domain façade be retired?**  
   A richer `ABSENT / EXACT / RECOVERABLE / CONFLICT` projection is more truthful than the
   legacy `existing: bool`, but may be unnecessary if only retained experiments still use it.

3. **How far should lifecycle repair authority extend?**  
   Portal state now converges because ownership is exact. Environment and transition still use
   create-or-exact semantics for existing state. Decide whether owned loopback/sysctl/route/link
   drift should be repaired or continue to fail closed.

4. **How narrow is portal ownership long term?**  
   Current portal convergence owns the exact IPv4 set and ordinary-side default on a dedicated
   endpoint. If future local identities/routes coexist there, the current flush-based lowering
   must become more granular.

5. **Must component decomposition become module decomposition?**  
   `managed_network_domain.py` currently implements B.001, C.007 and C.009 with explicit
   reverse markers. Decide whether this is sufficient or whether independent lifecycle modules
   would improve review/change containment.

6. **Does `HostPublicationAdapter` need a backend Protocol now?**  
   The semantic boundary is independent, but its field currently names the Linux backend
   concretely. This is not a Release-1 correctness problem; it is a portability/testability
   design choice.

7. **How far should mechanical traceability be rolled out?**  
   The new test covers every Python file explicitly declared in structured `Implementation`
   blocks. It does not yet prove that every production module is declared by some component.
   Decide whether CI should eventually require complete production-code coverage.

8. **Where should evidence links live?**  
   Stable architecture should not embed ephemeral workflow run IDs. Reviews currently provide
   the natural `architecture/code -> evidence run` layer; decide whether a separate durable
   evidence index is useful.

## Final verdict

**ACCEPTED — DEVELOPMENT BLOCK COMPLETE.**

Both original `<partial>` findings are resolved by actual ownership boundaries, the
lifecycle behavior is implemented and exercised end-to-end, and the first mechanically
enforced architecture-to-code trace is in place. The remaining items above are explicit
design questions, not hidden blockers to this block.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005-R5.R1` -> `VPNG-M001-R1.R1.R1`
- `VPNG-U007-R7.R3` -> `VPNG-D001-R1.R1.R3`

The original IDs in the historical body are intentionally preserved.
