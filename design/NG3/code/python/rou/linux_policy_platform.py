from __future__ import annotations

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
