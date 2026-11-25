# NG3 WireGuard peer-probe reusable seam review — 2026-11-25

**Review unit:** C.008 physical probe reuse + C.001 distinct peer-probe owner/projection seam  
**Source reviewed:** `5a2e112dc3d13880d212dd23eb62c993f612cd38`  
**Requirement:** `VPNG-U001-R1.R3.R8`  
**Architecture:** C.001, C.008, D.002  
**Stable evidence:** `EV-00110`

## Findings

### F1 — WireGuard peers are not encoded as synthetic logical paths

**Decision:** accepted  
**Resolution:** fixed

The lower shared owner domain now has a dedicated
`WireGuardPeerProbeOwner(device_id, peer_id)`. A.007 retains
`ProbePolicyOwner(profile_id, LogicalPathId)`; availability runtime/status APIs were not
widened.

### F2 — physical ICMP execution is reusable without transferring semantic ownership

**Decision:** accepted  
**Resolution:** fixed

`LinuxIcmpProbeDriver.execute()` consumes only current interface identity and target. The
existing A.007 `check()` path is a compatibility wrapper. Command rendering, UID isolation,
deadlines and technical result mapping are unchanged.

### F3 — shared C.001 allocation preserves separate owner scopes

**Decision:** accepted  
**Resolution:** fixed

The probe resource allocator accepts both semantic owner kinds but sorts them through an
explicit tagged owner key; it does not compare unlike dataclass identities or merge their
meaning. Tables and RPDB priorities remain one shared collision-free physical resource class.

### F4 — peer policy reuses physical machinery rather than duplicating it

**Decision:** accepted  
**Resolution:** fixed

`wireguard_peer_probe_policy.py` projects the permanent peer /32 through the already current
Device path into the same unicast+guard route, UID/oif RPDB rule and OUTPUT/INPUT local-admission
shape used by A.007. Equivalence tests compare all physical fields while allowing the semantic
owner to differ.

### F5 — C.001 is not falsely declared runtime-complete

**Decision:** accepted  
**Resolution:** open by design

The owner/projection/precondition seam is present, but alpha does not yet add peer-probe demand
to the shared NetworkPolicyAdapter desired state. That demand belongs to the not-yet-materialized
D.002 Manager. Therefore C.001 remains `partial` for R8; C.008 can be `full` because its
component-local physical execution contract is complete and reusable.

## Verification

GitHub Actions run `45553552569`, `unit` job `139000197586` — PASS, including the
complete architecture traceability suite and peer/availability physical-equivalence tests.

## Verdict

**PASS for the intended seam.** C.008 fully supports the R8 physical-attempt contract. C.001
has the required distinct owner/projection/precondition machinery but remains partial until D.002
runtime composition supplies and reconciles peer-probe demand.
