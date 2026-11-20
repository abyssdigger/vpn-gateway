import json
import unittest
from ipaddress import IPv4Address, IPv4Network

from rou.linux_host_managed_routing import (
    HostManagedBypassRuleSpec,
    HostManagedDispatchRuleSpec,
    HostManagedPreserveMainRuleSpec,
    HostManagedRouteSpec,
    HostManagedRoutingLinuxAllocation,
    HostManagedRoutingLinuxDesired,
)
from rou.linux_host_managed_routing_backend import (
    LinuxHostManagedRoutingBackend,
    cleanup_host_managed_routing_once,
)
from rou.network_policy_layout import NumericResourcePool


class Runner:
    def __init__(self, routes="[]", rules="[]"):
        self.routes = routes
        self.rules = rules
        self.calls = []

    def run(self, argv):
        self.calls.append(tuple(argv))
        if "rule" in argv and "show" in argv:
            return self.rules
        if "route" in argv and "show" in argv:
            return self.routes
        return ""


def allocation():
    return HostManagedRoutingLinuxAllocation(
        table=0x7FFF0003,
        bypass_priority=0x6000,
        dispatch_priority=0x6001,
        owned_rule_priorities=NumericResourcePool(0x6001, 0x6002),
        rule_protocol=203,
        route_protocol=203,
    )


def desired():
    route = HostManagedRouteSpec(
        destination=IPv4Network("10.0.0.0/8"),
        interface="vpng0",
        table=allocation().table,
        protocol=203,
    )
    return HostManagedRoutingLinuxDesired(
        routes=(route,),
        bypass=HostManagedBypassRuleSpec(
            priority=0x6000,
            interface="vpng0",
            protocol=203,
        ),
        dispatch=HostManagedDispatchRuleSpec(
            priority=0x6001,
            table=allocation().table,
            protocol=203,
        ),
    )


def desired_snat():
    route = HostManagedRouteSpec(
        destination=IPv4Network("198.19.255.10/32"),
        interface="vpng0",
        table=allocation().table,
        protocol=203,
        gateway=IPv4Address("198.19.255.2"),
        onlink=True,
    )
    return HostManagedRoutingLinuxDesired(
        routes=(route,),
        bypass=HostManagedBypassRuleSpec(
            priority=0x6000,
            interface="vpng0",
            protocol=203,
        ),
        dispatch=HostManagedDispatchRuleSpec(
            priority=0x6001,
            table=allocation().table,
            protocol=203,
        ),
    )


