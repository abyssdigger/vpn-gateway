# NG3 production implementation trace

**Status:** normative architecture trace manifest  
**Architecture:** `design/NG3/architecture-ng.md`  
**Scope:** production Python reference runtime under `design/NG3/code/python/rou/*.py`

This manifest is the exhaustive code-to-architecture edge for the current Python reference runtime. Every production Python unit appears exactly once below and resolves to one or more component specs. The referenced component specs own normative requirement traceability.

A production unit without a normal requirement path may appear only under `Architecture debt` with an explicit reason. Such an entry is a visible finding, not an accepted substitute for requirements.

## Trace: `A.001`

- `design/NG3/code/python/rou/alpha_runtime.py`
- `design/NG3/code/python/rou/controller_restart.py`
- `design/NG3/code/python/rou/controller_startup.py`
- `design/NG3/code/python/rou/controller_stop.py`
- `design/NG3/code/python/rou/instance_lock.py`

## Trace: `A.002`

- `design/NG3/code/python/rou/config.py`
- `design/NG3/code/python/rou/port_bundle.py`
- `design/NG3/code/python/rou/release1_config.py`

## Trace: `A.003`

- `design/NG3/code/python/rou/availability_description.py`

## Trace: `A.004`

- `design/NG3/code/python/rou/availability_confirmation.py`
- `design/NG3/code/python/rou/availability_manager.py`
- `design/NG3/code/python/rou/availability_routing_state.py`

## Trace: `A.004`, `A.007`, `C.001`, `C.003`

- `design/NG3/code/python/rou/linux_availability_cycle.py`

## Trace: `A.004`, `C.003`

- `design/NG3/code/python/rou/availability_route_priority.py`

## Trace: `A.005`

- `design/NG3/code/python/rou/device_policy.py`
- `design/NG3/code/python/rou/domain.py`
- `design/NG3/code/python/rou/payload_profile.py`
- `design/NG3/code/python/rou/profile_prefix_partition.py`

## Trace: `A.006`

- `design/NG3/code/python/rou/availability_priority.py`

## Trace: `A.007`

- `design/NG3/code/python/rou/availability_observation_tick.py`
- `design/NG3/code/python/rou/probe_attempt.py`
- `design/NG3/code/python/rou/probe_precondition.py`
- `design/NG3/code/python/rou/probe_runtime.py`

## Trace: `A.008`, `A.009`

- `design/NG3/code/python/rou/runtime_status.py`

## Trace: `A.011`

- `design/NG3/code/python/rou/protective_mode_manager.py`

## Trace: `A.010`

- `design/NG3/code/python/rou/operational_log.py`

## Trace: `B.001`, `C.007`, `C.009`

- `design/NG3/code/python/rou/managed_network_domain.py`

## Trace: `C.001`

- `design/NG3/code/python/rou/device_firewall_compiler.py`
- `design/NG3/code/python/rou/device_firewall_desired.py`
- `design/NG3/code/python/rou/device_firewall_policy_compiler.py`
- `design/NG3/code/python/rou/local_integration_policy.py`
- `design/NG3/code/python/rou/local_publication_policy.py`
- `design/NG3/code/python/rou/payload_forward_compiler.py`
- `design/NG3/code/python/rou/payload_forward_desired.py`
- `design/NG3/code/python/rou/payload_nat_desired.py`
- `design/NG3/code/python/rou/payload_network_policy_desired.py`
- `design/NG3/code/python/rou/payload_routing_desired.py`
- `design/NG3/code/python/rou/probe_desired.py`
- `design/NG3/code/python/rou/probe_policy.py`
- `design/NG3/code/python/rou/route_priority_domain_builder.py`
- `design/NG3/code/python/rou/route_priority_realization.py`

## Trace: `C.001`, `C.003`

- `design/NG3/code/python/rou/network_policy_activation.py`

## Trace: `C.002`

- `design/NG3/code/python/rou/linux_policy_platform.py`
- `design/NG3/code/python/rou/network_policy_layout.py`

## Trace: `C.003`

