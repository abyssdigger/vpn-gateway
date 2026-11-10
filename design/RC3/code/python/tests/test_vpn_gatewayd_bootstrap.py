#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from types import MappingProxyType
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import vpn_gatewayd as vpng


def make_config() -> object:
    profile = vpng.VpnProfileConfig(
        profile_id="primary",
        interface=vpng.InterfaceSelector.parse("vpns0"),
        network=IPv4Network("172.20.130.0/29"),
        routes=(IPv4Network("10.0.0.0/8"),),
        allowed_sources=(),
    )
    return vpng.GatewayConfig(
        reconcile_interval=10.0,
        common_allowed_sources=(IPv4Network("10.200.200.8/32"),),
        vpns=MappingProxyType({"primary": profile}),
    )


def make_daemon(kernel=None):
    if kernel is None:
        kernel = mock.Mock()
    daemon = vpng.VpnGatewayDaemon(
        config_path=Path("/dev/null"),
        kernel=kernel,
        config_loader=mock.Mock(),
    )
    daemon._install_config(make_config())
    return daemon


def desired_routes(daemon):
    state = daemon._resolve_profile_interfaces(
        (
            vpng.InterfaceRecord(
                "vpns0",
                7,
                frozenset({IPv4Address("172.20.130.1")}),
            ),
        )
    )
    allocations, _ = daemon._build_prefix_metric_state(state)
    return daemon._derive_desired_routes(
        interface_state_by_profile=state,
        prefix_metric_allocations_by_profile=allocations,
    )


def route(*, kind, proto, metric, via=None, interface=None, onlink=False):
    return vpng.RouteSpec(
        destination=IPv4Network("10.0.0.0/8"),
        route_type=kind,
        via=None if via is None else IPv4Address(via),
        interface=interface,
        metric=metric,
        proto=proto,
        onlink=onlink,
    )


