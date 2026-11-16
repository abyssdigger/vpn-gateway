from __future__ import annotations

import json
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.payload_routing_desired import ManagedRouteType
from rou.structural_routing_inventory import (
    StructuralRoutingInventoryError,
    parse_structural_routing_inventory,
)


HOST = InterfaceIdentity("host0", 5)
PATH0 = InterfaceIdentity("path0", 10)
PATH1 = InterfaceIdentity("path1", 20)


EXP029_ROUTES = [
    {
        "dev": "path1",
        "dst": "198.51.100.7",
        "flags": [],
        "metric": 1,
        "protocol": "202",
        "scope": "253",
        "table": "3221225472",
    },
    {
        "dst": "default",
        "flags": [],
        "metric": 4294967295,
        "protocol": "201",
        "table": "2147483648",
        "type": "6",
    },
    {
        "dev": "path0",
        "dst": "10.77.0.0/16",
        "flags": [],
        "metric": 1,
        "protocol": "202",
        "scope": "253",
        "table": "2147483648",
    },
]
EXP029_RULES = [
    {
        "fwmark": "0x1234",
        "fwmask": "0xffff",
        "priority": 8192,
        "src": "all",
        "table": "3221225472",
    },
    {
        "dst": "10.77.0.0",
        "dstlen": 16,
        "iif": "host0",
        "priority": 16384,
        "src": "all",
        "table": "2147483648",
    },
]


def parse(routes=EXP029_ROUTES, rules=EXP029_RULES, interfaces=(HOST, PATH0, PATH1)):
    return parse_structural_routing_inventory(
        json.dumps(routes),
        json.dumps(rules),
        interfaces,
        NG3_LINUX_POLICY_PLATFORM,
    )


class StructuralRoutingInventoryTests(unittest.TestCase):
    def test_exp029_shape_normalizes_to_typed_inventory(self):
        value = parse()
        self.assertEqual(value.conflicts, ())
        self.assertEqual(len(value.routes), 3)
        self.assertEqual(len(value.rules), 2)

        guard = next(
            route
            for route in value.routes
            if route.route_type is ManagedRouteType.BLACKHOLE
        )
        self.assertEqual(guard.table, 0x80000000)
        self.assertEqual(str(guard.destination), "0.0.0.0/0")
        self.assertEqual(guard.protocol, 201)
        self.assertEqual(guard.metric, 0xFFFFFFFF)

        host_route = next(
            route
            for route in value.routes
            if str(route.destination) == "198.51.100.7/32"
        )
        self.assertEqual(host_route.endpoint, PATH1)

        probe_rule = next(rule for rule in value.rules if rule.priority == 0x2000)
        self.assertEqual(probe_rule.fwmark, 0x1234)
        self.assertEqual(probe_rule.fwmask, 0xFFFF)

        payload_rule = next(rule for rule in value.rules if rule.priority == 0x4000)
        self.assertEqual(payload_rule.ingress, HOST)
        self.assertEqual(str(payload_rule.destination), "10.77.0.0/16")

    def test_foreign_low_table_and_priority_rows_are_ignored(self):
        routes = EXP029_ROUTES + [
            {
                "dst": "203.0.113.0/24",
                "dev": "path0",
                "table": "254",
                "protocol": "2",
                "metric": 0,
            }
        ]
        rules = EXP029_RULES + [
            {"priority": 32766, "src": "all", "table": "254"}
        ]
        value = parse(routes, rules)
        self.assertEqual(len(value.routes), 3)
        self.assertEqual(len(value.rules), 2)
        self.assertEqual(value.conflicts, ())

    def test_unexpected_reserved_route_role_is_conflict_not_ignored(self):
        routes = EXP029_ROUTES + [
            {
                "dst": "203.0.113.0/24",
                "dev": "path0",
                "table": str(0x80000001),
                "protocol": "99",
                "metric": 5,
            }
        ]
        value = parse(routes, EXP029_RULES)
        self.assertEqual(len(value.routes), 3)
        self.assertEqual(len(value.conflicts), 1)
        self.assertIn("unexpected protocol role", value.conflicts[0].reason)

    def test_reserved_rule_wrong_table_pool_is_conflict(self):
        rules = EXP029_RULES + [
            {
                "priority": 0x4001,
                "src": "all",
                "dst": "203.0.113.0",
                "dstlen": 24,
                "iif": "host0",
                "table": str(0xC0000000),
            }
        ]
        value = parse(EXP029_ROUTES, rules)
        self.assertEqual(len(value.conflicts), 1)
        self.assertIn("outside payload table pool", value.conflicts[0].reason)

    def test_reserved_rule_unknown_selector_is_conflict(self):
        rules = [
            {
                "priority": 0x4000,
                "src": "all",
                "dst": "10.77.0.0",
                "dstlen": 16,
                "iif": "host0",
                "table": str(0x80000000),
                "uidrange": "1-2",
            }
        ]
        value = parse([], rules)
        self.assertEqual(value.rules, ())
        self.assertEqual(len(value.conflicts), 1)
        self.assertIn("unsupported fields", value.conflicts[0].reason)

    def test_same_name_replacement_is_visible_as_missing_current_endpoint(self):
        replacement = InterfaceIdentity("path0", 11)
        value = parse(
            [EXP029_ROUTES[2]],
            [],
            (HOST, replacement, PATH1),
        )
        self.assertEqual(value.routes[0].endpoint, replacement)
        self.assertNotEqual(value.routes[0].endpoint, PATH0)

    def test_reserved_route_on_absent_interface_is_conflict(self):
        value = parse(
            [EXP029_ROUTES[2]],
            [],
            (HOST, PATH1),
        )
        self.assertEqual(value.routes, ())
        self.assertEqual(len(value.conflicts), 1)
        self.assertIn("absent from current interface inventory", value.conflicts[0].reason)

    def test_malformed_json_is_observation_error_not_empty_inventory(self):
        with self.assertRaisesRegex(
            StructuralRoutingInventoryError,
            "invalid route JSON",
        ):
            parse_structural_routing_inventory(
                "{",
                "[]",
                (HOST, PATH0, PATH1),
                NG3_LINUX_POLICY_PLATFORM,
            )

    def test_duplicate_normalized_reserved_object_is_conflict(self):
        value = parse(
            [EXP029_ROUTES[2], dict(EXP029_ROUTES[2])],
            [],
        )
        self.assertEqual(len(value.routes), 2)
        self.assertEqual(len(value.conflicts), 1)
        self.assertIn("duplicate normalized route", value.conflicts[0].reason)

    def test_blackhole_with_path_fields_is_conflict(self):
        bad = dict(EXP029_ROUTES[1])
        bad["dev"] = "path0"
        value = parse([bad], [])
        self.assertEqual(value.routes, ())
        self.assertEqual(len(value.conflicts), 1)
        self.assertIn("path next-hop fields", value.conflicts[0].reason)


if __name__ == "__main__":
    unittest.main()
