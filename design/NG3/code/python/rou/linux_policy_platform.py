from __future__ import annotations

from .linux_host_managed_routing import HostManagedRoutingLinuxAllocation
from .network_policy_layout import (
    NetworkPolicyPlatformSpace,
    NumericResourcePool,
    RouteMetricPlatformSpace,
)
from .stack_return_affinity import StackReturnAffinityPlatformSpace
from .probe_policy import ProbeLocalPlatform


NG3_LINUX_POLICY_PLATFORM = NetworkPolicyPlatformSpace(
    payload_tables=NumericResourcePool(
        first=0x80000000,
        stop=0xC0000000,
    ),
    probe_tables=NumericResourcePool(
        first=0xC0000000,
        stop=0x1_0000_0000,
    ),
    probe_rule_priorities=NumericResourcePool(
        first=0x2000,
        stop=0x4000,
    ),
    payload_rule_priorities=NumericResourcePool(
        first=0x4000,
        stop=0x6000,
    ),
    ambient_main_rule_priority=32766,
    path_route_protocol=202,
    guard_route_protocol=201,
    route_metrics=RouteMetricPlatformSpace(
        first_preference_metric=1,
        terminal_guard_metric=0xFFFFFFFF,
    ),
    nft_family="ip",
    nft_table="vpn_gate",
)


# Current ordinary-host managed-destination routing owner. Only the current
# bypass/dispatch/table keys are reserved.
NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION = HostManagedRoutingLinuxAllocation(
    table=0x7FFF0003,
    bypass_priority=0x6000,
    dispatch_priority=0x6001,
    owned_rule_priorities=NumericResourcePool(
        first=0x6001,
        stop=0x6002,
    ),
    rule_protocol=203,
    route_protocol=203,
)


# Current managed-stack Profile flow association / return affinity. The RPDB
# rules execute before probe/payload dispatch; marks live in a separate resource
# namespace and are allocated deterministically per active inbound-capable Profile.
NG3_STACK_RETURN_AFFINITY_PLATFORM = StackReturnAffinityPlatformSpace(
    marks=NumericResourcePool(
        first=0x10000000,
        stop=0x10002000,
    ),
    rule_priorities=NumericResourcePool(
        first=0x1800,
        stop=0x2000,
    ),
)


# Release-1 dedicated probe worker/local-policy identity. Numeric values are
# lower Linux allocation, not user configuration. UID 4242 is the current
# EXP-067-proven non-root alpha/reference worker identity.
NG3_PROBE_LOCAL_PLATFORM = ProbeLocalPlatform(
    process_uid=4242,
    conntrack_mark=0x20000001,
)


# Release-1 peaceful host-routing helper. It is intentionally distinct from the
# postponed authoritative owner above: explicit non-default main routes are
# consulted before this table, and no runtime reconciliation is attached.
NG3_PEACEFUL_HOST_ROUTING_LINUX_ALLOCATION = HostManagedRoutingLinuxAllocation(
    table=0x7FFF0004,
    bypass_priority=0x6002,
    preserve_priority=0x6003,
    dispatch_priority=0x6004,
    scope_exit_priority=0x7000,
    owned_rule_priorities=NumericResourcePool(
        first=0x6003,
        stop=0x7001,
    ),
    rule_protocol=204,
    route_protocol=204,
)
