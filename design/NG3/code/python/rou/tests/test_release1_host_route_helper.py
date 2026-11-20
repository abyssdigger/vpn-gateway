import unittest
from ipaddress import IPv4Interface

from rou.linux_policy_platform import NG3_PEACEFUL_HOST_ROUTING_LINUX_ALLOCATION
from rou.managed_network_domain import ManagedNetworkDomainSpec
from rou.release1_config import parse_release1_config
from rou.release1_host_route_helper import (
    build_release1_peaceful_host_routing_desired,
    helper_routing_uses_external_ingress,
    validate_release1_helper_routing_scope,
)


DOMAIN = ManagedNetworkDomainSpec(
    namespace="vpng-stack",
    host_interface="vpng0",
    inner_interface="stack0",
    inner_address=IPv4Interface("198.19.255.2/32"),
)

PROFILE = """
default_snat_address = "198.19.255.10"

[device.vpn]
enabled = true
expected_interfaces = ["vpn0"]

[profile.remote]
enabled = true
direction = "inbound+snat"
destinations = ["10.30.0.0/16"]
device_order = ["vpn"]
"""


class Release1HostRouteHelperTests(unittest.TestCase):
    def test_default_none_builds_no_host_contribution(self):
        cfg = parse_release1_config(PROFILE)
        self.assertIsNone(
            build_release1_peaceful_host_routing_desired(cfg, DOMAIN)
        )

    def test_local_and_exact_ingress_build_scoped_dispatch_union(self):
        cfg = parse_release1_config(
            'helper_routing_interfaces = ":local,eth0"\n' + PROFILE
        )
        desired = build_release1_peaceful_host_routing_desired(cfg, DOMAIN)
        self.assertIsNotNone(desired)
        self.assertEqual(
            [route.destination.with_prefixlen for route in desired.routes],
            ["198.19.255.10/32", "10.30.0.0/16"],
        )
        self.assertEqual(
            [
                (rule.incoming_interface, rule.invert_incoming_interface)
                for rule in desired.dispatch_rules
            ],
            [("lo", False), ("eth0", False)],
        )
        self.assertEqual(
            [rule.priority for rule in desired.dispatch_rules],
            [
                NG3_PEACEFUL_HOST_ROUTING_LINUX_ALLOCATION.dispatch_priority,
                NG3_PEACEFUL_HOST_ROUTING_LINUX_ALLOCATION.dispatch_priority + 1,
            ],
        )
        self.assertIsNotNone(desired.preserve_main)
        self.assertIsNotNone(desired.scope_exit)
        self.assertEqual(desired.bypass.goto_priority, desired.scope_exit.priority)
        snat = desired.routes[0]
        self.assertEqual(str(snat.gateway), "198.19.255.2")
        self.assertTrue(snat.onlink)

    def test_external_and_any_lower_to_expected_rpdb_selectors(self):
        external = build_release1_peaceful_host_routing_desired(
            parse_release1_config(
                'helper_routing_interfaces = ":external"\n' + PROFILE
            ),
            DOMAIN,
        )
        self.assertEqual(
            (
                external.dispatch.incoming_interface,
                external.dispatch.invert_incoming_interface,
            ),
            ("lo", True),
        )
        any_scope = build_release1_peaceful_host_routing_desired(
            parse_release1_config(
                'helper_routing_interfaces = ":any"\n' + PROFILE
            ),
            DOMAIN,
        )
        self.assertEqual(
            (
                any_scope.dispatch.incoming_interface,
                any_scope.dispatch.invert_incoming_interface,
            ),
            (None, False),
        )

    def test_managed_boundary_is_rejected_by_pre_mutation_scope_validation(self):
        cfg = parse_release1_config(
            'helper_routing_interfaces = "vpng0"\n' + PROFILE
        )
        with self.assertRaisesRegex(ValueError, "managed HOST<->STACK boundary"):
            validate_release1_helper_routing_scope(cfg, DOMAIN)
        with self.assertRaisesRegex(ValueError, "managed HOST<->STACK boundary"):
            build_release1_peaceful_host_routing_desired(cfg, DOMAIN)

    def test_external_forwarding_prerequisite_detection_is_scope_only(self):
        self.assertFalse(
            helper_routing_uses_external_ingress(
                parse_release1_config(
                    'helper_routing_interfaces = ":local"'
                )
            )
        )
        self.assertFalse(
            helper_routing_uses_external_ingress(
                parse_release1_config(
                    'helper_routing_interfaces = "lo"'
                )
            )
        )
        for value in (":external", ":any", "eth0", ":local,eth0"):
            with self.subTest(value=value):
                self.assertTrue(
                    helper_routing_uses_external_ingress(
                        parse_release1_config(
                            f'helper_routing_interfaces = "{value}"'
                        )
                    )
                )


if __name__ == "__main__":
    unittest.main()
