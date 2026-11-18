import unittest
from ipaddress import IPv4Address, IPv4Network

from rou.host_underlay_route import HostUnderlayPin
from rou.linux_host_boundary_policy import (
    HostBoundaryReturnRouteSpec,
    HostBoundaryRouteSpec,
    HostBoundaryRuleSpec,
)
from rou.linux_host_boundary_routes import LinuxHostBoundaryRouteBackend


class Runner:
    def __init__(self):
        self.calls = []

    def run(self, argv):
        self.calls.append(tuple(argv))
        return ""


class LinuxHostBoundaryRouteBackendTests(unittest.TestCase):
    def setUp(self):
        self.runner = Runner()
        self.backend = LinuxHostBoundaryRouteBackend(self.runner)

    def test_underlay_observation_is_fresh_and_normalized(self):
        responses = iter((
            '[{"dst":"198.51.100.10","gateway":"192.0.2.1","dev":"eth0","prefsrc":"192.0.2.20"}]',
            '[]',
        ))
        def run(argv):
            self.runner.calls.append(tuple(argv))
            return next(responses)
        self.runner.run = run

        pin = self.backend.observe_underlay_pin(
            IPv4Address("198.51.100.10"),
            managed_interface="vnga-host0",
            owner_protocol=203,
        )
        self.assertTrue(pin.owned)
        self.assertEqual(pin.interface, "eth0")
        self.assertEqual(pin.gateway, IPv4Address("192.0.2.1"))
        self.assertEqual(
            self.runner.calls,
            [
                ("ip", "-j", "-4", "route", "get", "198.51.100.10"),
                (
                    "ip", "-j", "-4", "route", "show",
                    "table", "main",
                ),
            ],
        )

    def test_existing_exact_route_is_external_and_never_mutated(self):
        responses = iter((
            '[{"dst":"198.51.100.10","gateway":"192.0.2.1","dev":"eth0","prefsrc":"192.0.2.20"}]',
            '[{"dst":"198.51.100.10/32","gateway":"192.0.2.1","dev":"eth0","prefsrc":"192.0.2.20","protocol":"static"}]',
        ))
        def run(argv):
            self.runner.calls.append(tuple(argv))
            return next(responses)
        self.runner.run = run

        pin = self.backend.observe_underlay_pin(
            IPv4Address("198.51.100.10"),
            managed_interface="vnga-host0",
            owner_protocol=203,
        )
        self.assertFalse(pin.owned)
        self.assertTrue(pin.present)
        before = list(self.runner.calls)
        self.backend.add_underlay_pin(pin)
        self.backend.delete_underlay_pin(pin)
        self.assertEqual(self.runner.calls, before)

    def test_existing_owned_pin_is_not_added_again_but_is_cleanup_owned(self):
        responses = iter((
            '[{"dst":"198.51.100.10","gateway":"192.0.2.1","dev":"eth0","prefsrc":"192.0.2.20"}]',
            '[{"dst":"198.51.100.10/32","gateway":"192.0.2.1","dev":"eth0","prefsrc":"192.0.2.20","protocol":203}]',
        ))
        def run(argv):
            self.runner.calls.append(tuple(argv))
            return next(responses)
        self.runner.run = run
        pin = self.backend.observe_underlay_pin(
            IPv4Address("198.51.100.10"),
            managed_interface="vnga-host0",
            owner_protocol=203,
        )
        self.assertTrue(pin.owned)
        self.assertTrue(pin.present)
        before = list(self.runner.calls)
        self.backend.add_underlay_pin(pin)
        self.assertEqual(self.runner.calls, before)

    def test_underlay_pin_add_delete_are_exact(self):
        pin = HostUnderlayPin(
            endpoint=IPv4Address("198.51.100.10"),
            interface="eth0",
            gateway=IPv4Address("192.0.2.1"),
            source=IPv4Address("192.0.2.20"),
            protocol=203,
        )
        self.backend.add_underlay_pin(pin)
        self.backend.delete_underlay_pin(pin)
        self.assertEqual(
            self.runner.calls,
            [
                (
                    "ip", "-4", "route", "add", "198.51.100.10/32",
                    "via", "192.0.2.1", "dev", "eth0",
                    "src", "192.0.2.20", "proto", "203",
                ),
                (
                    "ip", "-4", "route", "del", "198.51.100.10/32",
                    "via", "192.0.2.1", "dev", "eth0",
                    "src", "192.0.2.20", "proto", "203",
                ),
            ],
        )

    def test_network_namespace_wraps_host_commands(self):
        backend = LinuxHostBoundaryRouteBackend(
            self.runner,
            network_namespace="host-ns",
        )
        pin = HostUnderlayPin(
            endpoint=IPv4Address("198.51.100.10"),
            interface="eth0",
            gateway=IPv4Address("192.0.2.1"),
            source=None,
            protocol=203,
        )
        backend.add_underlay_pin(pin)
        self.assertEqual(
            self.runner.calls[0][:4],
            ("ip", "netns", "exec", "host-ns"),
        )
        self.assertEqual(
            self.runner.calls[0][4:],
            (
                "ip", "-4", "route", "add", "198.51.100.10/32",
                "via", "192.0.2.1", "dev", "eth0", "proto", "203",
            ),
        )

    def test_absent_custom_return_table_is_cleanly_absent(self):
        route = HostBoundaryReturnRouteSpec(
            via=IPv4Address("198.19.255.2"),
            interface="vnga-host0",
            table=1053,
            protocol=203,
        )
        self.runner.run = lambda argv: "[]"
        self.assertFalse(self.backend.return_route_present(route))

    def test_matching_custom_return_route_is_observed_from_table_all(self):
        route = HostBoundaryReturnRouteSpec(
            via=IPv4Address("198.19.255.2"),
            interface="vnga-host0",
            table=1053,
            protocol=203,
        )
        self.runner.run = lambda argv: (
            '[{"dst":"default","gateway":"198.19.255.2","dev":"vnga-host0",'
            '"protocol":"203","table":1053}]'
        )
        self.assertTrue(self.backend.return_route_present(route))

    def test_matching_bootstrap_route_and_return_rule_are_observed(self):
        bootstrap = HostBoundaryRouteSpec(
            destination=IPv4Network("10.0.0.0/8"),
            via=IPv4Address("198.19.255.2"),
            interface="vnga-host0",
            protocol=203,
        )
        rule = HostBoundaryRuleSpec(mark=0x53, table=1053, priority=1053)
        responses = iter((
            '[{"dst":"10.0.0.0/8","gateway":"198.19.255.2","dev":"vnga-host0","protocol":"203"}]',
            '[{"priority":0,"src":"all","table":255},{"priority":1053,"src":"all","fwmark":"0x53","table":1053},{"priority":32766,"src":"all","table":254}]',
        ))
        def run(argv):
            self.runner.calls.append(tuple(argv))
            return next(responses)
        self.runner.run = run
        self.assertTrue(self.backend.bootstrap_route_present(bootstrap))
        self.assertTrue(self.backend.return_rule_present(rule))

    def test_foreign_route_or_rule_at_owned_key_is_conflict(self):
        bootstrap = HostBoundaryRouteSpec(
            destination=IPv4Network("10.0.0.0/8"),
            via=IPv4Address("198.19.255.2"),
            interface="vnga-host0",
            protocol=203,
        )
        self.runner.run = lambda argv: '[{"dst":"10.0.0.0/8","gateway":"192.0.2.1","dev":"eth0","protocol":"static"}]'
        with self.assertRaisesRegex(RuntimeError, "foreign/conflicting"):
            self.backend.bootstrap_route_present(bootstrap)

        rule = HostBoundaryRuleSpec(mark=0x53, table=1053, priority=1053)
        self.runner.run = lambda argv: '[{"priority":1053,"src":"all","table":100}]'
        with self.assertRaisesRegex(RuntimeError, "table mismatch"):
            self.backend.return_rule_present(rule)

    def test_bootstrap_and_return_commands_are_bounded(self):
        bootstrap = HostBoundaryRouteSpec(
            destination=IPv4Network("0.0.0.0/1"),
            via=IPv4Address("198.19.255.2"),
            interface="vnga-host0",
            protocol=203,
        )
        route = HostBoundaryReturnRouteSpec(
            via=IPv4Address("198.19.255.2"),
            interface="vnga-host0",
            table=1053,
            protocol=203,
        )
        rule = HostBoundaryRuleSpec(
            mark=0x53,
            table=1053,
            priority=1053,
        )
        self.backend.add_bootstrap_route(bootstrap)
        self.backend.add_return_route(route)
        self.backend.add_return_rule(rule)
        self.backend.delete_return_rule(rule)
        self.backend.delete_return_route(route)
        self.backend.delete_bootstrap_route(bootstrap)

        self.assertIn(
            (
                "ip", "-4", "route", "add", "0.0.0.0/1",
                "via", "198.19.255.2", "dev", "vnga-host0", "proto", "203",
            ),
            self.runner.calls,
        )
        self.assertIn(
            (
                "ip", "-4", "route", "add", "default",
                "via", "198.19.255.2", "dev", "vnga-host0",
                "table", "1053", "proto", "203",
            ),
            self.runner.calls,
        )
        self.assertIn(
            (
                "ip", "-4", "rule", "add", "priority", "1053",
                "fwmark", "0x53", "lookup", "1053",
            ),
            self.runner.calls,
        )


if __name__ == "__main__":
    unittest.main()
