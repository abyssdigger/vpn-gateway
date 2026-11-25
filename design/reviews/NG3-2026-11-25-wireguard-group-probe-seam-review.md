# NG3 WireGuard recoverable-group probe seam review — 2026-11-25

**Review unit:** C.001/C.008 lower seam for optional D.002 group endpoint checks  
**Reviewed implementation head:** `5816f965f666fa3296c3dcf40a89681de98cf75d`  
**Requirements:** `VPNG-U001-R1.R3.R8.R3.R1`  
**Architecture:** C.001, C.008, D.002  
**Evidence:** `EV-00170`

## Verdict

**PASS — the lower probe plane can now represent and safely execute a recoverable-group
endpoint check without merging it with Profile availability or peer health.**

This unit deliberately does not change D.002 selection sequencing. The Manager must still
perform the accepted post-transfer group check in a later review unit.

## Findings and dispositions

### F1 — group semantic identity must not change when its peer owner changes

**Decision:** accepted.

`WireGuardGroupProbeOwner(profile_id, device_id)` reuses the already accepted canonical
recoverable-group identity. Current `peer_id` is not part of the probe owner because failover
changes the group's current realization, not the group's identity. Freshness across such a
transfer remains a D.002 sequencing/generation obligation.

### F2 — group, peer and Profile evidence must remain distinct

**Decision:** accepted.

The new owner is a third `ProbeSemanticOwner` variant. It receives its own allocation and
execution context even when its target/endpoint produces the same physical nft rule as an A.007
Profile probe. Scoped readiness therefore permits physical sharing without verdict sharing.

### F3 — duplicate physical projection should not fork by semantic owner type

**Decision:** fixed by `48a506ac60da637b8ab6b496811901e464524300`.

The initial implementation duplicated the existing peer lower projection. Both peer and group
semantic wrappers now delegate to `bound_probe_policy.py`, which owns the common
route/RPDB/local-admission projection. The wrappers retain only owner-specific validation.

### F4 — executor must not infer or bypass group configuration

**Decision:** accepted.

`WireGuardGroupProbeExecutor` requires the typed A.002 group, checks exact owner identity,
current Device/path identity, concrete ICMP target and target membership in the group's payload
prefix bundle, then requires the exact confirmed C.001 execution context before invoking C.008.

### F5 — lower executor must not decide candidate peer selection

**Decision:** accepted.

The executor receives no candidate-selection policy and no `peer_id`. It proves only the
technical group endpoint attempt over current confirmed lower state. D.002 remains responsible
for establishing the candidate's D.003 ownership before the attempt and interpreting
`REPLY/NO_REPLY/LOCAL_ERROR` according to R8.R3.R1.

## Evidence

- initial lower seam: `f131b3e2d832141fb0dd9cb04b897f3147044148`;
- shared physical projection refactor: `48a506ac60da637b8ab6b496811901e464524300`;
- scoped-readiness group-owner evidence:
  `5816f965f666fa3296c3dcf40a89681de98cf75d`;
- final focused run `45575745380`, unit job `139073253482`: **PASS**;
- actual-main lineage run `45575745345`: **PASS**.

## Remaining boundary

D.002 must next stop rejecting endpoint-bearing groups and implement candidate evaluation as
an explicit bounded state transition: fresh peer suitability, D.003 exact ownership transfer,
fresh group endpoint check through that owner, then accept or continue. `LOCAL_ERROR` must
remain unconfirmed/problem rather than being converted to negative remote reachability.
