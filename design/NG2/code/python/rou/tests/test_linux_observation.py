import json
from ipaddress import IPv4Network
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.linux_observation import (
    LinuxRoutingObservation,
    ObservedRoute,
    ObservedRule,
    parse_link_json,
    parse_route_json,
    parse_rule_json,
    verify_linux_routing,
)
from rou.linux_routing import (
    LinuxRoutingAllocationState,
    compile_linux_routing_desired,
)
from rou.network_rules import (
    DispatchRuleSpec,
    NetworkEndpoint,
    NetworkRulesSpec,
    RoutingDomainSpec,
    TerminalDisposition,
)
from rou.network_rules_composition import (
    OwnedNetworkRules,
    OwnerToken,
    compose_network_rules,
)


def _desired(path=InterfaceIdentity("vpns00", 10)):
    network = IPv4Network("10.0.0.0/8")
    owned = OwnedNetworkRules(
        OwnerToken(1),
        NetworkRulesSpec(
            routing_domains=(
                RoutingDomainSpec(
                    "corp",
                    (network,),
                    (path,),
                    TerminalDisposition.DROP,
                ),
            ),
            dispatch_rules=(
                DispatchRuleSpec(
                    network,
                    "corp",
                    source=NetworkEndpoint.local_network(),
                ),
            ),
        ),
    )
    return compile_linux_routing_desired(
        compose_network_rules((owned,)),
        LinuxRoutingAllocationState(),
        local_interface="host0",
    )


def _exact_observation(desired):
    routes = tuple(
        ObservedRoute(
            table_id=item.table_id,
            destination=item.destination,
            kind=item.kind.value,
            protocol=item.protocol,
            metric=item.metric,
            ifname=None if item.path is None else item.path.ifname,
        )
        for item in desired.routes
    )
    rules = [
        ObservedRule(
            priority=item.priority,
            source_ifname=item.source_ifname,
            destination=item.destination,
            table_id=item.table_id,
            action="to_tbl",
        )
        for item in desired.dispatch_rules
    ]
    if desired.terminal_rule is not None:
        rules.append(
            ObservedRule(
                priority=desired.terminal_rule.priority,
                source_ifname=desired.terminal_rule.source_ifname,
                destination=None,
                table_id=None,
                action="unreachable",
            )
        )
    rules = tuple(rules)
    return LinuxRoutingObservation(
        interfaces=(
            InterfaceIdentity("host0", 2),
            InterfaceIdentity("vpns00", 10),
        ),
        routes=routes,
        rules=rules,
        ip_forward=True,
    )


class LinuxObservationParserTests(unittest.TestCase):
    def test_parse_link_json_preserves_generation_identity(self):
        parsed = parse_link_json(
            json.dumps(
                [
                    {"ifname": "host0", "ifindex": 2},
                    {"ifname": "vpns00", "ifindex": 10},
                ]
            )
        )
        self.assertEqual(
            parsed,
            (
                InterfaceIdentity("host0", 2),
                InterfaceIdentity("vpns00", 10),
            ),
        )

    def test_parse_route_json_normalizes_numeric_protocol(self):
        parsed = parse_route_json(
            json.dumps(
                [
                    {
                        "table": 1,
                        "dst": "10.0.0.0/8",
                        "dev": "vpns00",
                        "protocol": "202",
                        "metric": 10,
                    },
                    {
                        "type": "blackhole",
                        "table": 1,
                        "dst": "default",
                        "protocol": 201,
                        "metric": 65536,
                    },
                ]
            )
        )
        self.assertEqual(parsed[0].protocol, 202)
        self.assertEqual(
            parsed[1].destination,
            IPv4Network("0.0.0.0/0"),
        )

    def test_parse_lookup_all_normalizes_to_default_prefix(self):
        parsed = parse_rule_json(
            json.dumps(
                [
                    {
                        "priority": 1,
                        "iif": "host0",
                        "table": 1,
                    }
                ]
            )
        )

        self.assertEqual(
            parsed[0].destination,
            IPv4Network("0.0.0.0/0"),
        )

    def test_parse_terminal_all_keeps_no_destination(self):
        parsed = parse_rule_json(
            json.dumps(
                [
                    {
                        "priority": 2,
                        "iif": "host0",
                        "action": "unreachable",
                    }
                ]
            )
        )

        self.assertIsNone(parsed[0].destination)

    def test_parse_rule_json_combines_dst_and_dstlen(self):
        parsed = parse_rule_json(
            json.dumps(
                [
                    {
                        "priority": 1,
                        "iif": "host0",
                        "dst": "10.0.0.0",
                        "dstlen": 8,
                        "table": 1,
                    }
                ]
            )
        )
        self.assertEqual(
            parsed[0].destination,
            IPv4Network("10.0.0.0/8"),
        )