class BootstrapTests(unittest.TestCase):
    def test_snapshot_uses_exact_binding_for_policy_and_routes(self):
        daemon = make_daemon()
        snapshot = daemon._build_reconciliation_snapshot(
            (
                vpng.InterfaceRecord(
                    "vpns0",
                    7,
                    frozenset({IPv4Address("172.20.130.1")}),
                ),
            )
        )

        nat_rules = snapshot.desired_full_policy.nat.chain(
            "VPNG-PRIMARY-NAT"
        ).rules
        self.assertTrue(any("-o vpns0 " in rule for rule in nat_rules))

        unicast = [
            item
            for item in snapshot.desired_routes_by_profile["primary"]
            if item.route_type is vpng.RouteType.UNICAST
        ]
        self.assertEqual(len(unicast), 1)
        self.assertEqual(unicast[0].interface, "vpns0")
        self.assertIsNone(unicast[0].via)
        self.assertFalse(unicast[0].onlink)
        self.assertEqual(unicast[0].metric, 10)

    def test_global_ipv6_prerequisite_rejects_enabled_forwarding(self):
        kernel = mock.Mock()
        kernel.get_ipv6_all_forwarding.return_value = True
        kernel.get_ipv6_default_forwarding.return_value = False
        kernel.get_ipv6_default_disabled.return_value = True

        daemon = make_daemon(kernel)
        with self.assertRaises(vpng.ReconciliationError):
            daemon._check_global_ipv6_prerequisites()

    def test_firewall_cleanup_removes_only_vpng_namespace(self):
        daemon = make_daemon()
        snapshot = """*filter
:INPUT ACCEPT [0:0]
:FORWARD ACCEPT [0:0]
:VPNG-PRIMARY-INPUT - [0:0]
-A INPUT -j VPNG-PRIMARY-INPUT
-A INPUT -p tcp --dport 22 -j ACCEPT
-A VPNG-PRIMARY-INPUT -j RETURN
COMMIT
*nat
:POSTROUTING ACCEPT [0:0]
:VPNG-PRIMARY-NAT - [0:0]
-A POSTROUTING -j VPNG-PRIMARY-NAT
-A POSTROUTING -o ens18 -j MASQUERADE
-A VPNG-PRIMARY-NAT -j RETURN
COMMIT
"""
        payload = daemon._build_firewall_cleanup_payload(snapshot)
        self.assertIn("-D INPUT -j VPNG-PRIMARY-INPUT", payload)
        self.assertIn("-F VPNG-PRIMARY-INPUT", payload)
        self.assertIn("-X VPNG-PRIMARY-INPUT", payload)
        self.assertIn("-D POSTROUTING -j VPNG-PRIMARY-NAT", payload)
        self.assertNotIn("--dport 22", payload)
        self.assertNotIn("-o ens18 -j MASQUERADE", payload)

    def test_apply_plan_orders_blackhole_before_destructive_and_unicast(self):
        kernel = mock.Mock()
        daemon = make_daemon(kernel)
        blackhole = route(
            kind=vpng.RouteType.BLACKHOLE,
            proto=vpng.BLACKHOLE_ROUTE_PROTO,
            metric=vpng.BLACKHOLE_METRIC,
        )
        unicast = route(
            kind=vpng.RouteType.UNICAST,
            proto=vpng.VPN_ROUTE_PROTO,
            metric=10,
            via=None,
            interface="vpns0",
            onlink=False,
        )
        old = route(
            kind=vpng.RouteType.UNREACHABLE,
            proto=99,
            metric=1,
        )
        replace = route(
            kind=vpng.RouteType.UNICAST,
            proto=vpng.VPN_ROUTE_PROTO,
            metric=20,
            via=None,
            interface="vpns1",
            onlink=False,
        )
        plan = vpng.ReconciliationPlan(
            route_adds=frozenset({unicast, blackhole}),
            route_deletes=frozenset({old}),
            route_replaces=frozenset({replace}),
        )

        daemon._apply_plan(plan)
        self.assertEqual(
            kernel.method_calls,
            [
                mock.call.add_route(blackhole),
                mock.call.delete_route(old),
                mock.call.replace_route(replace),
                mock.call.add_route(unicast),
            ],
        )

    def test_verify_plan_requires_exact_authoritative_state(self):
        daemon = make_daemon()
        profile = daemon.profiles["primary"]
        desired = desired_routes(daemon)["primary"]
        desired_map = MappingProxyType({"primary": desired})

        ok = daemon._verify_plan(
            all_kernel_routes=desired,
            desired_routes_by_profile=desired_map,
        )
        self.assertIs(
            ok.profile_results["primary"].result,
            vpng.ApplyStateResult.SUCCESS,
        )
        self.assertEqual(ok.owned_routes_by_profile["primary"], desired)

        competing = route(
            kind=vpng.RouteType.UNREACHABLE,
            proto=99,
            metric=1,
        )
        bad = daemon._verify_plan(
            all_kernel_routes=desired | frozenset({competing}),
            desired_routes_by_profile=desired_map,
        )
        self.assertIs(
            bad.profile_results["primary"].result,
            vpng.ApplyStateResult.FAIL,
        )

    def test_cleanup_is_config_independent_and_keeps_blackhole_until_firewall_removed(self):
        proto202 = route(
            kind=vpng.RouteType.UNICAST,
            proto=vpng.VPN_ROUTE_PROTO,
            metric=10,
            via=None,
            interface="vpns0",
            onlink=False,
        )
        blackhole = route(
            kind=vpng.RouteType.BLACKHOLE,
            proto=vpng.BLACKHOLE_ROUTE_PROTO,
            metric=vpng.BLACKHOLE_METRIC,
        )

        class FakeKernel:
            def __init__(self):
                self.forwarding = True
                self.routes = {proto202, blackhole}
                self.firewall_present = True
                self.events = []

            def set_ip_forward(self, enabled):
                self.events.append(("forward", enabled))
                self.forwarding = enabled

            def get_ip_forward(self):
                return self.forwarding

            def list_routes(self):
                raise vpng.KernelError(
                    "foreign multipath route makes full inventory unavailable"
                )

            def list_routes_by_proto(self, proto):
                return frozenset(
                    item for item in self.routes if item.proto == proto
                )

            def delete_route(self, item):
                self.events.append(("delete", item))
                if item is blackhole:
                    self.assert_firewall_removed()
                self.routes.remove(item)

            def assert_firewall_removed(self):
                if self.firewall_present:
                    raise AssertionError("blackhole removed before firewall cleanup")

            def iptables_save(self):
                if self.firewall_present:
                    return """*filter
:INPUT ACCEPT [0:0]
:FORWARD ACCEPT [0:0]
:VPNG-X - [0:0]
-A INPUT -j VPNG-X
-A VPNG-X -j RETURN
COMMIT
*nat
:POSTROUTING ACCEPT [0:0]
COMMIT
"""
                return """*filter
:INPUT ACCEPT [0:0]
:FORWARD ACCEPT [0:0]
COMMIT
*nat
:POSTROUTING ACCEPT [0:0]
COMMIT
"""

            def iptables_restore(self, payload, *, noflush=True):
                self.events.append("firewall_cleanup")
                self.firewall_present = False

        kernel = FakeKernel()
        daemon = vpng.VpnGatewayDaemon(
            config_path=Path("/dev/null"),
            kernel=kernel,
            config_loader=mock.Mock(),
        )
        daemon.cleanup()
        self.assertFalse(kernel.forwarding)
        self.assertEqual(kernel.routes, set())
        self.assertLess(
            kernel.events.index(("delete", proto202)),
            kernel.events.index("firewall_cleanup"),
        )
        self.assertLess(
            kernel.events.index("firewall_cleanup"),
            kernel.events.index(("delete", blackhole)),
        )

    def test_cleanup_rejects_reserved_proto201_marker_conflict(self):
        conflict = route(
            kind=vpng.RouteType.UNICAST,
            proto=vpng.BLACKHOLE_ROUTE_PROTO,
            metric=vpng.BLACKHOLE_METRIC,
            via=None,
            interface="vpns0",
            onlink=False,
        )

        kernel = mock.Mock()
        kernel.get_ip_forward.return_value = False
        kernel.list_routes_by_proto.side_effect = (
            frozenset(),
            frozenset({conflict}),
        )
        kernel.iptables_save.return_value = """*filter
:INPUT ACCEPT [0:0]
:FORWARD ACCEPT [0:0]
COMMIT
*nat
:POSTROUTING ACCEPT [0:0]
COMMIT
"""

        daemon = vpng.VpnGatewayDaemon(
            config_path=Path("/dev/null"),
            kernel=kernel,
            config_loader=mock.Mock(),
        )

        with self.assertRaises(vpng.CleanupError):
            daemon.cleanup()

        kernel.delete_route.assert_not_called()

    def test_apply_enables_forwarding_only_after_firewall_and_routes_verify(self):
        class FakeKernel:
            def __init__(self):
                self.events = []
                self.forwarding = False
                self.routes = set()

            def get_ipv6_all_forwarding(self):
                self.events.append("ipv6_all_forwarding")
                return False

            def get_ipv6_default_forwarding(self):
                self.events.append("ipv6_default_forwarding")
                return False

            def get_ipv6_default_disabled(self):
                self.events.append("ipv6_default_disable")
                return True

            def get_interface_ipv6_disabled(self, interface):
                self.events.append(("ipv6_interface_disable", interface))
                return True

            def list_routes(self):
                self.events.append("list_routes")
                return frozenset(self.routes)

            def list_interfaces(self):
                self.events.append("list_interfaces")
                return (
                    vpng.InterfaceRecord(
                        "vpns0",
                        7,
                        frozenset({IPv4Address("172.20.130.1")}),
                    ),
                )

            def add_route(self, item):
                self.events.append(("add", item.route_type))
                self.routes.add(item)

            def delete_route(self, item):
                raise AssertionError("unexpected delete")

            def replace_route(self, item):
                raise AssertionError("unexpected replace")

            def set_ip_forward(self, enabled):
                self.events.append(("forward", enabled))
                self.forwarding = enabled

            def get_ip_forward(self):
                self.events.append("get_forward")
                return self.forwarding

        kernel = FakeKernel()
        daemon = make_daemon(kernel)

        def filter_restore(*args, **kwargs):
            del args, kwargs
            kernel.events.append("filter_restore")

        def nat_restore(*args, **kwargs):
            del args, kwargs
            kernel.events.append("nat_restore")

        with (
            mock.patch.object(
                daemon,
                "_restore_filter_policy",
                side_effect=filter_restore,
            ),
            mock.patch.object(
                daemon,
                "_restore_nat_policy",
                side_effect=nat_restore,
            ),
            mock.patch.object(
                daemon,
                "_check_firewall_nat_policy",
                return_value=vpng.FirewallCheck(
                    vpng.FirewallSafety.SAFE,
                    None,
                ),
            ),
        ):
            daemon.apply()

        filter_index = kernel.events.index("filter_restore")
        nat_index = kernel.events.index("nat_restore")
        blackhole_index = kernel.events.index(
            ("add", vpng.RouteType.BLACKHOLE)
        )
        unicast_index = kernel.events.index(
            ("add", vpng.RouteType.UNICAST)
        )
        forward_index = kernel.events.index(("forward", True))

        self.assertLess(filter_index, nat_index)
        self.assertLess(nat_index, blackhole_index)
        self.assertLess(blackhole_index, unicast_index)
        self.assertLess(unicast_index, forward_index)
        self.assertEqual(
            daemon.profiles["primary"].owned_routes,
            frozenset(kernel.routes),
        )
        self.assertEqual(
            daemon.profiles["primary"].committed_active_bindings,
            (vpng.InterfaceBinding("vpns0", 7),),
        )
        self.assertIs(daemon.state, vpng.DaemonState.ACTIVE)


    def test_apply_allows_verified_zero_path_and_enters_degraded(self):
        class FakeKernel:
            def __init__(self):
                self.forwarding = False
                self.routes = set()

            def get_ipv6_all_forwarding(self): return False
            def get_ipv6_default_forwarding(self): return False
            def get_ipv6_default_disabled(self): return True
            def list_interfaces(self): return ()
            def list_routes(self): return frozenset(self.routes)
            def add_route(self, item): self.routes.add(item)
            def delete_route(self, item): self.routes.remove(item)
            def replace_route(self, item): self.routes.add(item)
            def set_ip_forward(self, enabled): self.forwarding = enabled
            def get_ip_forward(self): return self.forwarding

        kernel = FakeKernel()
        daemon = make_daemon(kernel)
        with (
            mock.patch.object(daemon, "_restore_filter_policy"),
            mock.patch.object(daemon, "_restore_nat_policy"),
            mock.patch.object(
                daemon,
                "_check_firewall_nat_policy",
                return_value=vpng.FirewallCheck(vpng.FirewallSafety.SAFE, None),
            ),
        ):
            daemon.apply()

        self.assertIs(daemon.state, vpng.DaemonState.DEGRADED)
        self.assertEqual(daemon.profiles["primary"].committed_active_bindings, ())
        self.assertTrue(kernel.forwarding)


if __name__ == "__main__":
    unittest.main(verbosity=2)
