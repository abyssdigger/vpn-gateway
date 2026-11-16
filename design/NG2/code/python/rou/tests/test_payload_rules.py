from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.network_rules import (
    EndpointKind,
    PacketView,
    SourceNatTarget,
    TrafficProtocol,
)
from rou.payload_rules import (
    EnvelopeAction,
    EnvelopeDirection,
    PayloadDirection,
    PayloadNatMode,
    PayloadPath,
    PayloadPortRange,
    PayloadProfileRequest,
    PayloadProtocol,
    PayloadRulesCalculator,
    PayloadTrafficSelector,
    PayloadTrafficStateRequest,
    TrafficEnvelope,
    TrafficEnvelopeRule,
)


class PayloadRulesCalculatorTests(unittest.TestCase):
    def _calculate(self, *profiles: PayloadProfileRequest):
        return PayloadRulesCalculator().calculate(
            PayloadTrafficStateRequest(profiles)
        )

    def test_preserves_ordered_paths_without_host_interface_leak(self):
        profile = PayloadProfileRequest(
            "profile-a",
            PayloadDirection.OUTBOUND,
            (IPv4Network("10.0.0.0/8"),),
            (
                PayloadPath(InterfaceIdentity("vpns00", 10)),
                PayloadPath(InterfaceIdentity("vpns01", 11)),
            ),
        )

        spec = self._calculate(profile)

        self.assertEqual(
            [
                (item.ifname, item.ifindex)
                for item in spec.routing_domains[0].ordered_paths
            ],
            [("vpns00", 10), ("vpns01", 11)],
        )
        self.assertIs(
            spec.dispatch_rules[0].source.kind,
            EndpointKind.LOCAL_NETWORK,
        )
        self.assertIsNone(spec.dispatch_rules[0].source.interface)

    def test_zero_path_keeps_terminal_fail_close(self):
        profile = PayloadProfileRequest(
            "profile-a",
            PayloadDirection.OUTBOUND,
            (IPv4Network("10.0.0.0/8"),),
            (),
        )

        spec = self._calculate(profile)

        self.assertEqual(spec.routing_domains[0].ordered_paths, ())
        self.assertEqual(spec.traffic_allows, ())
        self.assertEqual(spec.flow_initiation_allows, ())

    def test_dispatch_is_longest_prefix_first(self):
        broad = PayloadProfileRequest(
            "broad",
            PayloadDirection.OUTBOUND,
            (IPv4Network("10.0.0.0/8"),),
            (),
        )
        narrow = PayloadProfileRequest(
            "narrow",
            PayloadDirection.OUTBOUND,
            (IPv4Network("10.1.0.0/16"),),
            (),
        )

        spec = self._calculate(broad, narrow)

        self.assertEqual(
            [str(item.destination) for item in spec.dispatch_rules],
            ["10.1.0.0/16", "10.0.0.0/8"],
        )

    def test_same_destination_in_two_profiles_is_ambiguous(self):
        first = PayloadProfileRequest(
            "first",
            PayloadDirection.OUTBOUND,
            (IPv4Network("10.0.0.0/8"),),
            (),
        )
        second = PayloadProfileRequest(
            "second",
            PayloadDirection.OUTBOUND,
            (IPv4Network("10.0.0.0/8"),),
            (),
        )

        with self.assertRaises(ValueError):
            self._calculate(first, second)

    def test_outbound_allows_return_traffic_but_not_remote_initiation(self):
        profile = PayloadProfileRequest(
            "profile-a",
            PayloadDirection.OUTBOUND,
            (IPv4Network("10.0.0.0/8"),),
            (PayloadPath(InterfaceIdentity("vpns00", 10)),),
        )

        spec = self._calculate(profile)

        self.assertEqual(len(spec.traffic_allows), 2)
        self.assertEqual(len(spec.flow_initiation_allows), 1)
        flow = spec.flow_initiation_allows[0]
        self.assertIs(flow.source.kind, EndpointKind.LOCAL_NETWORK)
        self.assertIs(flow.destination.kind, EndpointKind.INTERFACE)

    def test_default_allow_envelope_drop_restricts_return_bytes(self):
        envelope = TrafficEnvelope(
            EnvelopeAction.ALLOW,
            (
                TrafficEnvelopeRule(
                    EnvelopeDirection.FROM_PATH,
                    EnvelopeAction.DROP,
                    PayloadTrafficSelector(
                        source=IPv4Network("10.20.0.0/16"),
                        protocol=PayloadProtocol.TCP,
                        destination_ports=(
                            PayloadPortRange(8007, 8007),
                        ),
                    ),
                ),
            ),
        )
        profile = PayloadProfileRequest(
            "profile-a",
            PayloadDirection.OUTBOUND,
            (IPv4Network("10.0.0.0/8"),),
            (
                PayloadPath(
                    InterfaceIdentity("vpns00", 10),
                    envelope,
                ),
            ),
        )

        spec = self._calculate(profile)
        reverse = next(
            item
            for item in spec.traffic_allows
            if item.source.kind is EndpointKind.INTERFACE
        )

        blocked = PacketView(
            IPv4Address("10.20.1.2"),
            IPv4Address("192.168.1.10"),
            TrafficProtocol.TCP,
            source_port=50000,
            destination_port=8007,
        )
        allowed = PacketView(
            IPv4Address("10.20.1.2"),
            IPv4Address("192.168.1.10"),
            TrafficProtocol.TCP,
            source_port=50000,
            destination_port=443,
        )

        self.assertFalse(reverse.predicate.matches(blocked))
        self.assertTrue(reverse.predicate.matches(allowed))

    def test_default_drop_envelope_allow_limits_outbound_flow(self):
        envelope = TrafficEnvelope(
            EnvelopeAction.DROP,
            (
                TrafficEnvelopeRule(
                    EnvelopeDirection.TO_PATH,
                    EnvelopeAction.ALLOW,
                    PayloadTrafficSelector(
                        destination=IPv4Network("10.0.0.0/8"),
                        protocol=PayloadProtocol.UDP,
                        destination_ports=(PayloadPortRange(53, 53),),
                    ),
                ),
            ),
        )
        profile = PayloadProfileRequest(
            "profile-a",
            PayloadDirection.OUTBOUND,
            (IPv4Network("10.0.0.0/8"),),
            (
                PayloadPath(
                    InterfaceIdentity("vpns00", 10),
                    envelope,
                ),
            ),
        )

        spec = self._calculate(profile)
        flow = spec.flow_initiation_allows[0]

        dns = PacketView(
            IPv4Address("192.168.1.10"),
            IPv4Address("10.1.2.3"),
            TrafficProtocol.UDP,
            source_port=50000,
            destination_port=53,
        )
        other = PacketView(
            IPv4Address("192.168.1.10"),
            IPv4Address("10.1.2.3"),
            TrafficProtocol.UDP,
            source_port=50000,
            destination_port=123,
        )

        self.assertTrue(flow.predicate.matches(dns))
        self.assertFalse(flow.predicate.matches(other))

    def test_envelope_rules_preserve_first_match_order(self):
        envelope = TrafficEnvelope(
            EnvelopeAction.DROP,
            (
                TrafficEnvelopeRule(
                    EnvelopeDirection.TO_PATH,
                    EnvelopeAction.ALLOW,
                    PayloadTrafficSelector(
                        destination=IPv4Network("10.0.0.0/8"),
                        protocol=PayloadProtocol.TCP,
                        destination_ports=(PayloadPortRange(443, 443),),
                    ),
                ),
                TrafficEnvelopeRule(
                    EnvelopeDirection.TO_PATH,
                    EnvelopeAction.DROP,
                    PayloadTrafficSelector(
                        destination=IPv4Network("10.1.0.0/16"),
                        protocol=PayloadProtocol.TCP,
                        destination_ports=(PayloadPortRange(443, 443),),
                    ),
                ),
            ),
        )
        profile = PayloadProfileRequest(
            "profile-a",
            PayloadDirection.OUTBOUND,
            (IPv4Network("10.0.0.0/8"),),
            (
                PayloadPath(
                    InterfaceIdentity("vpns00", 10),
                    envelope,
                ),
            ),
        )

        spec = self._calculate(profile)
        flow = spec.flow_initiation_allows[0]
        packet = PacketView(
            IPv4Address("192.168.1.10"),
            IPv4Address("10.1.2.3"),
            TrafficProtocol.TCP,
            source_port=50000,
            destination_port=443,
        )

        self.assertTrue(flow.predicate.matches(packet))

    def test_narrow_profile_prevents_broad_allow_from_widening_policy(self):
        path = PayloadPath(InterfaceIdentity("vpns00", 10))
        broad = PayloadProfileRequest(
            "broad",
            PayloadDirection.OUTBOUND,
            (IPv4Network("10.0.0.0/8"),),
            (path,),
        )
        narrow = PayloadProfileRequest(
            "narrow",
            PayloadDirection.INBOUND,
            (IPv4Network("10.1.0.0/16"),),
            (path,),
        )

        spec = self._calculate(broad, narrow)

        outbound_rules = [
            item
            for item in spec.flow_initiation_allows
            if item.source.kind is EndpointKind.LOCAL_NETWORK
        ]
        broad_packet = PacketView(
            IPv4Address("192.168.1.10"),
            IPv4Address("10.2.3.4"),
            TrafficProtocol.TCP,
            source_port=50000,
            destination_port=443,
        )
        narrow_packet = PacketView(
            IPv4Address("192.168.1.10"),
            IPv4Address("10.1.2.3"),
            TrafficProtocol.TCP,
            source_port=50000,
            destination_port=443,
        )

        self.assertTrue(
            any(rule.predicate.matches(broad_packet) for rule in outbound_rules)
        )
        self.assertFalse(
            any(rule.predicate.matches(narrow_packet) for rule in outbound_rules)
        )

    def test_nat_none_emits_no_source_translation(self):
        profile = PayloadProfileRequest(
            "profile-a",
            PayloadDirection.OUTBOUND,
            (IPv4Network("10.0.0.0/8"),),
            (PayloadPath(InterfaceIdentity("vpns00", 10)),),
        )

        spec = self._calculate(profile)

        self.assertEqual(spec.source_nat, ())

    def test_masquerade_maps_to_egress_address_translation(self):
        profile = PayloadProfileRequest(
            "profile-a",
            PayloadDirection.OUTBOUND,
            (IPv4Network("10.0.0.0/8"),),
            (
                PayloadPath(
                    InterfaceIdentity("vpns00", 10),
                    nat_mode=PayloadNatMode.MASQUERADE,
                ),
            ),
        )

        spec = self._calculate(profile)

        self.assertEqual(len(spec.source_nat), 1)
        rule = spec.source_nat[0]
        self.assertIs(rule.target, SourceNatTarget.EGRESS_ADDRESS)
        self.assertEqual(rule.egress.interface, InterfaceIdentity("vpns00", 10))

    def test_broad_nat_does_not_capture_more_specific_profile(self):
        broad = PayloadProfileRequest(
            "broad",
            PayloadDirection.OUTBOUND,
            (IPv4Network("10.0.0.0/8"),),
            (
                PayloadPath(
                    InterfaceIdentity("vpns00", 10),
                    nat_mode=PayloadNatMode.MASQUERADE,
                ),
            ),
        )
        narrow = PayloadProfileRequest(
            "narrow",
            PayloadDirection.OUTBOUND,
            (IPv4Network("10.1.0.0/16"),),
            (PayloadPath(InterfaceIdentity("vpns01", 11)),),
        )

        spec = self._calculate(broad, narrow)
        packet = PacketView(
            IPv4Address("192.168.1.10"),
            IPv4Address("10.1.2.3"),
            TrafficProtocol.TCP,
            source_port=50000,
            destination_port=443,
        )

        self.assertEqual(len(spec.source_nat), 1)
        self.assertFalse(spec.source_nat[0].predicate.matches(packet))

    def test_same_name_new_ifindex_remains_distinct(self):
        profile = PayloadProfileRequest(
            "profile-a",
            PayloadDirection.OUTBOUND,
            (IPv4Network("10.0.0.0/8"),),
            (
                PayloadPath(InterfaceIdentity("vpns00", 10)),
                PayloadPath(InterfaceIdentity("vpns00", 11)),
            ),
        )

        spec = self._calculate(profile)

        self.assertEqual(
            [item.ifindex for item in spec.routing_domains[0].ordered_paths],
            [10, 11],
        )


if __name__ == "__main__":
    unittest.main()
