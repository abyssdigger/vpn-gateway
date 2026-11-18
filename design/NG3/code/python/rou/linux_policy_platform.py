from __future__ import annotations

from .linux_host_boundary_policy import HostBoundaryLinuxAllocation
from .linux_host_bootstrap import HostBootstrapLinuxAllocation
from .network_policy_layout import (
    NetworkPolicyPlatformSpace,
    NumericResourcePool,
    RouteMetricPlatformSpace,
)


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


# Ordinary-host namespace boundary owner. These are deliberately fixed Release-1
# keys, not a host-global allocation service. If the administrator already owns a
# conflicting key, host-boundary activation must fail rather than renumber silently.
NG3_HOST_BOUNDARY_LINUX_ALLOCATION = HostBoundaryLinuxAllocation(
    mark=0x56504E47,             # ASCII "VPNG"
    return_table=0x7FFF0001,
    return_rule_priority=0x1800,
    route_protocol=203,
)


# Selected ordinary-host bootstrap owner (EXP-059). Return steering remains the
# separate allocation above and must execute at higher precedence.
NG3_HOST_BOOTSTRAP_LINUX_ALLOCATION = HostBootstrapLinuxAllocation(
    table=0x7FFF0002,
    bypass_priority=0x1F00,
    pair_priorities=NumericResourcePool(
        first=0x2000,
        stop=0x6000,
    ),
    rule_protocol=203,
    route_protocol=203,
)