- `design/NG3/code/python/rou/composite_nft_mutation.py`
- `design/NG3/code/python/rou/composite_nft_plan.py`
- `design/NG3/code/python/rou/composite_nft_policy.py`
- `design/NG3/code/python/rou/device_firewall_compare.py`
- `design/NG3/code/python/rou/device_firewall_mutation.py`
- `design/NG3/code/python/rou/device_firewall_structure.py`
- `design/NG3/code/python/rou/iproute_priority_backend.py`
- `design/NG3/code/python/rou/linux_composite_nft.py`
- `design/NG3/code/python/rou/linux_device_firewall.py`
- `design/NG3/code/python/rou/linux_local_integration.py`
- `design/NG3/code/python/rou/linux_local_publication.py`
- `design/NG3/code/python/rou/linux_nft_scaffold.py`
- `design/NG3/code/python/rou/linux_payload_nat.py`
- `design/NG3/code/python/rou/linux_probe_local.py`
- `design/NG3/code/python/rou/linux_probe_routing.py`
- `design/NG3/code/python/rou/linux_stack_return_affinity.py`
- `design/NG3/code/python/rou/linux_structural_policy.py`
- `design/NG3/code/python/rou/linux_structural_routing.py`
- `design/NG3/code/python/rou/local_integration_mutation.py`
- `design/NG3/code/python/rou/local_integration_observation.py`
- `design/NG3/code/python/rou/local_publication_mutation.py`
- `design/NG3/code/python/rou/local_publication_observation.py`
- `design/NG3/code/python/rou/nft_namespace_inventory.py`
- `design/NG3/code/python/rou/nft_payload_scaffold.py`
- `design/NG3/code/python/rou/nft_scaffold_enforcer.py`
- `design/NG3/code/python/rou/nft_scaffold_executor.py`
- `design/NG3/code/python/rou/payload_forward_compare.py`
- `design/NG3/code/python/rou/payload_forward_observation.py`
- `design/NG3/code/python/rou/payload_nat_mutation.py`
- `design/NG3/code/python/rou/payload_nat_observation.py`
- `design/NG3/code/python/rou/payload_routing_compare.py`
- `design/NG3/code/python/rou/probe_local_mutation.py`
- `design/NG3/code/python/rou/probe_local_observation.py`
- `design/NG3/code/python/rou/probe_routing_compare.py`
- `design/NG3/code/python/rou/probe_routing_convergence.py`
- `design/NG3/code/python/rou/probe_routing_plan.py`
- `design/NG3/code/python/rou/route_priority.py`
- `design/NG3/code/python/rou/route_priority_convergence.py`
- `design/NG3/code/python/rou/route_priority_enforcer.py`
- `design/NG3/code/python/rou/route_priority_executor.py`
- `design/NG3/code/python/rou/route_priority_inventory.py`
- `design/NG3/code/python/rou/route_priority_profile.py`
- `design/NG3/code/python/rou/stack_return_affinity.py`
- `design/NG3/code/python/rou/stack_return_affinity_convergence.py`
- `design/NG3/code/python/rou/structural_policy_mutation.py`
- `design/NG3/code/python/rou/structural_policy_plan.py`
- `design/NG3/code/python/rou/structural_policy_transaction.py`
- `design/NG3/code/python/rou/structural_routing_inventory.py`

## Trace: `C.004`

- `design/NG3/code/python/rou/binding.py`
- `design/NG3/code/python/rou/direct_device_route.py`
- `design/NG3/code/python/rou/interface_identity.py`
- `design/NG3/code/python/rou/interface_inventory.py`
- `design/NG3/code/python/rou/linux_vpn_path_adapter.py`

## Trace: `C.005`

- `design/NG3/code/python/rou/forwarding_gate.py`

## Trace: `C.006`

- `design/NG3/code/python/rou/linux_forwarding_gate.py`

## Trace: `C.008`

- `design/NG3/code/python/rou/icmp_probe_driver.py`

## Trace: `C.010`

- `design/NG3/code/python/rou/protective_payload_gate.py`
- `design/NG3/code/python/rou/linux_protective_payload_gate.py`

## Trace: `E.004`

- `design/NG3/code/python/rou/aggressive_host_routing_enforcer.py`
- `design/NG3/code/python/rou/linux_aggressive_escape_guard.py`
- `design/NG3/code/python/rou/linux_aggressive_routing_authority.py`

## Trace: `E.001`

- `design/NG3/code/python/rou/host_publication_adapter.py`
- `design/NG3/code/python/rou/host_publication_policy.py`
- `design/NG3/code/python/rou/linux_host_publication.py`

## Trace: `E.002`

- `design/NG3/code/python/rou/host_managed_routing.py`
- `design/NG3/code/python/rou/host_routing_contribution.py`
- `design/NG3/code/python/rou/linux_host_managed_routing.py`
- `design/NG3/code/python/rou/linux_host_managed_routing_backend.py`
- `design/NG3/code/python/rou/release1_host_boundary.py`
- `design/NG3/code/python/rou/release1_host_route_helper.py`
- `design/NG3/code/python/rou/selected_host_boundary.py`

## Architecture debt

- `design/NG3/code/python/rou/__init__.py` — package export facade exists as Python packaging convenience; no product semantic requirement requires this file itself. Exported implementation units remain traced by their own entries above.
