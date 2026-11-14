from ipaddress import IPv4Network
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.linux_nft import (
    InterfaceRefKind,
    LinuxNftError,
    compile_nft_filter_desired,
    compile_nft_nat_desired,
)
from rou.network_rules import (
    FlowInitiationAllowSpec,
    NetworkEndpoint,
    NetworkRulesSpec,
    PortRange,
    SourceNatSpec,
    SourceNatTarget,
    TrafficAllowSpec,
    TrafficPredicate,
    TrafficProtocol,
    TrafficSelector,
)
from rou.network_rules_composition import (
    OwnedNetworkRules,
    OwnerToken,
    compose_network_rules,
)


LOCAL = NetworkEndpoint.local_network()


def _path(name: str, ifindex: int) -> NetworkEndpoint:
    return NetworkEndpoint.interface_path(
        InterfaceIdentity(name, ifindex)
    )


def _owned(
    token: int,
    *,
    traffic=(),
    flows=(),
) -> OwnedNetworkRules:
    return OwnedNetworkRules(
        OwnerToken(token),
        NetworkRulesSpec(
            traffic_allows=tuple(traffic),
            flow_initiation_allows=tuple(flows),
        ),
    )


class LinuxNftFilterTests(unittest.TestCase):
    def test_numeric_ifindex_and_marker_are_generation_aware(self):
        path = _path("vpns00", 10)
        allow = TrafficAllowSpec(
            LOCAL,
            path,
            TrafficPredicate.always(),
        )
        flow = FlowInitiationAllowSpec(
            LOCAL,
            path,
            TrafficPredicate.always(),
        )

        desired = compile_nft_filter_desired(
            compose_network_rules(
                (_owned(1, traffic=(allow,), flows=(flow,)),)
            ),
            local_interface="host0",
        )

        self.assertIn('iifname "host0" oif 10', desired.definition)
        self.assertNotIn('oifname "vpns00"', desired.definition)
        self.assertTrue(
            any(
                marker.interface_ref.kind is InterfaceRefKind.OIF
                and marker.interface_ref.ifindex == 10
                for marker in desired.markers
            )
        )

    def test_established_policy_uses_union_of_owner_traffic_allows(self):
        first = TrafficAllowSpec(
            LOCAL,
            _path("vpns00", 10),
            TrafficPredicate.always(),
        )
        second = TrafficAllowSpec(
            LOCAL,
            _path("vpns01", 11),
            TrafficPredicate.always(),
        )

        desired = compile_nft_filter_desired(
            compose_network_rules(
                (
                    _owned(1, traffic=(first,)),
                    _owned(2, traffic=(second,)),
                )
            ),
            local_interface="host0",
        )

        traffic_section = desired.definition.split(
            "chain traffic_bytes {", 1
        )[1].split("}", 1)[0]
        self.assertIn("oif 10", traffic_section)
        self.assertIn("oif 11", traffic_section)

    def test_new_flow_does_not_cross_compose_different_owners(self):
        path = _path("vpns00", 10)
        traffic_only = _owned(
            1,
            traffic=(
                TrafficAllowSpec(
                    LOCAL,
                    path,
                    TrafficPredicate.always(),
                ),
            ),
        )
        flow_only = _owned(
            2,
            flows=(
                FlowInitiationAllowSpec(
                    LOCAL,
                    path,
                    TrafficPredicate.always(),
                ),
            ),
        )

        desired = compile_nft_filter_desired(
            compose_network_rules((traffic_only, flow_only)),
            local_interface="host0",
        )

        new_section = desired.definition.split(
            "chain new_flows {", 1
        )[1].split("}", 1)[0]
        self.assertNotIn("return", new_section)

    def test_new_flow_intersects_traffic_and_flow_predicates_within_owner(self):
        path = _path("vpns00", 10)
        traffic = TrafficAllowSpec(
            LOCAL,
            path,
            TrafficPredicate.match(
                TrafficSelector(
                    destination=IPv4Network("10.0.0.0/8"),
                )
            ),
        )
        flow = FlowInitiationAllowSpec(
            LOCAL,
            path,
            TrafficPredicate.match(
                TrafficSelector(
                    protocol=TrafficProtocol.TCP,
                    destination_ports=(PortRange(443, 443),),
                )
            ),
        )

        desired = compile_nft_filter_desired(
            compose_network_rules(
                (_owned(1, traffic=(traffic,), flows=(flow,)),)
            ),
            local_interface="host0",
        )

        new_section = desired.definition.split(
            "chain new_flows {", 1
        )[1].split("}", 1)[0]
        self.assertIn("ip daddr 10.0.0.0/8", new_section)
        self.assertIn("ip protocol tcp", new_section)
        self.assertIn("tcp dport 443", new_section)

    def test_default_allow_exception_predicate_compiles_negation(self):
        path = _path("vpns00", 10)
        blocked = TrafficPredicate.match(
            TrafficSelector(
                destination=IPv4Network("10.20.0.0/16"),
                protocol=TrafficProtocol.TCP,
                destination_ports=(PortRange(8007, 8007),),
            )
        )
        allowed = TrafficPredicate.negate(blocked)
        traffic = TrafficAllowSpec(LOCAL, path, allowed)

        desired = compile_nft_filter_desired(
            compose_network_rules((_owned(1, traffic=(traffic,)),)),
            local_interface="host0",
        )

        section = desired.definition.split(
            "chain traffic_bytes {", 1
        )[1].split("}", 1)[0]
        # NOT(A and B and C) becomes one rule for each negated atom.
        self.assertIn("ip daddr != 10.20.0.0/16", section)
        self.assertIn("ip protocol != tcp", section)
        self.assertIn("tcp dport != 8007", section)

    def test_reverse_direction_uses_numeric_iif(self):
        path = _path("vpns00", 10)
        traffic = TrafficAllowSpec(
            path,
            LOCAL,
            TrafficPredicate.always(),
        )

        desired = compile_nft_filter_desired(
            compose_network_rules((_owned(1, traffic=(traffic,)),)),
            local_interface="host0",
        )

        self.assertIn('iif 10 oifname "host0"', desired.definition)
        self.assertTrue(
            any(
                marker.interface_ref.kind is InterfaceRefKind.IIF
                for marker in desired.markers
            )
        )

    def test_interface_to_interface_pair_is_explicitly_unsupported(self):
        first = _path("vpns00", 10)
        second = _path("vpns01", 11)
        traffic = TrafficAllowSpec(
            first,
            second,
            TrafficPredicate.always(),
        )

        with self.assertRaises(LinuxNftError):
            compile_nft_filter_desired(
                compose_network_rules((_owned(1, traffic=(traffic,)),)),
                local_interface="host0",
            )

    def test_never_predicate_emits_no_allow_rule(self):
        traffic = TrafficAllowSpec(
            LOCAL,
            _path("vpns00", 10),
            TrafficPredicate.never(),
        )

        desired = compile_nft_filter_desired(
            compose_network_rules((_owned(1, traffic=(traffic,)),)),
            local_interface="host0",
        )

        traffic_section = desired.definition.split(
            "chain traffic_bytes {", 1
        )[1].split("}", 1)[0]
        self.assertNotIn("return", traffic_section)



