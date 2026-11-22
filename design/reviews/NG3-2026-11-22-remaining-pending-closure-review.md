# VPN-GATE NG3 — remaining pending requirements closure review

**Date:** 2026-11-22  
**Baseline:** `fe9e32d5ed2f8a16e2e8c30e0137c74b425e4956`  
**Architecture:** `design/NG3/architecture-ng.md`  
**Current executable baseline:** GitHub Actions `NG3 Python` run `45027427711` — SUCCESS, 21/21 jobs.

## Scope

This review evaluates the 17 Requirement/Constraint nodes that remained
`pending_closure` after the postponed-state split. It does not change product semantics,
architecture, implementation, constraints, or postponed descendants. It only decides whether
the current architecture plus already accepted executable evidence is sufficient for closure
under `design/requirements-model.md`.

All 17 nodes have exact current architecture coverage. The closure model still requires
accepted evidence: architecture reference alone is not used as closure evidence.

## Findings and dispositions

### F1 — Device-scoped NAT and firewall policy are implemented current behavior

Affected nodes:

- `VPNG-U001-R1.R4.R1`
- `VPNG-U001-R1.R4.R2`
- `VPNG-U001-R4.R4.R6.R1`
- `VPNG-U001-R4.R4.R6.R2`

**Decision:** accepted.  
**Resolution:** fixed.

Current configuration tests prove explicit `use_outbound_nat`, ordered Device firewall
grammar and role-sensitive validation. EXP-033 proves exact-path outbound masquerade and
source hiding. EXP-041 proves that Device firewall policy is a narrowing child layer rather
than a new permission source, including terminal no-match DROP. EXP-042 proves source,
destination and protocol/port predicates. The current workflow reruns these paths in
`linux-payload-nat` and `linux-payload-forward`.

`VPNG-U001-R1.R4.R2` and `VPNG-U001-R4.R4.R6.R2` are closed directly, not by descendant
aggregation. Their postponed per-path Device-firewall descendants remain postponed; current
Device-wide per-VPN-resource filtering is sufficient for the parent statements and does not
claim the future finer granularity.

### F2 — Profile source identity configuration and inbound distinguishability are executable

Affected nodes:

- `VPNG-U001-R3`
- `VPNG-U001-R4.R4.R4.R4.C1`

**Decision:** accepted.  
**Resolution:** fixed.

`test_release1_config.py` covers the canonical `direction` encodings, shared
`default_snat_address`, explicit per-Profile IPv4 override, invalid outbound SNAT and the
required default for bare `+snat`. EXP-075 proves reverse reachability for the Profile SNAT
identity. EXP-076 proves shared identity, no-SNAT source preservation, Profile isolation,
policy-before-translation ordering and reverse flows. The current workflow jobs
`linux-profile-snat-reverse`, `linux-profile-snat-combined` and `linux-payload-nat` all
pass.

This directly closes the Release-1 encoding constraint and the user-visible inbound-source
distinguishability requirement.

### F3 — the current human configuration surface is accepted

Affected nodes:

- `VPNG-U001-R4.R4.R6.R1` (also covered by F1)
- `VPNG-U001-R4.R4.R4.R4.C1` (also covered by F2)

**Decision:** accepted.  
**Resolution:** fixed.

The canonical configuration parser is strict and the current unit suite exercises the complete
surface, including Device NAT, ordered Device firewall policy, Profile SNAT identity and
availability selection. No lower Linux object identifiers are required as user input.

### F4 — peaceful host-routing automation closes the current automation promise

Affected nodes:

- `VPNG-U001-R5`
- `VPNG-U001-R5.R1.R1`

**Decision:** accepted.  
**Resolution:** fixed.

EXP-078 proves `:local`, `:external`, `:any`, exact-ingress and selector-union behavior
while leaving the host main table untouched. EXP-079 proves absolute managed-boundary
no-recapture. EXP-080 proves selector-scoped preserve-main behavior leaves unrelated
administrator policy unchanged. The current `linux-host-managed-routing` job reruns these
experiments successfully.

The broad parent `VPNG-U001-R5` is closed directly: it requires that the user can explicitly
enable host-routing automation, which the peaceful helper provides. The postponed aggressive
helper is an additional ownership mode, not a prerequisite for satisfying that parent promise.

### F5 — packet matching by source, destination and traffic type is implemented before translation

Affected node:

- `VPNG-U002-R2.R1.R3`

