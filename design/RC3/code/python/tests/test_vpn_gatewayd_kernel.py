#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import vpn_gatewayd as vpng


def kernel() -> object:
    return vpng.SubprocessKernelInterface()


def completed(payload) -> SimpleNamespace:
    return SimpleNamespace(stdout=json.dumps(payload))


def unicast_route(
    *,
    destination: str = "10.0.0.0/8",
    via: str | None = "172.20.130.6",
    interface: str | None = "vpns0",
    metric: int | None = 10,
    proto: int | None = vpng.VPN_ROUTE_PROTO,
    onlink: bool = True,
) -> object:
    return vpng.RouteSpec(
        destination=IPv4Network(destination),
        route_type=vpng.RouteType.UNICAST,
        via=None if via is None else IPv4Address(via),
        interface=interface,
        metric=metric,
        proto=proto,
        onlink=onlink,
    )


class KernelRouteAdapterTests(unittest.TestCase):
    def test_list_routes_normalizes_supported_main_table_routes(self):
        adapter = kernel()
        payload = [
            {
                "dst": "default",
                "gateway": "10.200.200.1",
                "dev": "ens18",
                "protocol": 16,
                "metric": 100,
                "flags": [],
            },
            {
                "dst": "10.200.200.0/24",
                "dev": "ens18",
                "protocol": 2,
                "scope": 253,
                "prefsrc": "10.200.200.7",
                "flags": [],
            },
            {
                "type": "blackhole",
                "dst": "10.0.0.0/8",
                "protocol": "201",
                "metric": 65536,
                "flags": [],
            },
            {
                "dst": "203.0.113.9",
                "dev": "lo",
                "protocol": 4,
                "flags": [],
            },
            {
                "type": "throw",
                "dst": "192.168.0.0/16",
                "protocol": 202,
                "flags": ["onlink"],
            },
        ]

        with mock.patch.object(
            adapter,
            "_run",
            return_value=completed(payload),
        ) as run:
            routes = adapter.list_routes()

        run.assert_called_once_with(
            (
                "ip",
                "-j",
                "-N",
                "-4",
                "route",
                "show",
                "table",
                "main",
            )
        )
        self.assertEqual(len(routes), 5)
        self.assertIn(
            vpng.RouteSpec(
                destination=IPv4Network("0.0.0.0/0"),
                route_type=vpng.RouteType.UNICAST,
                via=IPv4Address("10.200.200.1"),
                interface="ens18",
                metric=100,
                proto=16,
                onlink=False,
            ),
            routes,
        )
        self.assertIn(
            vpng.RouteSpec(
                destination=IPv4Network("10.200.200.0/24"),
                route_type=vpng.RouteType.UNICAST,
                via=None,
                interface="ens18",
                metric=None,
                proto=vpng.KERNEL_ROUTE_PROTO,
                onlink=False,
            ),
            routes,
        )
        self.assertIn(
            vpng.RouteSpec(
                destination=IPv4Network("203.0.113.9/32"),
                route_type=vpng.RouteType.UNICAST,
                via=None,
                interface="lo",
                metric=None,
                proto=4,
                onlink=False,
            ),
            routes,
        )

    def test_list_routes_accepts_numeric_route_type_strings_from_dash_N(self):
        adapter = kernel()
        payload = [
            {
                "type": "6",
                "dst": "192.0.2.0/24",
                "protocol": "201",
                "metric": 65536,
                "flags": [],
            },
            {
                "type": "9",
                "dst": "198.51.100.0/24",
                "protocol": "202",
                "flags": [],
            },
        ]

        with mock.patch.object(
            adapter,
            "_run",
            return_value=completed(payload),
        ):
            routes = adapter.list_routes()

        self.assertEqual(
            {route.route_type for route in routes},
            {vpng.RouteType.BLACKHOLE, vpng.RouteType.THROW},
        )

    def test_list_routes_by_proto_uses_selective_query_and_context_proto(self):
        adapter = kernel()
        payload = [
            {
                "dst": "10.0.0.0/8",
                "gateway": "172.20.130.6",
                "dev": "vpns0",
                "metric": 10,
                "flags": ["onlink"],
            }
        ]

        with mock.patch.object(
            adapter,
            "_run",
            return_value=completed(payload),
        ) as run:
            routes = adapter.list_routes_by_proto(vpng.VPN_ROUTE_PROTO)

        run.assert_called_once_with(
            (
                "ip",
                "-j",
                "-N",
                "-4",
                "route",
                "show",
                "table",
                "main",
                "proto",
                "202",
            )
        )
        route = next(iter(routes))
        self.assertEqual(route.proto, vpng.VPN_ROUTE_PROTO)

    def test_list_routes_by_proto_rejects_mismatched_or_unrepresentable_marker(self):
        adapter = kernel()

        with mock.patch.object(
            adapter,
            "_run",
            return_value=completed(
                [{"dst": "10.0.0.0/8", "protocol": 201, "flags": []}]
            ),
        ):
            with self.assertRaises(vpng.KernelError):
                adapter.list_routes_by_proto(vpng.VPN_ROUTE_PROTO)

        with mock.patch.object(
            adapter,
            "_run",
            return_value=completed(
                [{"dst": "10.0.0.0/8", "nhid": 42}]
            ),
        ):
            with self.assertRaises(vpng.KernelError):
                adapter.list_routes_by_proto(vpng.VPN_ROUTE_PROTO)

    def test_list_routes_missing_protocol_normalizes_to_boot(self):
        adapter = kernel()
        with mock.patch.object(
            adapter,
            "_run",
            return_value=completed(
                [{"dst": "198.51.100.0/24", "dev": "ens18", "flags": []}]
            ),
        ):
            routes = adapter.list_routes()

        route = next(iter(routes))
        self.assertEqual(route.proto, 3)

    def test_list_routes_rejects_multipath_and_nhid(self):
        adapter = kernel()

        for entry in (
            {
                "dst": "10.0.0.0/8",
                "nexthops": [{"gateway": "192.0.2.1", "dev": "ens18"}],
            },
            {"dst": "10.0.0.0/8", "nhid": 42},
            {"dst": "10.0.0.0/8", "multipath": []},
        ):
            with self.subTest(entry=entry):
                with mock.patch.object(
                    adapter,
                    "_run",
                    return_value=completed([entry]),
                ):
                    with self.assertRaises(vpng.KernelError):
                        adapter.list_routes()

    def test_list_routes_rejects_invalid_json_shape_and_type(self):
        adapter = kernel()

        with mock.patch.object(
            adapter,
            "_run",
            return_value=SimpleNamespace(stdout="{broken"),
        ):
            with self.assertRaises(vpng.KernelError):
                adapter.list_routes()

        with mock.patch.object(
            adapter,
            "_run",
            return_value=SimpleNamespace(stdout='{"dst":"10.0.0.0/8"}'),
        ):
            with self.assertRaises(vpng.KernelError):
                adapter.list_routes()

        with mock.patch.object(
            adapter,
            "_run",
            return_value=completed(
                [{"type": "local", "dst": "10.0.0.1/32"}]
            ),
        ):
            with self.assertRaises(vpng.KernelError):
                adapter.list_routes()

    def test_list_routes_rejects_non_main_and_structured_via(self):
        adapter = kernel()

        for entry in (
            {"dst": "10.0.0.0/8", "table": 100},
            {
                "dst": "10.0.0.0/8",
                "via": {"family": "inet6", "host": "2001:db8::1"},
            },
        ):
            with self.subTest(entry=entry):
                with mock.patch.object(
                    adapter,
                    "_run",
                    return_value=completed([entry]),
                ):
                    with self.assertRaises(vpng.KernelError):
                        adapter.list_routes()

    def test_route_add_materializes_complete_unicast_spec(self):
        adapter = kernel()
        route = unicast_route()

        with mock.patch.object(adapter, "_run") as run:
            adapter.add_route(route)

        run.assert_called_once_with(
            (
                "ip",
                "-4",
                "route",
                "add",
                "unicast",
                "10.0.0.0/8",
                "table",
                "main",
                "proto",
                "202",
                "metric",
                "10",
                "via",
                "172.20.130.6",
                "dev",
                "vpns0",
                "onlink",
            )
        )

    def test_route_delete_materializes_blackhole_spec(self):
        adapter = kernel()
        route = vpng.RouteSpec(
            destination=IPv4Network("10.0.0.0/8"),
            route_type=vpng.RouteType.BLACKHOLE,
            via=None,
            interface=None,
            metric=vpng.BLACKHOLE_METRIC,
            proto=vpng.BLACKHOLE_ROUTE_PROTO,
            onlink=False,
        )

        with mock.patch.object(adapter, "_run") as run:
            adapter.delete_route(route)

        run.assert_called_once_with(
            (
                "ip",
                "-4",
                "route",
                "del",
                "blackhole",
                "10.0.0.0/8",
                "table",
                "main",
                "proto",
                "201",
                "metric",
                "65536",
            )
        )

    def test_route_replace_uses_replace_verb(self):
        adapter = kernel()
        route = unicast_route(metric=None, onlink=False)

        with mock.patch.object(adapter, "_run") as run:
            adapter.replace_route(route)

        argv = run.call_args.args[0]
        self.assertEqual(argv[3], "replace")
        self.assertNotIn("metric", argv)
        self.assertNotIn("onlink", argv)

    def test_route_mutation_rejects_proto_none_without_running_ip(self):
        adapter = kernel()
        route = unicast_route(proto=None)

        with mock.patch.object(adapter, "_run") as run:
            for method in (
                adapter.add_route,
                adapter.delete_route,
                adapter.replace_route,
            ):
                with self.subTest(method=method.__name__):
                    with self.assertRaises(vpng.KernelError):
                        method(route)
        run.assert_not_called()

    def test_list_interfaces_keeps_ifindex_ipv4_and_empty_interfaces(self):
        adapter = kernel()
        payload = [
            {
                "ifindex": 1,
                "ifname": "lo",
                "addr_info": [
                    {"family": "inet", "local": "127.0.0.1"},
                    {"family": "inet6", "local": "::1"},
                ],
            },
            {
                "ifindex": 7,
                "ifname": "vpns0",
                "addr_info": [
                    {
                        "family": "inet",
                        "local": "172.20.130.1",
                        "peer": "172.20.130.6",
                    }
                ],
            },
            {"ifindex": 8, "ifname": "wg0", "addr_info": []},
        ]

        with mock.patch.object(
            adapter,
            "_run",
            return_value=completed(payload),
        ) as run:
            records = adapter.list_interfaces()

        run.assert_called_once_with(("ip", "-j", "addr", "show"))
        self.assertEqual(
            records,
            (
                vpng.InterfaceRecord(
                    "lo",
                    1,
                    frozenset({IPv4Address("127.0.0.1")}),
                ),
                vpng.InterfaceRecord(
                    "vpns0",
                    7,
                    frozenset({IPv4Address("172.20.130.1")}),
                ),
                vpng.InterfaceRecord("wg0", 8, frozenset()),
            ),
        )

    def test_list_interfaces_merges_only_same_name_same_ifindex(self):
        adapter = kernel()
        payload = [
            {
                "ifindex": 2,
                "ifname": "ens18",
                "addr_info": [{"family": "inet", "local": "10.0.0.1"}],
            },
            {
                "ifindex": 2,
                "ifname": "ens18",
                "addr_info": [{"family": "inet", "local": "10.0.0.2"}],
            },
        ]

        with mock.patch.object(
            adapter,
            "_run",
            return_value=completed(payload),
        ):
            records = adapter.list_interfaces()

        self.assertEqual(
            records,
            (
                vpng.InterfaceRecord(
                    "ens18",
                    2,
                    frozenset(
                        {
                            IPv4Address("10.0.0.1"),
                            IPv4Address("10.0.0.2"),
                        }
                    ),
                ),
            ),
        )

        payload[1]["ifindex"] = 3
        with mock.patch.object(
            adapter,
            "_run",
            return_value=completed(payload),
        ):
            with self.assertRaises(vpng.KernelError):
                adapter.list_interfaces()

    def test_list_interfaces_rejects_invalid_ifindex_and_inet_local(self):
        adapter = kernel()

        for entry in (
            {"ifname": "vpns0", "addr_info": []},
            {"ifindex": 0, "ifname": "vpns0", "addr_info": []},
            {
                "ifindex": 7,
                "ifname": "vpns0",
                "addr_info": [{"family": "inet"}],
            },
            {
                "ifindex": 7,
                "ifname": "vpns0",
                "addr_info": [{"family": "inet", "local": "not-an-ip"}],
            },
        ):
            with self.subTest(entry=entry):
                with mock.patch.object(
                    adapter,
                    "_run",
                    return_value=completed([entry]),
                ):
                    with self.assertRaises(vpng.KernelError):
                        adapter.list_interfaces()

    def test_list_interface_ipv4_uses_local_and_keeps_empty_interfaces(self):
        adapter = kernel()
        payload = [
            {
                "ifname": "lo",
                "addr_info": [
                    {"family": "inet", "local": "127.0.0.1", "prefixlen": 8}
                ],
            },
            {
                "ifname": "vpns0",
                "addr_info": [
                    {
                        "family": "inet",
                        "local": "172.20.130.1",
                        "peer": "172.20.130.6",
                        "prefixlen": 32,
                    }
                ],
            },
            {"ifname": "wg0", "addr_info": []},
            {
                "ifname": "v6only0",
                "addr_info": [
                    {
                        "family": "inet6",
                        "local": "2001:db8::1",
                        "prefixlen": 64,
                    }
                ],
            },
        ]

        with mock.patch.object(
            adapter,
            "_run",
            return_value=completed(payload),
        ) as run:
            addresses = adapter.list_interface_ipv4()

        run.assert_called_once_with(("ip", "-j", "addr", "show"))
        self.assertIsInstance(addresses, MappingProxyType)
        self.assertEqual(
            addresses["lo"],
            frozenset({IPv4Address("127.0.0.1")}),
        )
        self.assertEqual(
            addresses["vpns0"],
            frozenset({IPv4Address("172.20.130.1")}),
        )
        self.assertEqual(addresses["wg0"], frozenset())
        self.assertEqual(addresses["v6only0"], frozenset())

    def test_list_interface_ipv4_merges_duplicate_interface_records(self):
        adapter = kernel()
        payload = [
            {
                "ifname": "ens18",
                "addr_info": [{"family": "inet", "local": "10.0.0.1"}],
            },
            {
                "ifname": "ens18",
                "addr_info": [{"family": "inet", "local": "10.0.0.2"}],
            },
        ]

        with mock.patch.object(
            adapter,
            "_run",
            return_value=completed(payload),
        ):
            addresses = adapter.list_interface_ipv4()

        self.assertEqual(
            addresses["ens18"],
            frozenset(
                {
                    IPv4Address("10.0.0.1"),
                    IPv4Address("10.0.0.2"),
                }
            ),
        )

    def test_list_interface_ipv4_rejects_missing_or_invalid_local(self):
        adapter = kernel()

        for entry in (
            {"ifname": "vpns0", "addr_info": [{"family": "inet"}]},
            {
                "ifname": "vpns0",
                "addr_info": [{"family": "inet", "local": "not-an-ip"}],
            },
            {"ifname": "", "addr_info": []},
        ):
            with self.subTest(entry=entry):
                with mock.patch.object(
                    adapter,
                    "_run",
                    return_value=completed([entry]),
                ):
                    with self.assertRaises(vpng.KernelError):
                        adapter.list_interface_ipv4()


