from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.binding import LogicalPathId
from rou.interface_identity import InterfaceIdentity
from rou.linux_policy_platform import (
    NG3_LINUX_POLICY_PLATFORM,
    NG3_PROBE_LOCAL_PLATFORM,
)
from rou.network_policy_layout import (
    ProbePolicyOwner,
    ProbeRoutingDemand,
    WireGuardGroupProbeOwner,
    allocate_network_policy_layout,
)
from rou.payload_routing_desired import ManagedRouteType
from rou.probe_policy import (
    AvailabilityProbeIntent,
    build_probe_network_policy_desired_state,
)
from rou.route_priority_inventory import RoutePriorityPathRoute
from rou.wireguard_group_probe_policy import (
    WireGuardGroupProbeIntent,
    build_wireguard_group_probe_policy_desired_state,
)


PATH = LogicalPathId("wg", 0, 0)
EP = InterfaceIdentity("wg0", 17)
OWNER = WireGuardGroupProbeOwner("corp", "wg")
TARGET = IPv4Address("10.77.0.1")


class WireGuardGroupProbePolicyTests(unittest.TestCase):
    def test_projects_distinct_group_owner_without_new_logical_path(self):
        layout = allocate_network_policy_layout(
            (),
            (ProbeRoutingDemand(OWNER),),
            NG3_LINUX_POLICY_PLATFORM,
        )
        route = RoutePriorityPathRoute(PATH, EP)
        desired = build_wireguard_group_probe_policy_desired_state(
            (WireGuardGroupProbeIntent(OWNER, TARGET, route),),
            layout,
            NG3_LINUX_POLICY_PLATFORM,
            NG3_PROBE_LOCAL_PLATFORM,
        )

        self.assertEqual(len(desired.rules), 1)
        self.assertIs(desired.rules[0].owner, OWNER)
        self.assertEqual(desired.rules[0].endpoint, EP)
        self.assertEqual(desired.rules[0].target, TARGET)
        self.assertEqual(
            {
                (item.route_type, item.destination)
                for item in desired.routes
            },
            {
                (ManagedRouteType.UNICAST, IPv4Network("10.77.0.1/32")),
                (ManagedRouteType.BLACKHOLE, IPv4Network("0.0.0.0/0")),
            },
        )

    def test_group_projection_is_physically_equivalent_to_profile_probe(self):
        route = RoutePriorityPathRoute(PATH, EP)
        group_layout = allocate_network_policy_layout(
            (),
            (ProbeRoutingDemand(OWNER),),
            NG3_LINUX_POLICY_PLATFORM,
        )
        group = build_wireguard_group_probe_policy_desired_state(
            (WireGuardGroupProbeIntent(OWNER, TARGET, route),),
            group_layout,
            NG3_LINUX_POLICY_PLATFORM,
            NG3_PROBE_LOCAL_PLATFORM,
        )

        profile_owner = ProbePolicyOwner("corp", PATH)
        profile_layout = allocate_network_policy_layout(
            (),
            (ProbeRoutingDemand(profile_owner),),
            NG3_LINUX_POLICY_PLATFORM,
        )
        profile = build_probe_network_policy_desired_state(
            (AvailabilityProbeIntent(profile_owner, TARGET),),
            profile_layout,
            (route,),
            NG3_LINUX_POLICY_PLATFORM,
            NG3_PROBE_LOCAL_PLATFORM,
        )

        self.assertEqual(group.routes, profile.routes)
        self.assertEqual(
            [
                (
                    item.priority,
                    item.process_uid,
                    item.endpoint,
                    item.target,
                    item.table,
                    item.mechanism,
                )
                for item in group.rules
            ],
            [
                (
                    item.priority,
                    item.process_uid,
                    item.endpoint,
                    item.target,
                    item.table,
                    item.mechanism,
                )
                for item in profile.rules
            ],
        )
        self.assertEqual(
            [
                (
                    item.hook,
                    item.endpoint,
                    item.target,
                    item.conntrack_mark,
                    item.process_uid,
                    item.mechanism,
                )
                for item in group.local_rules
            ],
            [
                (
                    item.hook,
                    item.endpoint,
                    item.target,
                    item.conntrack_mark,
                    item.process_uid,
                    item.mechanism,
                )
                for item in profile.local_rules
            ],
        )

    def test_owner_device_must_match_current_path_device(self):
        with self.assertRaisesRegex(
            ValueError,
            "differs from current path Device",
        ):
            WireGuardGroupProbeIntent(
                WireGuardGroupProbeOwner("corp", "other"),
                TARGET,
                RoutePriorityPathRoute(PATH, EP),
            )


if __name__ == "__main__":
    unittest.main()
