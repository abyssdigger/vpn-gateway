import unittest
from ipaddress import IPv4Address, IPv4Network

from rou.domain import Direction
from rou.host_boundary_policy import HostBoundaryProfileIntent, build_host_boundary_policy
from rou.host_underlay_policy import (
    UnderlayEndpointPayloadConflict,
    required_underlay_endpoints,
)


class HostUnderlayPolicyTests(unittest.TestCase):
    def plan(self, *networks):
        return build_host_boundary_policy(
            (
                HostBoundaryProfileIntent(
                    profile_id="p",
                    direction=Direction.OUTBOUND,
                    destinations=tuple(IPv4Network(value) for value in networks),
                ),
            )
        )

    def test_full_tunnel_captures_all_external_client_endpoints(self):
        result = required_underlay_endpoints(
            self.plan("0.0.0.0/0"),
            (
                IPv4Address("198.51.100.10"),
                IPv4Address("203.0.113.20"),
            ),
        )
        self.assertEqual(
            result,
            (
                IPv4Address("198.51.100.10"),
                IPv4Address("203.0.113.20"),
            ),
        )

    def test_narrow_bootstrap_pins_only_endpoints_it_captures(self):
        result = required_underlay_endpoints(
            self.plan("10.0.0.0/8"),
            (
                IPv4Address("10.1.2.3"),
                IPv4Address("198.51.100.10"),
            ),
        )
        self.assertEqual(result, (IPv4Address("10.1.2.3"),))

    def test_global_capture_is_not_profile_local(self):
        plan = build_host_boundary_policy(
            (
                HostBoundaryProfileIntent(
                    profile_id="full",
                    direction=Direction.OUTBOUND,
                    destinations=(IPv4Network("0.0.0.0/0"),),
                ),
                HostBoundaryProfileIntent(
                    profile_id="other",
                    direction=Direction.INBOUND,
                    destinations=(IPv4Network("10.0.0.0/8"),),
                ),
            )
        )
        result = required_underlay_endpoints(
            plan,
            (IPv4Address("198.51.100.10"),),
        )
        self.assertEqual(result, (IPv4Address("198.51.100.10"),))

    def test_exact_bootstrap_destination_equal_to_transport_endpoint_is_rejected(self):
        with self.assertRaises(UnderlayEndpointPayloadConflict):
            required_underlay_endpoints(
                self.plan("198.51.100.10/32"),
                (IPv4Address("198.51.100.10"),),
            )

    def test_no_bootstrap_route_means_no_pin(self):
        plan = build_host_boundary_policy(
            (
                HostBoundaryProfileIntent(
                    profile_id="in",
                    direction=Direction.INBOUND,
                    destinations=(IPv4Network("10.0.0.0/8"),),
                ),
            )
        )
        self.assertEqual(
            required_underlay_endpoints(
                plan,
                (IPv4Address("10.1.2.3"),),
            ),
            (),
        )


if __name__ == "__main__":
    unittest.main()
