from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.network_rules import (
    EndpointKind,
    IcmpType,
    PredicateKind,
    TrafficProtocol,
)
from rou.probe_rules import (
    AvailabilityProbeRequest,
    AvailabilityProbeSetRequest,
    ProbeRulesCalculator,
)


class ProbeRulesCalculatorTests(unittest.TestCase):
    def test_icmp_probe_derives_isolated_local_process_rules(self):
        path = InterfaceIdentity("vpns00", 43)
        request = AvailabilityProbeSetRequest(
            (
                AvailabilityProbeRequest(
                    "profile-a:vpns00",
                    path,
                    IPv4Address("172.21.201.19"),
                ),
            )
        )

        rules = ProbeRulesCalculator().calculate(request)

        self.assertEqual(len(rules.routing_domains), 1)
        domain = rules.routing_domains[0]
        self.assertEqual(domain.name, "profile-a:vpns00")
        self.assertEqual(
            domain.destinations,
            (IPv4Network("172.21.201.19/32"),),
        )
        self.assertEqual(domain.ordered_paths, (path,))

        dispatch = rules.dispatch_rules[0]
        self.assertIs(dispatch.source.kind, EndpointKind.LOCAL_PROCESS)
        self.assertEqual(dispatch.bound_output.interface, path)
        self.assertIs(dispatch.protocol, TrafficProtocol.ICMP)

        self.assertEqual(len(rules.traffic_allows), 2)
        outbound, inbound = rules.traffic_allows
        self.assertIs(outbound.source.kind, EndpointKind.LOCAL_PROCESS)
        self.assertEqual(outbound.destination.interface, path)
        self.assertEqual(
            outbound.predicate.selector.icmp_types,
            (IcmpType.ECHO_REQUEST,),
        )
        self.assertEqual(inbound.source.interface, path)
        self.assertIs(inbound.destination.kind, EndpointKind.LOCAL_PROCESS)
        self.assertEqual(
            inbound.predicate.selector.icmp_types,
            (IcmpType.ECHO_REPLY,),
        )

        self.assertEqual(len(rules.flow_initiation_allows), 1)
        self.assertEqual(
            rules.flow_initiation_allows[0],
            rules.flow_initiation_allows[0],
        )
        self.assertEqual(rules.source_nat, ())

    def test_multiple_same_target_probes_keep_distinct_bound_paths(self):
        target = IPv4Address("172.21.201.19")
        first = InterfaceIdentity("vpns00", 43)
        second = InterfaceIdentity("vpns01", 45)

        rules = ProbeRulesCalculator().calculate(
            AvailabilityProbeSetRequest(
                (
                    AvailabilityProbeRequest("pri", first, target),
                    AvailabilityProbeRequest("sec", second, target),
                )
            )
        )

        self.assertEqual(
            [item.bound_output.interface for item in rules.dispatch_rules],
            [first, second],
        )

    def test_duplicate_probe_id_is_rejected(self):
        path = InterfaceIdentity("vpns00", 43)
        with self.assertRaisesRegex(ValueError, "duplicate probe_id"):
            AvailabilityProbeSetRequest(
                (
                    AvailabilityProbeRequest(
                        "same",
                        path,
                        IPv4Address("192.0.2.1"),
                    ),
                    AvailabilityProbeRequest(
                        "same",
                        path,
                        IPv4Address("192.0.2.2"),
                    ),
                )
            )


if __name__ == "__main__":
    unittest.main()