class KernelSystemAdapterTests(unittest.TestCase):
    def test_ip_forward_procfs_round_trip(self):
        adapter = kernel()
        with __import__("tempfile").TemporaryDirectory() as td:
            path = Path(td) / "ip_forward"
            path.write_text("0\n", encoding="ascii")
            with mock.patch("vpn_gatewayd.kernel.IP_FORWARD_PATH", path):
                self.assertFalse(adapter.get_ip_forward())
                adapter.set_ip_forward(True)
                self.assertEqual(path.read_text(encoding="ascii"), "1\n")
                self.assertTrue(adapter.get_ip_forward())
                adapter.set_ip_forward(False)
                self.assertEqual(path.read_text(encoding="ascii"), "0\n")

    def test_ip_forward_rejects_unexpected_value(self):
        adapter = kernel()
        with __import__("tempfile").TemporaryDirectory() as td:
            path = Path(td) / "ip_forward"
            path.write_text("2\n", encoding="ascii")
            with mock.patch("vpn_gatewayd.kernel.IP_FORWARD_PATH", path):
                with self.assertRaises(vpng.KernelError):
                    adapter.get_ip_forward()

    def test_ipv6_prerequisite_sysctls_are_read_as_boolean(self):
        adapter = kernel()
        with __import__("tempfile").TemporaryDirectory() as td:
            root = Path(td)
            all_forward = root / "all-forwarding"
            default_forward = root / "default-forwarding"
            default_disable = root / "default-disable"
            conf = root / "conf"
            interface_dir = conf / "vpns0"
            interface_dir.mkdir(parents=True)
            interface_disable = interface_dir / "disable_ipv6"

            all_forward.write_text("0\n", encoding="ascii")
            default_forward.write_text("0\n", encoding="ascii")
            default_disable.write_text("1\n", encoding="ascii")
            interface_disable.write_text("1\n", encoding="ascii")

            with (
                mock.patch(
                    "vpn_gatewayd.kernel.IPV6_ALL_FORWARDING_PATH",
                    all_forward,
                ),
                mock.patch(
                    "vpn_gatewayd.kernel.IPV6_DEFAULT_FORWARDING_PATH",
                    default_forward,
                ),
                mock.patch(
                    "vpn_gatewayd.kernel.IPV6_DEFAULT_DISABLE_PATH",
                    default_disable,
                ),
                mock.patch("vpn_gatewayd.kernel.IPV6_CONF_DIR", conf),
            ):
                self.assertFalse(adapter.get_ipv6_all_forwarding())
                self.assertFalse(adapter.get_ipv6_default_forwarding())
                self.assertTrue(adapter.get_ipv6_default_disabled())
                self.assertTrue(
                    adapter.get_interface_ipv6_disabled("vpns0")
                )

    def test_ipv6_prerequisite_sysctl_rejects_unexpected_value(self):
        adapter = kernel()
        with __import__("tempfile").TemporaryDirectory() as td:
            path = Path(td) / "forwarding"
            path.write_text("2\n", encoding="ascii")
            with mock.patch(
                "vpn_gatewayd.kernel.IPV6_ALL_FORWARDING_PATH",
                path,
            ):
                with self.assertRaises(vpng.KernelError):
                    adapter.get_ipv6_all_forwarding()

    def test_interface_ipv6_sysctl_rejects_path_like_name(self):
        adapter = kernel()
        with self.assertRaises(vpng.KernelError):
            adapter.get_interface_ipv6_disabled("../all")

    def test_iptables_save_reads_filter_then_nat_without_unsupported_wait(self):
        adapter = vpng.SubprocessKernelInterface(iptables_wait_seconds=7)
        responses = [
            SimpleNamespace(stdout="*filter\nCOMMIT\n"),
            SimpleNamespace(stdout="*nat\nCOMMIT\n"),
        ]
        with mock.patch.object(adapter, "_run", side_effect=responses) as run:
            snapshot = adapter.iptables_save()
        self.assertEqual(snapshot, "*filter\nCOMMIT\n*nat\nCOMMIT\n")
        self.assertEqual(
            run.call_args_list,
            [
                mock.call(("iptables-save", "-t", "filter")),
                mock.call(("iptables-save", "-t", "nat")),
            ],
        )

    def test_iptables_restore_uses_wait_and_noflush(self):
        adapter = vpng.SubprocessKernelInterface(iptables_wait_seconds=7)
        with mock.patch.object(adapter, "_run") as run:
            adapter.iptables_restore("*filter\nCOMMIT\n", noflush=True)
        run.assert_called_once_with(
            ("iptables-restore", "-w", "7", "--noflush"),
            input_text="*filter\nCOMMIT\n",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