**Decision:** accepted.  
**Resolution:** fixed.

The Device firewall compiler has explicit direction partitioning and normalized
source/destination/protocol/port predicates. EXP-042 proves canonical nft representation for
IPv4 source, IPv4 destination and L4 protocol/ports. EXP-076 additionally proves that managed
policy classification occurs on the original source before Profile source translation.
Current `linux-payload-forward` and `linux-profile-snat-combined` evidence pass.

The node remains `decomposition: incomplete`; direct acceptance evidence is therefore used,
not closure by descendants.

### F6 — pure priority reorder preserves path membership

Affected node:

- `VPNG-U003-R3.R9`

**Decision:** accepted.  
**Resolution:** fixed.

`test_route_priority_convergence.py` exercises make-before-break swaps, partial re-observation,
duplicate cleanup, exact no-op and rejection of structural membership changes. The current
`linux-route-priority` job passes, and EXP-068 continues to prove live effective-order
failover/recovery. This is sufficient evidence that priority-only convergence does not
temporarily remove an otherwise eligible path.

### F7 — established inbound flows retain return-path affinity

Affected node:

- `VPNG-U003-R4`

**Decision:** accepted.  
**Resolution:** fixed.

EXP-061 proves that the same exchange fails without stack return affinity, succeeds with the
affinity owner, and fails again after owner removal. The production-owner integration is also
covered by the current `linux-stack-return-affinity-owner` job. Both
`linux-stack-return-affinity` and owner integration pass on the reviewed baseline.

### F8 — unrelated host network state cannot bypass managed policy

Affected node:

- `VPNG-U004-R4.R6`

**Decision:** accepted.  
**Resolution:** fixed.

The accepted cross-domain structural evidence for EXP-048 proves terminal managed routing
behavior rather than ambient/main fallback and exact owner-scoped mutation that preserves
unrelated state. The current workflow passes `linux-structural-inventory-shape`,
`linux-payload-forward`, `linux-forwarding-barrier`, `linux-policy-platform` and
`linux-host-managed-routing`. Together with the current C.003 exact/fail-closed convergence
contract, this is sufficient evidence that unrelated host network state cannot broaden or
redirect managed traffic around the required policy.

## Aggregate closure after direct findings

Once the direct findings above are applied, the following complete parents close by the
formal immediate-child aggregation rule:

- `VPNG-U001-R1.R4` — both direct children become closed;
- `VPNG-U001-R4` — all current immediate children were already closed;
- `VPNG-U001-R4.R4.R4.R4` — its immediate normative constraint becomes closed;
- `VPNG-U001-R5.R1` — its detailed peaceful-helper child becomes closed;
- `VPNG-U003-R3.R6.R3.R1` — all immediate children/constraints were already closed.

These aggregate closures do not broaden any descendant scope and do not re-enter postponed
capabilities.

## Closure set

The complete accepted transition is:

- `VPNG-U001-R1.R4`: `pending_closure -> closed`
- `VPNG-U001-R1.R4.R1`: `pending_closure -> closed`
- `VPNG-U001-R1.R4.R2`: `pending_closure -> closed`
- `VPNG-U001-R3`: `pending_closure -> closed`
- `VPNG-U001-R4`: `pending_closure -> closed`
- `VPNG-U001-R4.R4.R4.R4`: `pending_closure -> closed`
- `VPNG-U001-R4.R4.R4.R4.C1`: `pending_closure -> closed`
- `VPNG-U001-R4.R4.R6.R1`: `pending_closure -> closed`
- `VPNG-U001-R4.R4.R6.R2`: `pending_closure -> closed`
- `VPNG-U001-R5`: `pending_closure -> closed`
- `VPNG-U001-R5.R1`: `pending_closure -> closed`
- `VPNG-U001-R5.R1.R1`: `pending_closure -> closed`
- `VPNG-U002-R2.R1.R3`: `pending_closure -> closed`
- `VPNG-U003-R3.R6.R3.R1`: `pending_closure -> closed`
- `VPNG-U003-R3.R9`: `pending_closure -> closed`
- `VPNG-U003-R4`: `pending_closure -> closed`
- `VPNG-U004-R4.R6`: `pending_closure -> closed`

No `postponed`, `rejected_closure`, decomposition label or requirement statement changes.

## Verdict

**PASS — all 17 remaining `pending_closure` nodes have sufficient accepted closure
evidence.**

The normative follow-up is limited to changing those 17 closure labels to `closed`.
