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
    WireGuardPeerProbeOwner,
    allocate_network_policy_layout,
)
from rou.payload_routing_desired import ManagedRouteType
from rou.probe_policy import (
    AvailabilityProbeIntent,
    build_probe_network_policy_desired_state,
)
from rou.route_priority_inventory import RoutePriorityPathRoute
from rou.wireguard_peer_probe_policy import (
    WireGuardPeerProbeIntent,
    build_wireguard_peer_probe_policy_desired_state,
)


PATH = LogicalPathId("wg", 0, 0)
EP = InterfaceIdentity("wg0", 17)
OWNER = WireGuardPeerProbeOwner("wg", "edge-a")
TARGET = IPv4Address("10.201.0.1")


class WireGuardPeerProbePolicyTests(unittest.TestCase):
    def test_projects_separate_owner_without_new_logical_path(self):
        layout = allocate_network_policy_layout(
            (),
            (ProbeRoutingDemand(OWNER),),
            NG3_LINUX_POLICY_PLATFORM,
        )
        route = RoutePriorityPathRoute(PATH, EP)
        desired = build_wireguard_peer_probe_policy_desired_state(
            (WireGuardPeerProbeIntent(OWNER, TARGET, route),),
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
                (ManagedRouteType.UNICAST, IPv4Network("10.201.0.1/32")),
                (ManagedRouteType.BLACKHOLE, IPv4Network("0.0.0.0/0")),
            },
        )
        unicast = next(
            item
            for item in desired.routes
            if item.route_type is ManagedRouteType.UNICAST
        )
        self.assertEqual(unicast.path_id, PATH)
        self.assertEqual(unicast.endpoint, EP)
        self.assertEqual(
            {item.owner for item in desired.local_rules},
            {OWNER},
        )

    def test_peer_projection_is_physically_equivalent_to_availability_probe(self):
        route = RoutePriorityPathRoute(PATH, EP)

        peer_layout = allocate_network_policy_layout(
            (),
            (ProbeRoutingDemand(OWNER),),
            NG3_LINUX_POLICY_PLATFORM,
        )
        peer = build_wireguard_peer_probe_policy_desired_state(
            (WireGuardPeerProbeIntent(OWNER, TARGET, route),),
            peer_layout,
            NG3_LINUX_POLICY_PLATFORM,
            NG3_PROBE_LOCAL_PLATFORM,
        )

        availability_owner = ProbePolicyOwner("corp", PATH)
        availability_layout = allocate_network_policy_layout(
            (),
            (ProbeRoutingDemand(availability_owner),),
            NG3_LINUX_POLICY_PLATFORM,
        )
        availability = build_probe_network_policy_desired_state(
            (AvailabilityProbeIntent(availability_owner, TARGET),),
            availability_layout,
            (route,),
            NG3_LINUX_POLICY_PLATFORM,
            NG3_PROBE_LOCAL_PLATFORM,
        )

        self.assertEqual(peer.routes, availability.routes)
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
                for item in peer.rules
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
                for item in availability.rules
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
                for item in peer.local_rules
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
                for item in availability.local_rules
            ],
        )

    def test_owner_device_must_match_current_path_device(self):
        with self.assertRaisesRegex(
            ValueError,
            "differs from current path Device",
        ):
            WireGuardPeerProbeIntent(
                WireGuardPeerProbeOwner("other", "edge-a"),
                TARGET,
                RoutePriorityPathRoute(PATH, EP),
            )

    def test_shared_layout_must_allocate_peer_owner(self):
        layout = allocate_network_policy_layout(
            (),
            (),
            NG3_LINUX_POLICY_PLATFORM,
        )
        with self.assertRaisesRegex(ValueError, "lacks shared probe allocation"):
            build_wireguard_peer_probe_policy_desired_state(
                (WireGuardPeerProbeIntent(
                    OWNER,
                    TARGET,
                    RoutePriorityPathRoute(PATH, EP),
                ),),
                layout,
                NG3_LINUX_POLICY_PLATFORM,
                NG3_PROBE_LOCAL_PLATFORM,
            )


if __name__ == "__main__":
    unittest.main()