class LinuxNftNatTests(unittest.TestCase):
    def test_masquerade_uses_local_ingress_and_numeric_egress(self):
        path = _path("vpns00", 10)
        nat = SourceNatSpec(
            source=LOCAL,
            egress=path,
            predicate=TrafficPredicate.match(
                TrafficSelector(
                    destination=IPv4Network("10.0.0.0/8"),
                )
            ),
            target=SourceNatTarget.EGRESS_ADDRESS,
        )
        owned = OwnedNetworkRules(
            OwnerToken(7),
            NetworkRulesSpec(source_nat=(nat,)),
        )

        desired = compile_nft_nat_desired(
            compose_network_rules((owned,)),
            local_interface="host0",
        )

        self.assertIn(
            'iifname "host0" oif 10 ip daddr 10.0.0.0/8 masquerade',
            desired.definition,
        )
        self.assertEqual(len(desired.markers), 1)
        self.assertEqual(desired.markers[0].owner, OwnerToken(7))
        self.assertIs(
            desired.markers[0].interface_ref.kind,
            InterfaceRefKind.OIF,
        )

    def test_nat_predicate_negation_is_preserved(self):
        path = _path("vpns00", 10)
        predicate = TrafficPredicate.all_of(
            TrafficPredicate.match(
                TrafficSelector(
                    destination=IPv4Network("10.0.0.0/8"),
                )
            ),
            TrafficPredicate.negate(
                TrafficPredicate.match(
                    TrafficSelector(
                        destination=IPv4Network("10.1.0.0/16"),
                    )
                )
            ),
        )
        nat = SourceNatSpec(
            source=LOCAL,
            egress=path,
            predicate=predicate,
            target=SourceNatTarget.EGRESS_ADDRESS,
        )
        owned = OwnedNetworkRules(
            OwnerToken(1),
            NetworkRulesSpec(source_nat=(nat,)),
        )

        desired = compile_nft_nat_desired(
            compose_network_rules((owned,)),
            local_interface="host0",
        )

        self.assertIn("ip daddr 10.0.0.0/8", desired.definition)
        self.assertIn("ip daddr != 10.1.0.0/16", desired.definition)

    def test_nat_from_dynamic_interface_is_explicitly_unsupported(self):
        path = _path("vpns00", 10)
        nat = SourceNatSpec(
            source=path,
            egress=path,
            predicate=TrafficPredicate.always(),
            target=SourceNatTarget.EGRESS_ADDRESS,
        )
        owned = OwnedNetworkRules(
            OwnerToken(1),
            NetworkRulesSpec(source_nat=(nat,)),
        )

        with self.assertRaises(LinuxNftError):
            compile_nft_nat_desired(
                compose_network_rules((owned,)),
                local_interface="host0",
            )

    def test_never_nat_predicate_emits_no_rule(self):
        path = _path("vpns00", 10)
        nat = SourceNatSpec(
            source=LOCAL,
            egress=path,
            predicate=TrafficPredicate.never(),
            target=SourceNatTarget.EGRESS_ADDRESS,
        )
        owned = OwnedNetworkRules(
            OwnerToken(1),
            NetworkRulesSpec(source_nat=(nat,)),
        )

        desired = compile_nft_nat_desired(
            compose_network_rules((owned,)),
            local_interface="host0",
        )

        postrouting = desired.definition.split(
            "chain postrouting {", 1
        )[1].split("}", 1)[0]
        self.assertNotIn("masquerade", postrouting)


if __name__ == "__main__":
    unittest.main()
