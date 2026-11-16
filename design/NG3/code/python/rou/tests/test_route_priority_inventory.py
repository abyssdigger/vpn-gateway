from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
import json
import unittest

from rou.binding import LogicalPathId
from rou.interface_identity import InterfaceIdentity
from rou.route_priority_inventory import (
    RoutePriorityInventoryError,
    RoutePriorityPathRoute,
    parse_ip_route_priority_snapshot,
)


A = LogicalPathId("oc", 0, 0)
B = LogicalPathId("wg", 0, 0)
EP_A = InterfaceIdentity("tun0", 10)
EP_B = InterfaceIdentity("wg0", 20)
DEST = IPv4Network("10.0.0.0/8")
PROTO = 202


def spec_a():
    return RoutePriorityPathRoute(
        path_id=A,
        endpoint=EP_A,
        gateway=IPv4Address("172.20.0.1"),
        onlink=True,
    )


def spec_b():
    return RoutePriorityPathRoute(
        path_id=B,
        endpoint=EP_B,
    )


def parse(
    rows,
    *,
    destination=DEST,
    paths=None,
    interfaces=None,
    protocol_filtered=False,
):
    return parse_ip_route_priority_snapshot(
        json.dumps(rows),
        destination=destination,
        owner_protocol=PROTO,
        path_routes=(spec_a(), spec_b()) if paths is None else paths,
        interfaces=(EP_A, EP_B) if interfaces is None else interfaces,
        protocol_filtered=protocol_filtered,
    )


