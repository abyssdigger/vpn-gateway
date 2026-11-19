import unittest
from ipaddress import IPv4Address, IPv4Network

from rou.domain import Direction
from rou.host_managed_routing import (
    HostManagedRoutingProfile,
    build_host_managed_routing_plan,
)


class HostManagedRoutingTests(unittest.TestCase):
    def profile(self, profile_id, direction, destinations, snat=None):
        return HostManagedRoutingProfile(
            profile_id=profile_id,
            direction=direction,
            destinations=tuple(IPv4Network(item) for item in destinations),
            effective_snat_address=(
                None if snat is None else IPv4Address(snat)
            ),
        )

    def test_direction_does_not_change_remote_route_presence(self):
        plan = build_host_managed_routing_plan(
            (
                self.profile("out", Direction.OUTBOUND, ["10.1.0.0/16"]),
                self.profile("in", Direction.INBOUND, ["10.2.0.0/16"]),
                self.profile(
                    "both", Direction.BIDIRECTIONAL, ["10.3.0.0/16"]
                ),
            )
        )
        self.assertEqual(
            [item.destination.with_prefixlen for item in plan.routes],
            ["10.1.0.0/16", "10.2.0.0/16", "10.3.0.0/16"],
        )

    def test_shared_snat_identity_collapses_to_one_32(self):
        plan = build_host_managed_routing_plan(
            (
                self.profile(
                    "a", Direction.INBOUND, ["10.1.0.0/16"], "198.19.255.10"
                ),
                self.profile(
                    "b", Direction.INBOUND, ["10.2.0.0/16"], "198.19.255.10"
                ),
            )
        )
        identity = next(
            item
            for item in plan.routes
            if item.destination == IPv4Network("198.19.255.10/32")
        )
        self.assertEqual(identity.profile_ids, ("a", "b"))

    def test_full_tunnel_is_explicit(self):
        plan = build_host_managed_routing_plan(
            (
                self.profile("full", Direction.OUTBOUND, ["0.0.0.0/0"]),
            )
        )
        self.assertTrue(plan.full_tunnel)

    def test_empty_profile_set_is_empty_plan(self):
        plan = build_host_managed_routing_plan(())
        self.assertEqual(plan.routes, ())
        self.assertFalse(plan.full_tunnel)


if __name__ == "__main__":
    unittest.main()
