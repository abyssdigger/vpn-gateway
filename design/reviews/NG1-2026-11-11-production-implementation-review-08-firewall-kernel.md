# Production implementation review 08 — filter-table apply/verify

Role: external expert review focused on iptables transaction semantics, verification and
failure containment.

## Scope

Reviewed `firewall_kernel.py`, integration/unit tests, v0 canonical save technique and
Draft 4 filter ownership.

## Findings

No source-level corrective finding remains.

The only behavior requiring kernel proof is the exact
`iptables-legacy-restore -> iptables-legacy-save` canonical round-trip. A disposable
network-namespace integration harness has therefore been added and wired into GitHub CI.
Until that run succeeds, the source implementation is accepted but kernel round-trip
evidence is tracked by CI rather than inferred from mocks.

## Safety/Rust review

- apply uses one restore transaction for the complete owned filter table;
- verification compares normalized semantic serialization, ignoring counters/timestamps;
- namespace execution remains argv-based and injectable;
- no forwarding state is changed by this layer.

## Verdict

Source design approved. Kernel round-trip evidence delegated to the dedicated integration
job; any failure is a gate for Planner forwarding-open.
