# NG3 combined probe-plane desired composition review — 2026-11-25

**Review unit:** C.001 pure full-union desired composition for A.007 + D.002 semantic owners  
**Reviewed implementation head:** `8d905151b2f13c356585504f66c0de1e1c46380f`  
**Requirement:** `VPNG-U001-R1.R3.R8`  
**Architecture:** A.007, C.001, D.002  
**Evidence:** `EV-00200`

## Verdict

**PASS — the accepted A.007 Profile, D.002 peer and D.002 recoverable-group probe owners can
now be compiled into one deterministic C.001 allocation and one complete physical desired
union without merging their semantic evidence.**

This review deliberately accepts only the pure composition boundary. The running alpha still
uses its older A.007-only assembly/cycle and therefore this unit does not claim runtime
D.002 scheduling, status publication or A.007 generation invalidation.

## Findings and dispositions

### F1 — a shared physical plane must have one accepted allocation and one full desired union

**Decision:** accepted.

`build_probe_plane_desired_assembly(...)` creates one `ProbeRoutingDemand` set spanning all
current Profile, peer and group semantic owners, calls the existing collision-free
`NetworkPolicyLayoutCalculator` once and lowers the complete owner set through one
`bound_probe_policy.py` invocation. There is no per-consumer allocator or second physical
projector.

### F2 — equal physical target does not permit semantic verdict merging

**Decision:** accepted.

A Profile availability owner and a recoverable-group owner may intentionally carry the same
ICMP target and current endpoint. They remain distinct semantic owners with distinct probe
allocations/execution contexts. Existing C.001 scoped readiness may later let one identical
physical local nft rule satisfy both owners, but their evidence/verdict identities remain
separate.

### F3 — D.002 intent must be bound to the exact accepted current path

**Decision:** accepted.

Peer/group intents are rejected when their supplied `RoutePriorityPathRoute` is not exactly
the accepted current route realization. This catches same logical path with a replaced
`InterfaceIdentity` before allocation/convergence and prevents stale D.002 lower intent from
joining the current union.

### F4 — semantic Profile membership must be fail-closed at the combined boundary

**Decision:** fixed by `2f4f29678b66b617379e1ba818cb3d428f1fc5e8`.

The first composer revision checked current Device/path identity but could still receive a
well-typed group owner whose `profile_id` did not own that current path. The final version
requires both A.007 Profile owners and D.002 group owners to belong to the accepted current
Profile/path membership. Peer technical owners remain Device-scoped as required.

### F5 — input enumeration order must not change internal resource identity

**Decision:** accepted.

Typed intents are normalized by the existing semantic-owner ordering before allocation.
Reversing peer input order produces exactly the same layout, full desired state and normalized
typed intent set.

### F6 — new production code must remain exhaustively architecture-traced

**Decision:** fixed by `8d905151b2f13c356585504f66c0de1e1c46380f`.

Run `45581842029`, unit job `139093679022`, failed only the production-unit trace guard:
all seven new composition tests passed, but the new module was absent from the exhaustive
manifest. The final commit adds the exact `A.007 + C.001 + D.002` trace edge. Run
`45582035756`, unit job `139094358081`, then passed the complete unit suite.

## Evidence

- initial composer: `294660b98851eb1061fb400b0e29dbf792f1b0ad`;
- focused tests: `115e3b2046f0bef9435e074b2ad39724ec6263a9`;
- owner-membership review fix: `2f4f29678b66b617379e1ba818cb3d428f1fc5e8`;
- final implementation/trace head: `8d905151b2f13c356585504f66c0de1e1c46380f`;
- final deterministic evidence: run `45582035756`, unit job `139094358081` — **PASS**;
- actual-main lineage run `45582035803` — **PASS**.

## Remaining boundary

The running alpha must next derive current D.002 peer/group intents, use this full-union
assembly for C.001 probe convergence and request A.007 readiness only for its Profile-owner
subset. D.002 then needs periodic/explicit reconciliation and runtime status publication.
Finally A.007 evidence currentness must include the applicable D.002 generation so a
group-owner transfer cannot leave old Profile evidence current.
