from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.binding import LogicalPathId
from rou.domain import Direction
from rou.interface_identity import InterfaceIdentity
from rou.linux_policy_platform import (
    NG3_LINUX_POLICY_PLATFORM,
    NG3_PROBE_LOCAL_PLATFORM,
)
from rou.network_policy_layout import (
    ProbePolicyOwner,
    WireGuardGroupProbeOwner,
    WireGuardPeerProbeOwner,
)
from rou.payload_profile import PayloadProfileRequest
from rou.probe_plane_desired import (
    ProbePlaneDesiredAssemblyError,
    build_probe_plane_desired_assembly,
)
from rou.probe_policy import AvailabilityProbeIntent
from rou.route_priority_inventory import RoutePriorityPathRoute
from rou.wireguard_group_probe_policy import WireGuardGroupProbeIntent
from rou.wireguard_peer_probe_policy import WireGuardPeerProbeIntent


PATH = LogicalPathId("wg", 0, 0)
EP = InterfaceIdentity("wg0", 17)
ROUTE = RoutePriorityPathRoute(PATH, EP)
PROFILE_OWNER = ProbePolicyOwner("corp", PATH)
PEER_A_OWNER = WireGuardPeerProbeOwner("wg", "edge-a")
PEER_B_OWNER = WireGuardPeerProbeOwner("wg", "edge-b")
GROUP_OWNER = WireGuardGroupProbeOwner("corp", "wg")
GROUP_TARGET = IPv4Address("10.77.0.1")


def profile() -> PayloadProfileRequest:
    return PayloadProfileRequest(
        "corp",
        Direction.OUTBOUND,
        (IPv4Network("10.77.0.0/24"),),
        (PATH,),
    )


def availability() -> AvailabilityProbeIntent:
    return AvailabilityProbeIntent(PROFILE_OWNER, GROUP_TARGET)


def peer_a() -> WireGuardPeerProbeIntent:
    return WireGuardPeerProbeIntent(
        PEER_A_OWNER,
        IPv4Address("10.201.0.1"),
        ROUTE,
    )


def peer_b() -> WireGuardPeerProbeIntent:
    return WireGuardPeerProbeIntent(
        PEER_B_OWNER,
        IPv4Address("10.201.0.2"),
        ROUTE,
    )


def group() -> WireGuardGroupProbeIntent:
    return WireGuardGroupProbeIntent(
        GROUP_OWNER,
        GROUP_TARGET,
        ROUTE,
    )


class ProbePlaneDesiredAssemblyTests(unittest.TestCase):
    def build(self, *, peers=None):
        peer_intents = (
            (peer_a(), peer_b())
            if peers is None
            else peers
        )
        return build_probe_plane_desired_assembly(
            (profile(),),
            (availability(),),
            peer_intents,
            (group(),),
            (ROUTE,),
            NG3_LINUX_POLICY_PLATFORM,
            NG3_PROBE_LOCAL_PLATFORM,
        )

    def test_one_layout_and_desired_union_cover_all_semantic_owners(self):
        result = self.build()
        expected = (
            PROFILE_OWNER,
            PEER_A_OWNER,
            PEER_B_OWNER,
            GROUP_OWNER,
        )

        self.assertEqual(
            tuple(item.owner for item in result.layout.probe),
            expected,
        )
        self.assertEqual(
            tuple(item.owner for item in result.probe.rules),
            expected,
        )
        self.assertEqual(
            {item.owner for item in result.probe.local_rules},
            set(expected),
        )
        self.assertEqual(len(result.probe.routes), 2 * len(expected))
        self.assertEqual(
            len({item.table for item in result.layout.probe}),
            len(expected),
        )
        self.assertEqual(
            len({item.rule_priority for item in result.layout.probe}),
            len(expected),
        )

    def test_same_physical_target_keeps_profile_and_group_semantics_distinct(self):
        result = self.build()
        by_owner = {item.owner: item for item in result.probe.rules}

        profile_rule = by_owner[PROFILE_OWNER]
        group_rule = by_owner[GROUP_OWNER]
        self.assertEqual(profile_rule.target, GROUP_TARGET)
        self.assertEqual(group_rule.target, GROUP_TARGET)
        self.assertEqual(profile_rule.endpoint, EP)
        self.assertEqual(group_rule.endpoint, EP)
        self.assertNotEqual(profile_rule.table, group_rule.table)
        self.assertNotEqual(profile_rule.priority, group_rule.priority)

    def test_input_order_does_not_change_shared_allocation_or_desired_union(self):
        one = self.build()
        two = self.build(peers=(peer_b(), peer_a()))

        self.assertEqual(one.layout, two.layout)
        self.assertEqual(one.probe, two.probe)
        self.assertEqual(one.peer_intents, two.peer_intents)

    def test_d002_intent_must_use_accepted_current_path_realization(self):
        stale_route = RoutePriorityPathRoute(
            PATH,
            InterfaceIdentity("wg0", 99),
        )
        stale_peer = WireGuardPeerProbeIntent(
            PEER_A_OWNER,
            IPv4Address("10.201.0.1"),
            stale_route,
        )

        with self.assertRaisesRegex(
            ProbePlaneDesiredAssemblyError,
            "accepted current path",
        ):
            build_probe_plane_desired_assembly(
                (profile(),),
                (availability(),),
                (stale_peer,),
                (group(),),
                (ROUTE,),
                NG3_LINUX_POLICY_PLATFORM,
                NG3_PROBE_LOCAL_PLATFORM,
            )

    def test_availability_owner_must_belong_to_current_profile_path(self):
        wrong = AvailabilityProbeIntent(
            ProbePolicyOwner("other", PATH),
            GROUP_TARGET,
        )
        with self.assertRaisesRegex(
            ProbePlaneDesiredAssemblyError,
            "availability owner is outside current Profile/path membership",
        ):
            build_probe_plane_desired_assembly(
                (profile(),),
                (wrong,),
                (peer_a(),),
                (group(),),
                (ROUTE,),
                NG3_LINUX_POLICY_PLATFORM,
                NG3_PROBE_LOCAL_PLATFORM,
            )

    def test_group_owner_must_belong_to_current_profile_path(self):
        wrong = WireGuardGroupProbeIntent(
            WireGuardGroupProbeOwner("other", "wg"),
            GROUP_TARGET,
            ROUTE,
        )
        with self.assertRaisesRegex(
            ProbePlaneDesiredAssemblyError,
            "group probe owner is outside current Profile/path membership",
        ):
            build_probe_plane_desired_assembly(
                (profile(),),
                (availability(),),
                (peer_a(),),
                (wrong,),
                (ROUTE,),
                NG3_LINUX_POLICY_PLATFORM,
                NG3_PROBE_LOCAL_PLATFORM,
            )

    def test_duplicate_semantic_owner_is_rejected_before_allocation(self):
        with self.assertRaisesRegex(
            ProbePlaneDesiredAssemblyError,
            "duplicate semantic owner",
        ):
            build_probe_plane_desired_assembly(
                (profile(),),
                (availability(),),
                (peer_a(), peer_a()),
                (group(),),
                (ROUTE,),
                NG3_LINUX_POLICY_PLATFORM,
                NG3_PROBE_LOCAL_PLATFORM,
            )


if __name__ == "__main__":
    unittest.main()