class RoutePriorityInventoryTests(unittest.TestCase):
    def test_projects_one_owned_route_key_domain(self):
        snapshot = parse(
            [
                {
                    "dst": "10.0.0.0/8",
                    "dev": "tun0",
                    "gateway": "172.20.0.1",
                    "protocol": 202,
                    "metric": 10,
                    "flags": ["onlink"],
                },
                {
                    "dst": "10.0.0.0/8",
                    "dev": "wg0",
                    "protocol": "202",
                    "metric": 20,
                    "flags": [],
                },
            ]
        )
        self.assertEqual(snapshot.routes[A], frozenset((10,)))
        self.assertEqual(snapshot.routes[B], frozenset((20,)))

    def test_partial_duplicate_is_preserved_for_one_path(self):
        snapshot = parse(
            [
                {
                    "dst": "10.0.0.0/8",
                    "dev": "tun0",
                    "gateway": "172.20.0.1",
                    "protocol": 202,
                    "metric": 10,
                    "flags": ["onlink"],
                },
                {
                    "dst": "10.0.0.0/8",
                    "dev": "tun0",
                    "gateway": "172.20.0.1",
                    "protocol": 202,
                    "metric": 30,
                    "flags": ["onlink"],
                },
                {
                    "dst": "10.0.0.0/8",
                    "dev": "wg0",
                    "protocol": 202,
                    "metric": 20,
                },
            ]
        )
        self.assertEqual(snapshot.routes[A], frozenset((10, 30)))
        self.assertEqual(snapshot.routes[B], frozenset((20,)))

    def test_missing_path_is_authoritative_empty_set(self):
        snapshot = parse(
            [
                {
                    "dst": "10.0.0.0/8",
                    "dev": "tun0",
                    "gateway": "172.20.0.1",
                    "protocol": 202,
                    "metric": 10,
                    "flags": ["onlink"],
                }
            ]
        )
        self.assertEqual(snapshot.routes[A], frozenset((10,)))
        self.assertEqual(snapshot.routes[B], frozenset())

    def test_foreign_protocol_and_destination_are_ignored(self):
        snapshot = parse(
            [
                {
                    "dst": "10.0.0.0/8",
                    "dev": "tun0",
                    "gateway": "172.20.0.1",
                    "protocol": 99,
                    "metric": 1,
                    "flags": ["onlink"],
                },
                {
                    "dst": "192.0.2.0/24",
                    "dev": "tun0",
                    "gateway": "172.20.0.1",
                    "protocol": 202,
                    "metric": 2,
                    "flags": ["onlink"],
                },
            ]
        )
        self.assertEqual(snapshot.routes[A], frozenset())
        self.assertEqual(snapshot.routes[B], frozenset())

    def test_default_destination_is_normalized(self):
        snapshot = parse(
            [
                {
                    "dst": "default",
                    "dev": "wg0",
                    "protocol": 202,
                    "metric": 20,
                }
            ],
            destination=IPv4Network("0.0.0.0/0"),
        )
        self.assertEqual(snapshot.routes[B], frozenset((20,)))

    def test_same_name_new_ifindex_cannot_impersonate_bound_path(self):
        new_tun = InterfaceIdentity("tun0", 11)
        with self.assertRaisesRegex(
            RoutePriorityInventoryError,
            "not the current interface identity",
        ):
            parse(
                [],
                paths=(spec_a(), spec_b()),
                interfaces=(new_tun, EP_B),
            )

    def test_owned_row_on_unbound_interface_is_rejected(self):
        foreign = InterfaceIdentity("vpn9", 90)
        with self.assertRaisesRegex(
            RoutePriorityInventoryError,
            "does not match exactly one expected logical path",
        ):
            parse(
                [
                    {
                        "dst": "10.0.0.0/8",
                        "dev": "vpn9",
                        "protocol": 202,
                        "metric": 10,
                    }
                ],
                interfaces=(EP_A, EP_B, foreign),
            )

    def test_route_on_absent_interface_is_rejected(self):
        with self.assertRaisesRegex(
            RoutePriorityInventoryError,
            "absent from current interface inventory",
        ):
            parse(
                [
                    {
                        "dst": "10.0.0.0/8",
                        "dev": "ghost0",
                        "protocol": 202,
                        "metric": 10,
                    }
                ]
            )

    def test_gateway_or_onlink_mismatch_is_rejected(self):
        with self.assertRaisesRegex(
            RoutePriorityInventoryError,
            "does not match exactly one expected logical path",
        ):
            parse(
                [
                    {
                        "dst": "10.0.0.0/8",
                        "dev": "tun0",
                        "gateway": "172.20.0.9",
                        "protocol": 202,
                        "metric": 10,
                        "flags": ["onlink"],
                    }
                ]
            )
        with self.assertRaisesRegex(
            RoutePriorityInventoryError,
            "does not match exactly one expected logical path",
        ):
            parse(
                [
                    {
                        "dst": "10.0.0.0/8",
                        "dev": "tun0",
                        "gateway": "172.20.0.1",
                        "protocol": 202,
                        "metric": 10,
                    }
                ]
            )

    def test_multipath_or_nonunicast_owned_row_is_rejected(self):
        with self.assertRaisesRegex(RoutePriorityInventoryError, "unsupported"):
            parse(
                [
                    {
                        "dst": "10.0.0.0/8",
                        "protocol": 202,
                        "metric": 10,
                        "nexthops": [{"dev": "tun0"}, {"dev": "wg0"}],
                    }
                ]
            )
        with self.assertRaisesRegex(RoutePriorityInventoryError, "not unicast"):
            parse(
                [
                    {
                        "dst": "10.0.0.0/8",
                        "type": "blackhole",
                        "dev": "tun0",
                        "protocol": 202,
                        "metric": 10,
                    }
                ]
            )

    def test_duplicate_exact_path_metric_is_rejected(self):
        row = {
            "dst": "10.0.0.0/8",
            "dev": "wg0",
            "protocol": 202,
            "metric": 20,
        }
        with self.assertRaisesRegex(
            RoutePriorityInventoryError,
            "duplicates metric",
        ):
            parse([row, dict(row)])

    def test_protocol_filtered_query_accepts_omitted_protocol(self):
        snapshot = parse(
            [
                {
                    "dst": "10.0.0.0/8",
                    "dev": "wg0",
                    "metric": 20,
                }
            ],
            protocol_filtered=True,
        )
        self.assertEqual(snapshot.routes[B], frozenset((20,)))

    def test_protocol_filtered_query_rejects_explicit_mismatch(self):
        with self.assertRaisesRegex(
            RoutePriorityInventoryError,
            "does not match filtered owner protocol",
        ):
            parse(
                [
                    {
                        "dst": "10.0.0.0/8",
                        "dev": "wg0",
                        "protocol": 99,
                        "metric": 20,
                    }
                ],
                protocol_filtered=True,
            )

    def test_unfiltered_omitted_protocol_is_foreign_not_owned(self):
        snapshot = parse(
            [
                {
                    "dst": "10.0.0.0/8",
                    "dev": "wg0",
                    "metric": 20,
                }
            ]
        )
        self.assertEqual(snapshot.routes[B], frozenset())

    def test_unrepresentable_route_fields_fail_owned_inventory(self):
        for key, value in (
            ("nhid", 7),
            ("multipath", [{"dev": "wg0"}]),
            ("via", {"family": "inet6", "addr": "::1"}),
        ):
            with self.subTest(key=key):
                with self.assertRaisesRegex(
                    RoutePriorityInventoryError,
                    "unsupported",
                ):
                    parse(
                        [
                            {
                                "dst": "10.0.0.0/8",
                                "dev": "wg0",
                                "protocol": 202,
                                "metric": 20,
                                key: value,
                            }
                        ]
                    )

    def test_unrepresented_owned_route_flag_is_rejected(self):
        with self.assertRaisesRegex(
            RoutePriorityInventoryError,
            "unrepresented flags",
        ):
            parse(
                [
                    {
                        "dst": "10.0.0.0/8",
                        "dev": "wg0",
                        "protocol": 202,
                        "metric": 20,
                        "flags": ["linkdown"],
                    }
                ]
            )

    def test_path_route_constructor_validates_runtime_types(self):
        with self.assertRaisesRegex(ValueError, "gateway"):
            RoutePriorityPathRoute(
                path_id=A,
                endpoint=EP_A,
                gateway="172.20.0.1",  # type: ignore[arg-type]
            )
        with self.assertRaisesRegex(ValueError, "onlink"):
            RoutePriorityPathRoute(
                path_id=A,
                endpoint=EP_A,
                onlink=1,  # type: ignore[arg-type]
            )

    def test_malformed_json_is_observation_error_not_empty_snapshot(self):
        with self.assertRaisesRegex(
            RoutePriorityInventoryError,
            "invalid ip-route JSON",
        ):
            parse_ip_route_priority_snapshot(
                "{",
                destination=DEST,
                owner_protocol=PROTO,
                path_routes=(spec_a(), spec_b()),
                interfaces=(EP_A, EP_B),
            )

    def test_invalid_metric_is_rejected(self):
        with self.assertRaisesRegex(
            RoutePriorityInventoryError,
            "metric must be a non-negative integer",
        ):
            parse(
                [
                    {
                        "dst": "10.0.0.0/8",
                        "dev": "wg0",
                        "protocol": 202,
                        "metric": True,
                    }
                ]
            )

    def test_duplicate_current_interface_identity_is_rejected(self):
        with self.assertRaisesRegex(
            RoutePriorityInventoryError,
            "duplicate current interface name",
        ):
            parse(
                [],
                interfaces=(EP_A, InterfaceIdentity("tun0", 11), EP_B),
            )

    def test_one_current_endpoint_cannot_back_two_paths(self):
        duplicate = RoutePriorityPathRoute(
            path_id=B,
            endpoint=EP_A,
            gateway=IPv4Address("172.20.0.1"),
            onlink=True,
        )
        with self.assertRaisesRegex(
            RoutePriorityInventoryError,
            "assigned to multiple logical paths",
        ):
            parse([], paths=(spec_a(), duplicate))


if __name__ == "__main__":
    unittest.main()