class LinuxHostManagedRoutingBackendTests(unittest.TestCase):
    def test_tolerant_cleanup_leaves_foreign_replacement(self):
        alloc = HostManagedRoutingLinuxAllocation(
            table=0x7FFF0004,
            bypass_priority=0x6002,
            preserve_priority=0x6003,
            dispatch_priority=0x6004,
            owned_rule_priorities=NumericResourcePool(0x6003, 0x6005),
            rule_protocol=204,
            route_protocol=204,
        )
        desired_state = HostManagedRoutingLinuxDesired(
            routes=(),
            bypass=None,
            dispatch=None,
            preserve_main=None,
        )
        runner = Runner(
            routes=json.dumps([
                {
                    "dst": "10.0.0.0/8",
                    "dev": "eth9",
                    "table": alloc.table,
                    "protocol": 99,
                }
            ]),
            rules=json.dumps([
                {
                    "priority": 0x6003,
                    "src": "all",
                    "table": 123,
                    "protocol": 99,
                }
            ]),
        )
        backend = LinuxHostManagedRoutingBackend(runner, alloc)
        result = cleanup_host_managed_routing_once(
            backend,
            desired_state,
            tolerate_foreign_replacements=True,
        )
        self.assertEqual(result.routes, ())
        self.assertEqual(result.rule_priorities, ())
        self.assertTrue(result.conflicts)
        self.assertFalse(any("del" in call for call in runner.calls))

    def test_preserve_main_rule_signature_and_driver_command(self):
        alloc = HostManagedRoutingLinuxAllocation(
            table=0x7FFF0004,
            bypass_priority=0x6002,
            preserve_priority=0x6003,
            dispatch_priority=0x6004,
            owned_rule_priorities=NumericResourcePool(0x6003, 0x6005),
            rule_protocol=204,
            route_protocol=204,
        )
        route = HostManagedRouteSpec(
            destination=IPv4Network("0.0.0.0/0"),
            interface="vpng0",
            table=alloc.table,
            protocol=204,
        )
        desired_state = HostManagedRoutingLinuxDesired(
            routes=(route,),
            bypass=HostManagedBypassRuleSpec(0x6002, "vpng0", 204),
            dispatch=HostManagedDispatchRuleSpec(0x6004, alloc.table, 204),
            preserve_main=HostManagedPreserveMainRuleSpec(0x6003, 204, 0),
        )
        rules = json.dumps([
            {
                "priority": 0x6002, "src": "all", "iif": "vpng0",
                "table": 254, "protocol": 204,
            },
            {
                "priority": 0x6003, "src": "all", "table": 254,
                "protocol": 204, "suppress_prefixlen": 0,
            },
            {
                "priority": 0x6004, "src": "all", "table": alloc.table,
                "protocol": 204,
            },
        ])
        routes = json.dumps([
            {
                "dst": "default", "dev": "vpng0",
                "table": alloc.table, "protocol": 204,
            }
        ])
        runner = Runner(routes, rules)
        backend = LinuxHostManagedRoutingBackend(runner, alloc)
        self.assertTrue(backend.observe(desired_state).exact)
        backend.add_preserve_main_rule(desired_state.preserve_main)
        self.assertIn(
            (
                "ip", "-4", "rule", "add", "priority", str(0x6003),
                "protocol", "204", "lookup", "main",
                "suppress_prefixlength", "0",
            ),
            runner.calls,
        )

    def test_gateway_backed_snat_route_is_observed_exactly(self):
        routes = json.dumps(
            [
                {
                    "dst": "198.19.255.10",
                    "dev": "vpng0",
                    "gateway": "198.19.255.2",
                    "flags": ["onlink"],
                    "protocol": 203,
                    "table": allocation().table,
                }
            ]
        )
        rules = json.dumps(
            [
                {
                    "priority": 0x6000,
                    "src": "all",
                    "iif": "vpng0",
                    "table": 254,
                    "protocol": 203,
                },
                {
                    "priority": 0x6001,
                    "src": "all",
                    "table": allocation().table,
                    "protocol": 203,
                },
            ]
        )
        observed = LinuxHostManagedRoutingBackend(
            Runner(routes, rules), allocation()
        ).observe(desired_snat())
        self.assertTrue(observed.exact)
        self.assertEqual(observed.conflicts, ())

    def test_exact_kernel_json_is_observed(self):
        routes = json.dumps(
            [
                {
                    "dst": "10.0.0.0/8",
                    "dev": "vpng0",
                    "protocol": 203,
                    "table": allocation().table,
                }
            ]
        )
        rules = json.dumps(
            [
                {"priority": 0, "src": "all", "table": 255},
                {
                    "priority": 0x6000,
                    "src": "all",
                    "iif": "vpng0",
                    "table": 254,
                    "protocol": 203,
                },
                {
                    "priority": 0x6001,
                    "src": "all",
                    "table": allocation().table,
                    "protocol": 203,
                },
                {"priority": 32766, "src": "all", "table": 254},
            ]
        )
        observed = LinuxHostManagedRoutingBackend(
            Runner(routes, rules), allocation()
        ).observe(desired())
        self.assertTrue(observed.exact)
        self.assertEqual(observed.conflicts, ())

    def test_foreign_rule_at_required_priority_is_conflict(self):
        rules = json.dumps(
            [
                {
                    "priority": 0x6001,
                    "src": "all",
                    "table": 100,
                    "protocol": 99,
                }
            ]
        )
        observed = LinuxHostManagedRoutingBackend(
            Runner("[]", rules), allocation()
        ).observe(desired())
        self.assertIn("foreign rule", "; ".join(observed.conflicts))

    def test_driver_adds_gateway_backed_snat_route_onlink(self):
        runner = Runner()
        backend = LinuxHostManagedRoutingBackend(runner, allocation())
        route = desired_snat().routes[0]
        backend.add_route(route)
        self.assertIn(
            (
                "ip", "-4", "route", "add", "table", str(allocation().table),
                "198.19.255.10/32", "via", "198.19.255.2",
                "dev", "vpng0", "onlink", "proto", "203",
            ),
            runner.calls,
        )

    def test_driver_commands_are_device_only_and_generic(self):
        runner = Runner()
        backend = LinuxHostManagedRoutingBackend(runner, allocation())
        d = desired()
        backend.add_route(d.routes[0])
        backend.add_bypass_rule(d.bypass)
        backend.add_dispatch_rule(d.dispatch)
        self.assertIn(
            (
                "ip", "-4", "route", "add", "table", str(allocation().table),
                "10.0.0.0/8", "dev", "vpng0", "proto", "203",
            ),
            runner.calls,
        )
        self.assertIn(
            (
                "ip", "-4", "rule", "add", "priority", str(0x6001),
                "protocol", "203", "lookup", str(allocation().table),
            ),
            runner.calls,
        )


if __name__ == "__main__":
    unittest.main()
