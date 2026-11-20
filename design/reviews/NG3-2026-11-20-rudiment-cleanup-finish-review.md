# NG3 rudiment-cleanup finish review — 2026-11-20

## Scope

Continuation and completion of the interrupted cleanup review unit whose prior branch ended at
`048fb07e7ef938d38c5aee663f6a93b6fc6c18d7`.

This review covers:

- removal-follow-through after deletion of the obsolete scalar Profile classifier;
- preservation of the managed-L3 backend contract after removal of current dual-backend machinery;
- experiment-registry temporal status-reference semantics;
- a read-only rudiment review of the remaining controller host-boundary lifecycle seam.

Working branch:

`ng3-design-cycle-20261120-rudiment-cleanup-finish-35m`

## Completed corrections

### Profile classification cleanup

The production `profile_classification.py` module remains removed.

Two stale tests still depended on its scalar helpers and caused the previous tip's unit job to
fail. The correction does not restore that production API:

- `test_profile_prefix_partition.py` now keeps a small test-local scalar oracle used only to
  prove exhaustive equivalence of the current disjoint-prefix partition;
- `test_pure_structural_pipeline.py` exercises the current
  `build_*_profile_partition(...)` contract directly.

This preserves independent semantic evidence without retaining a compatibility API.

### Managed-L3 backend scope

Release 1 remains singular:

`routed-veth-proxy-arp`

No runtime backend selector, alternate implementation seam, Device/Profile backend knob or
dual-backend CI matrix is restored.

The architecture now preserves the distinct fact established by EXP-070/071: netkit L3 is an
experimentally viable future realization of the same managed-L3 endpoint role, while the
performance comparison found no material steady-state dataplane advantage that justifies
Release-1 dual-backend complexity.

The general development rule is now explicit in `VPNG0007-R7.R3.R5`: where practical lower
mechanisms provide the same accepted semantics, common logic depends on the semantic contract
and mechanism-specific observation/actuation remains behind the lower boundary. A future
netkit backend may therefore be selected through platform/implementation settings in the same
VPN-GATE product build rather than requiring a separate product variant.

### Temporal experiment-status references

Experiment lifecycle rules now require a Note that references another mutable object's
status/disposition/role to record the relationship as a fact of the decision being documented,
rather than as an automatically current claim about the referenced object.

The referenced object's own canonical registry entry remains authoritative for later/current
status. EXP-014's reference to EXP-062 and the current EXP-070/071/072/075 applicability notes
were aligned with this rule where the causal relationship is explicit.

## Evidence

GitHub Actions workflow `NG3 Python`, run `44701273975`, completed successfully on code
commit `dc6e46375273bb86907cdb40c7bd0cf7d59ab377`.

The run includes:

- unit tests;
- Linux payload routing/NAT/firewall integrations;
- EXP-049/050 OpenVPN onboarding/lifecycle;
- alpha smoke;
- stack return affinity;
- host managed routing;
- Profile SNAT reverse and combined dataplane evidence;
- Debian-12 routed-veth evidence.

All jobs completed successfully.

Subsequent commits in this review unit change only requirements, architecture, process and
experiment-registry documentation.

## Rudiment review findings

### F1 — controller host-routing lifecycle mechanism is current, not removable

`ControllerBoundaryContribution` currently provides materially required lifecycle ordering
for ordinary-host managed routing:

- converge the host managed-routing contribution before internal payload policy is activated;
- clean it after convergence/activation failure;
- clean it during stop before managed-domain teardown;
- retain the controller lifetime lock when cleanup cannot be confirmed.

Removing this behavior without an equivalent replacement would violate the current startup,
shutdown and independent-cleanup semantics represented by `VPNG0005-R5.R1`,
`VPNG0005-R5.R4`, `VPNG0005-R5.R5` and `VPNG0005-R5.R6`.

**Disposition:** retain the behavior.

### F2 — the generic boundary naming is stale

The only current implementation of `ControllerBoundaryContribution` is the host
managed-routing contribution in `selected_host_boundary.py`. The old generalized
host-boundary/backend selection model has been removed.

Current names therefore overstate the remaining generality:

- `ControllerBoundaryContribution`;
- `ControllerBoundaryContributionBuilder`;
- `SelectedHostBoundary*`;
- `SelectedLinuxHostBoundaryContribution`;
- `release1_host_boundary.py`.

The implementation responsibility is now specifically ordinary-host managed routing.

**Disposition:** open cleanup finding. Re-review a mechanical specialization/rename around
host-managed-routing responsibility; do not remove lifecycle ordering.

### F3 — startup/stop architecture omits an implemented current step

Architecture section 12.0.3 currently describes startup as building payload desired state and
then calling `activate_network_policy(...)`. The executable controller additionally builds
and converges the host managed-routing contribution before activation.

Section 12.0.4 likewise describes containment followed by managed-domain teardown, while the
implementation first attempts host managed-routing cleanup and only then destroys the managed
domain.

The host-routing semantics themselves are documented in section 1.1.1-A, but their lifecycle
placement is not represented in the startup/stop sequence.

**Disposition:** open architecture-consistency finding. The next cleanup unit should describe
the current ordering explicitly before or together with any mechanical specialization.

### F4 — minor stale wording remains in controller tests

A synthetic cleanup failure in `test_controller_stop.py` still uses the diagnostic text
`host bootstrap remains`. It no longer names a current owner/mechanism.

**Disposition:** editorial cleanup candidate; no behavioral significance.

## Verdict

**Completed carry-over work: ACCEPTED.**

The interrupted cleanup unit's concrete CI regression is fixed without restoring obsolete
production machinery. The managed-L3/netkit evidence boundary and temporal experiment-note
semantics are now explicit.

The controller lifecycle review found no justification for deleting the lifecycle behavior.
It did identify stale generalized naming plus a documentation/implementation sequencing gap.
Those findings are suitable for a subsequent bounded cleanup unit and are not blockers for
the completed carry-over work.
