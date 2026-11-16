"""Pure multi-path composition for normalized Device firewall policy."""

from __future__ import annotations

from typing import Iterable

from .device_firewall_compiler import (
    DeviceFirewallCompileError,
    compile_device_firewall_policy,
)
from .device_firewall_desired import DeviceFirewallDesiredState
from .device_policy import DeviceFirewallPolicyIntent
from .interface_identity import InterfaceIdentity
from .route_priority_inventory import RoutePriorityPathRoute


class DeviceFirewallPolicyCompileError(ValueError):
    pass


def compile_device_firewall_policies(
    policies: Iterable[DeviceFirewallPolicyIntent],
    path_routes: Iterable[RoutePriorityPathRoute],
    host_boundary: InterfaceIdentity,
) -> DeviceFirewallDesiredState:
    """Compile normalized Device policy over all current payload paths.

    Production child-chain identifiers are deterministic internal lower tokens
    derived only from the canonical ordinal of the current LogicalPathId set.
    User/Device IDs are never embedded in nft object names.
    """
    if not isinstance(host_boundary, InterfaceIdentity):
        raise DeviceFirewallPolicyCompileError(
            "host_boundary must be InterfaceIdentity"
        )

    policy_by_device: dict[str, DeviceFirewallPolicyIntent] = {}
    for policy in policies:
        if not isinstance(policy, DeviceFirewallPolicyIntent):
            raise DeviceFirewallPolicyCompileError(
                "policies must contain DeviceFirewallPolicyIntent"
            )
        if policy.device_id in policy_by_device:
            raise DeviceFirewallPolicyCompileError(
                f"duplicate Device firewall policy for {policy.device_id!r}"
            )
        policy_by_device[policy.device_id] = policy

    route_by_path = {}
    endpoint_owner: dict[InterfaceIdentity, object] = {}
    for route in path_routes:
        if not isinstance(route, RoutePriorityPathRoute):
            raise DeviceFirewallPolicyCompileError(
                "path_routes must contain RoutePriorityPathRoute"
            )
        if route.path_id in route_by_path:
            raise DeviceFirewallPolicyCompileError(
                f"duplicate current path realization for {route.path_id!r}"
            )
        if route.endpoint == host_boundary:
            raise DeviceFirewallPolicyCompileError(
                "host boundary cannot also be a Device path endpoint"
            )
        previous = endpoint_owner.get(route.endpoint)
        if previous is not None and previous != route.path_id:
            raise DeviceFirewallPolicyCompileError(
                "one current endpoint cannot realize multiple logical paths"
            )
        route_by_path[route.path_id] = route
        endpoint_owner[route.endpoint] = route.path_id

    ordered_routes = tuple(
        route_by_path[path_id]
        for path_id in sorted(route_by_path)
    )

    chains = []
    for ordinal, route in enumerate(ordered_routes):
        policy = policy_by_device.get(route.path_id.device_id)
        if policy is None:
            raise DeviceFirewallPolicyCompileError(
                "current payload path has no normalized Device firewall policy: "
                f"{route.path_id!r}"
            )

        try:
            desired = compile_device_firewall_policy(
                policy,
                host_boundary,
                route.endpoint,
                out_chain_name=f"df_out_{ordinal:08x}",
                in_chain_name=f"df_in_{ordinal:08x}",
            )
        except DeviceFirewallCompileError as exc:
            raise DeviceFirewallPolicyCompileError(str(exc)) from exc
        chains.extend(desired.chains)

    return DeviceFirewallDesiredState(tuple(chains))
