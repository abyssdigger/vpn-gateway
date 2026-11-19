from ipaddress import IPv4Address
import unittest

from rou.alpha_runtime import AlphaPreparedPolicy
from rou.host_publication_policy import HostPublicationSelectorKind
from rou.interface_identity import InterfaceIdentity
from rou.payload_routing_desired import ManagedRouteType


CONFIG = """
[device.ovpn]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false
allow_vpn_client = "udp:11941>198.19.254.2:11940"

[profile.alpha]
enabled = true
direction = "outbound"
destinations = ["10.253.0.1/32"]
device_order = ["ovpn"]
"""


class AlphaPreparedPolicyTests(unittest.TestCase):
    def test_zero_path_is_fail_closed_but_admits_vpn_transport(self):
        prepared = AlphaPreparedPolicy.from_text(
            CONFIG,
            local_address=IPv4Address("198.19.255.2"),
        )
        host_boundary = InterfaceIdentity("vnga-inner0", 7)
        desired = prepared.build_current(
            host_boundary,
            (
                InterfaceIdentity("lo", 1),
                host_boundary,
            ),
        )

        self.assertEqual(len(desired.routing.rules), 1)
        self.assertEqual(len(desired.routing.routes), 1)
        self.assertIs(
            desired.routing.routes[0].route_type,
            ManagedRouteType.BLACKHOLE,
        )
        self.assertEqual(desired.nft.profile_forward.rules, ())
        self.assertEqual(desired.nft.payload_nat.masquerade_rules, ())
        self.assertEqual(len(desired.nft.local_integration.rules), 2)
        self.assertEqual(desired.nft.device_firewall.chains, ())

    def test_new_exact_vpn_endpoint_becomes_current_path_without_nat(self):
        prepared = AlphaPreparedPolicy.from_text(
            CONFIG,
            local_address=IPv4Address("198.19.255.2"),
        )
        host_boundary = InterfaceIdentity("vnga-inner0", 7)
        prepared.build_current(
            host_boundary,
            (
                InterfaceIdentity("lo", 1),
                host_boundary,
            ),
        )

        vpn0 = InterfaceIdentity("vpn0", 11)
        desired = prepared.build_current(
            host_boundary,
            (
                InterfaceIdentity("lo", 1),
                host_boundary,
                vpn0,
            ),
        )

        unicast = tuple(
            route
            for route in desired.routing.routes
            if route.route_type is ManagedRouteType.UNICAST
        )
        self.assertEqual(len(unicast), 1)
        self.assertEqual(unicast[0].endpoint, vpn0)
        self.assertEqual(str(unicast[0].destination), "10.253.0.1/32")
        self.assertEqual(desired.nft.payload_nat.masquerade_rules, ())
        self.assertEqual(len(desired.nft.profile_forward.rules), 2)
        self.assertEqual(len(desired.nft.local_integration.rules), 2)

    def test_inbound_current_path_materializes_stack_return_affinity(self):
        config = CONFIG.replace(
            'direction = "outbound"',
            'direction = "inbound"',
        ).replace(
            'use_outbound_nat = false\n',
            '',
        )
        prepared = AlphaPreparedPolicy.from_text(
            config,
            local_address=IPv4Address("198.19.255.2"),
        )
        host_boundary = InterfaceIdentity("vnga-inner0", 7)
        vpn0 = InterfaceIdentity("vpn0", 11)
        desired = prepared.build_current(
            host_boundary,
            (InterfaceIdentity("lo", 1), host_boundary, vpn0),
        )
        self.assertIsNotNone(desired.stack_return_affinity)
        self.assertEqual(len(desired.stack_return_affinity.classifiers), 1)
        self.assertEqual(len(desired.stack_return_affinity.rules), 1)

    def test_legacy_integration_object_is_rejected(self):
        with self.assertRaisesRegex(Exception, "top level has unsupported"):
            AlphaPreparedPolicy.from_text(
                CONFIG
                + """
[integration.legacy]
device = "ovpn"
protocol = "udp"
remote_ipv4 = "198.19.254.2"
remote_port = 11940
""",
                local_address=IPv4Address("198.19.255.2"),
            )

    def test_alpha_rejects_canonical_features_not_yet_materialized(self):
        with self.assertRaisesRegex(Exception, "availability_check"):
            AlphaPreparedPolicy.from_text(
                CONFIG.replace(
                    'device_order = ["ovpn"]',
                    'device_order = ["ovpn"]\n'
                    '[profile.alpha.availability_check]\n'
                    'mechanism = "icmp"\n'
                    'target = "10.253.0.1"',
                ),
                local_address=IPv4Address("198.19.255.2"),
            )

        with self.assertRaisesRegex(Exception, r"requests \+snat"):
            AlphaPreparedPolicy.from_text(
                CONFIG.replace(
                    'direction = "outbound"',
                    'direction = "inbound+snat"',
                ).replace(
                    'use_outbound_nat = false\n',
                    "",
                ),
                local_address=IPv4Address("198.19.255.2"),
            )

        route_return = AlphaPreparedPolicy.from_text(
            CONFIG.replace(
                'direction = "outbound"',
                'direction = "inbound+route-return"',
            ).replace(
                'use_outbound_nat = false\n',
                "",
            ),
            local_address=IPv4Address("198.19.255.2"),
        )
        self.assertTrue(route_return.config.profiles["alpha"].route_return)

    def test_alpha_materializes_canonical_server_publication_both_halves(self):
        replacement = (
            'use_outbound_nat = false\n'
            'publish_vpn_server = [\n'
            '    "tcp/eth0:443,8000-8001>8443,18000-18001",\n'
            '    "udp:53",\n'
            ']\n'
        )
        prepared = AlphaPreparedPolicy.from_text(
            CONFIG.replace("use_outbound_nat = false\n", replacement),
            local_address=IPv4Address("198.19.255.2"),
        )
        host_boundary = InterfaceIdentity("vnga-inner0", 7)
        desired = prepared.build_current(
            host_boundary,
            (InterfaceIdentity("lo", 1), host_boundary),
        )
        self.assertEqual(len(desired.nft.local_publication.rules), 8)

        host = prepared.build_host_publication_desired()
        self.assertEqual(len(host.rules), 4)
        first = next(rule for rule in host.rules if rule.host_port == 443)
        self.assertIs(first.selector_kind, HostPublicationSelectorKind.INTERFACE)
        self.assertEqual(first.selector_value, "eth0")
        self.assertEqual(first.internal_port, 8443)
        self.assertEqual(str(first.internal_address), "198.19.255.2")
        udp = next(rule for rule in host.rules if rule.protocol.value == "udp")
        self.assertIs(udp.selector_kind, HostPublicationSelectorKind.ANY)
        self.assertEqual(udp.host_port, 53)
        self.assertEqual(udp.internal_port, 53)

    def test_alpha_rejects_ambiguous_server_publication_projection(self):
        replacement = (
            'use_outbound_nat = false\n'
            'publish_vpn_server = [\n'
            '    "tcp:443>8443",\n'
            '    "tcp/198.51.100.10:443>9443",\n'
            ']\n'
        )
        with self.assertRaisesRegex(
            Exception,
            "host publication projection failed before runtime mutation",
        ):
            AlphaPreparedPolicy.from_text(
                CONFIG.replace("use_outbound_nat = false\n", replacement),
                local_address=IPv4Address("198.19.255.2"),
            )

    def test_alpha_materializes_canonical_device_nat_and_firewall(self):
        prepared = AlphaPreparedPolicy.from_text(
            CONFIG.replace(
                "use_outbound_nat = false",
                """use_outbound_nat = true
firewall = [
    "out allow icmp to 10.253.0.1/32",
]""",
            ),
            local_address=IPv4Address("198.19.255.2"),
        )
        host_boundary = InterfaceIdentity("vnga-inner0", 7)
        vpn0 = InterfaceIdentity("vpn0", 11)
        desired = prepared.build_current(
            host_boundary,
            (InterfaceIdentity("lo", 1), host_boundary, vpn0),
        )
        self.assertEqual(len(desired.nft.payload_nat.masquerade_rules), 1)
        self.assertEqual(len(desired.nft.device_firewall.chains), 2)


if __name__ == "__main__":
    unittest.main()