class LinuxRoutingVerificationTests(unittest.TestCase):
    def test_exact_routing_and_generation_pass(self):
        desired = _desired()
        observed = _exact_observation(desired)

        result = verify_linux_routing(
            desired,
            observed,
            expected_ip_forward=True,
        )

        self.assertTrue(result.ok, result.errors)

    def test_same_name_new_ifindex_fails_generation_verification(self):
        desired = _desired()
        observed = _exact_observation(desired)
        observed = LinuxRoutingObservation(
            interfaces=(
                InterfaceIdentity("host0", 2),
                InterfaceIdentity("vpns00", 11),
            ),
            routes=observed.routes,
            rules=observed.rules,
            ip_forward=True,
        )

        result = verify_linux_routing(
            desired,
            observed,
            expected_ip_forward=True,
        )

        self.assertFalse(result.ok)
        self.assertTrue(
            any("generation mismatch" in item for item in result.errors)
        )

    def test_extra_route_in_owned_table_fails(self):
        desired = _desired()
        observed = _exact_observation(desired)
        extra = ObservedRoute(
            table_id=desired.verification_tables[0],
            destination=IPv4Network("192.0.2.0/24"),
            kind="unicast",
            protocol=202,
            metric=30,
            ifname="vpns00",
        )
        observed = LinuxRoutingObservation(
            observed.interfaces,
            observed.routes + (extra,),
            observed.rules,
            observed.ip_forward,
        )

        result = verify_linux_routing(desired, observed)

        self.assertFalse(result.ok)
        self.assertTrue(
            any("unexpected routes" in item for item in result.errors)
        )

    def test_stale_tagged_table_outside_allocator_history_fails(self):
        desired = _desired()
        observed = _exact_observation(desired)
        stale = ObservedRoute(
            table_id=77,
            destination=IPv4Network("203.0.113.0/24"),
            kind="unicast",
            protocol=202,
            metric=10,
            ifname="vpns00",
        )
        observed = LinuxRoutingObservation(
            observed.interfaces,
            observed.routes + (stale,),
            observed.rules,
            observed.ip_forward,
        )

        result = verify_linux_routing(desired, observed)

        self.assertFalse(result.ok)
        self.assertIn(77, result.tagged_tables)
        self.assertTrue(
            any("outside tracked tables" in item for item in result.errors)
        )

    def test_foreign_route_outside_owned_tables_is_ignored(self):
        desired = _desired()
        observed = _exact_observation(desired)
        foreign = ObservedRoute(
            table_id=100,
            destination=IPv4Network("198.51.100.0/24"),
            kind="unicast",
            protocol=99,
            metric=5,
            ifname="host0",
        )
        observed = LinuxRoutingObservation(
            observed.interfaces,
            observed.routes + (foreign,),
            observed.rules,
            observed.ip_forward,
        )

        result = verify_linux_routing(desired, observed)

        self.assertTrue(result.ok, result.errors)

    def test_extra_rule_in_owned_priority_window_fails(self):
        desired = _desired()
        observed = _exact_observation(desired)
        extra = ObservedRule(
            priority=100,
            source_ifname="host0",
            destination=IPv4Network("192.0.2.0/24"),
            table_id=100,
            action="to_tbl",
        )
        observed = LinuxRoutingObservation(
            observed.interfaces,
            observed.routes,
            observed.rules + (extra,),
            observed.ip_forward,
        )

        result = verify_linux_routing(desired, observed)

        self.assertFalse(result.ok)
        self.assertTrue(
            any("unexpected RPDB" in item for item in result.errors)
        )

    def test_forwarding_expectation_is_verified(self):
        desired = _desired()
        observed = _exact_observation(desired)
        observed = LinuxRoutingObservation(
            observed.interfaces,
            observed.routes,
            observed.rules,
            False,
        )

        result = verify_linux_routing(
            desired,
            observed,
            expected_ip_forward=True,
        )

        self.assertFalse(result.ok)
        self.assertTrue(
            any("ip_forward mismatch" in item for item in result.errors)
        )


if __name__ == "__main__":
    unittest.main()
