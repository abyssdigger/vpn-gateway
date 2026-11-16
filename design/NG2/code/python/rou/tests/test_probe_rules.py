from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.availability_probe_policy import AvailabilityProbePolicy
from rou.interface_identity import InterfaceIdentity
from rou.network_rules import (
    EndpointKind,
    IcmpType,
    TrafficProtocol,
)
from rou.probe_rules import (
    AvailabilityProbeRequest,
    AvailabilityProbeSetRequest,
    ProbeRulesCalculator,
    availability_probe_sets_semantically_equal,
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
        self.assertEqual(
            domain.name,
            "probe:icmp:vpns00:43:172.21.201.19",
        )
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
            outbound.predicate.selector.destination,
            IPv4Network("172.21.201.19/32"),
        )
        self.assertEqual(
            outbound.predicate.selector.icmp_types,
            (IcmpType.ECHO_REQUEST,),
        )
        self.assertEqual(inbound.source.interface, path)
        self.assertIs(inbound.destination.kind, EndpointKind.LOCAL_PROCESS)
        self.assertEqual(
            inbound.predicate.selector.source,
            IPv4Network("172.21.201.19/32"),
        )
        self.assertEqual(
            inbound.predicate.selector.icmp_types,
            (IcmpType.ECHO_REPLY,),
        )

        self.assertEqual(len(rules.flow_initiation_allows), 1)
        initiation = rules.flow_initiation_allows[0]
        self.assertIs(initiation.source.kind, EndpointKind.LOCAL_PROCESS)
        self.assertEqual(initiation.destination.interface, path)
        self.assertEqual(
            initiation.predicate.selector.icmp_types,
            (IcmpType.ECHO_REQUEST,),
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

    def test_same_physical_probe_plane_is_deduplicated_across_logical_ids(self):
        target = IPv4Address("172.21.201.19")
        path = InterfaceIdentity("vpns00", 43)

        first = AvailabilityProbeSetRequest(
            (
                AvailabilityProbeRequest("profile-a", path, target),
                AvailabilityProbeRequest("profile-b", path, target),
            )
        )
        second = AvailabilityProbeSetRequest(tuple(reversed(first.probes)))

        first_rules = ProbeRulesCalculator().calculate(first)
        second_rules = ProbeRulesCalculator().calculate(second)

        self.assertEqual(first_rules, second_rules)
        self.assertEqual(len(first_rules.routing_domains), 1)
        self.assertEqual(len(first_rules.dispatch_rules), 1)
        self.assertEqual(len(first_rules.traffic_allows), 2)
        self.assertEqual(len(first_rules.flow_initiation_allows), 1)


    def test_probe_set_semantic_equality_ignores_tuple_order(self):
        target = IPv4Address("172.21.201.19")
        first_path = InterfaceIdentity("vpns00", 43)
        second_path = InterfaceIdentity("vpns01", 45)

        first = AvailabilityProbeSetRequest(
            (
                AvailabilityProbeRequest("pri", first_path, target),
                AvailabilityProbeRequest("sec", second_path, target),
            )
        )
        reordered = AvailabilityProbeSetRequest(tuple(reversed(first.probes)))

        self.assertTrue(
            availability_probe_sets_semantically_equal(first, reordered)
        )

    def test_probe_set_semantic_equality_detects_logical_change(self):
        path = InterfaceIdentity("vpns00", 43)
        first = AvailabilityProbeSetRequest(
            (
                AvailabilityProbeRequest(
                    "probe",
                    path,
                    IPv4Address("192.0.2.1"),
                ),
            )
        )
        changed = AvailabilityProbeSetRequest(
            (
                AvailabilityProbeRequest(
                    "probe",
                    path,
                    IPv4Address("192.0.2.2"),
                ),
            )
        )

        self.assertFalse(
            availability_probe_sets_semantically_equal(first, changed)
        )

    def test_policy_change_is_logical_but_not_physical_rules_change(self):
        path = InterfaceIdentity("vpns00", 43)
        target = IPv4Address("192.0.2.1")
        first = AvailabilityProbeSetRequest(
            (
                AvailabilityProbeRequest(
                    "probe",
                    path,
                    target,
                    policy=AvailabilityProbePolicy(
                        interval_seconds=10,
                        retry_interval_seconds=1,
                        timeout_seconds=1,
                    ),
                ),
            )
        )
        changed = AvailabilityProbeSetRequest(
            (
                AvailabilityProbeRequest(
                    "probe",
                    path,
                    target,
                    policy=AvailabilityProbePolicy(
                        interval_seconds=30,
                        retry_interval_seconds=2,
                        timeout_seconds=1,
                    ),
                ),
            )
        )

        self.assertFalse(
            availability_probe_sets_semantically_equal(first, changed)
        )
        self.assertEqual(
            ProbeRulesCalculator().calculate(first),
            ProbeRulesCalculator().calculate(changed),
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
