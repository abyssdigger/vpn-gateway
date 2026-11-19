from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.binding import LogicalPathId
from rou.interface_identity import InterfaceIdentity
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.linux_probe_routing import (
    LinuxProbeRoutingBackend,
    LinuxProbeRoutingError,
)
from rou.network_policy_layout import ProbePolicyOwner
from rou.payload_routing_desired import ManagedRouteSpec, ManagedRouteType
from rou.probe_policy import ProbeRuleSpec
from rou.structural_routing_inventory import (
    ObservedManagedRoute,
    ObservedManagedRule,
)


PATH = LogicalPathId("device", 0, 0)
VPN = InterfaceIdentity("vpn0", 20)
TABLE = 0xC0000000
PRIORITY = 0x2000
TARGET = IPv4Address("198.51.100.7")


class FakeRunner:
    def __init__(self):
        self.commands = []

    def run(self, argv):
        self.commands.append(tuple(argv))
        return ""


def backend():
    runner = FakeRunner()
    return runner, LinuxProbeRoutingBackend(
        runner,
        "managed",
        NG3_LINUX_POLICY_PLATFORM,
    )


class LinuxProbeRoutingBackendTests(unittest.TestCase):
    def test_add_probe_route_reuses_shared_route_shape(self):
        runner, value = backend()
        value.add_route(
            ManagedRouteSpec(
                table=TABLE,
                destination=IPv4Network(f"{TARGET}/32"),
                route_type=ManagedRouteType.UNICAST,
                protocol=NG3_LINUX_POLICY_PLATFORM.path_route_protocol,
                metric=(
                    NG3_LINUX_POLICY_PLATFORM
                    .route_metrics.first_preference_metric
                ),
                path_id=PATH,
                endpoint=VPN,
            )
        )
        self.assertEqual(
            runner.commands[-1],
            (
                "ip", "-n", "managed", "-4", "route", "add",
                "unicast", f"{TARGET}/32",
                "table", str(TABLE),
                "proto", str(NG3_LINUX_POLICY_PLATFORM.path_route_protocol),
                "metric", str(
                    NG3_LINUX_POLICY_PLATFORM
                    .route_metrics.first_preference_metric
                ),
                "dev", "vpn0",
            ),
        )

    def test_delete_probe_guard_reuses_exact_observed_route_shape(self):
        runner, value = backend()
        value.delete_route(
            ObservedManagedRoute(
                table=TABLE,
                destination=IPv4Network("0.0.0.0/0"),
                route_type=ManagedRouteType.BLACKHOLE,
                protocol=NG3_LINUX_POLICY_PLATFORM.guard_route_protocol,
                metric=(
                    NG3_LINUX_POLICY_PLATFORM
                    .route_metrics.terminal_guard_metric
                ),
                scope=None,
                endpoint=None,
                gateway=None,
                onlink=False,
            )
        )
        self.assertEqual(
            runner.commands[-1],
            (
                "ip", "-n", "managed", "-4", "route", "del",
                "blackhole", "default",
                "table", str(TABLE),
                "proto", str(NG3_LINUX_POLICY_PLATFORM.guard_route_protocol),
                "metric", str(
                    NG3_LINUX_POLICY_PLATFORM
                    .route_metrics.terminal_guard_metric
                ),
            ),
        )

    def test_add_probe_rule_uses_exp065_shape(self):
        runner, value = backend()
        value.add_rule(
            ProbeRuleSpec(
                owner=ProbePolicyOwner("corp", PATH),
                priority=PRIORITY,
                process_uid=4242,
                target=TARGET,
                table=TABLE,
            )
        )
        self.assertEqual(
            runner.commands[-1],
            (
                "ip", "-n", "managed", "-4", "rule", "add",
                "priority", str(PRIORITY),
                "uidrange", "4242-4242",
                "ipproto", "icmp",
                "to", f"{TARGET}/32",
                "lookup", str(TABLE),
            ),
        )

    def test_delete_probe_rule_uses_exp065_exact_delete_shape(self):
        runner, value = backend()
        value.delete_rule(
            ObservedManagedRule(
                priority=PRIORITY,
                table=TABLE,
                ingress=None,
                destination=IPv4Network(f"{TARGET}/32"),
                uid_start=4242,
                uid_end=4242,
                ipproto=1,
            )
        )
        self.assertEqual(
            runner.commands[-1],
            (
                "ip", "-n", "managed", "-4", "rule", "del",
                "priority", str(PRIORITY),
                "uidrange", "4242-4242",
                "ipproto", "1",
                "to", f"{TARGET}/32",
                "lookup", str(TABLE),
            ),
        )

    def test_probe_backend_rejects_payload_owner_resources(self):
        runner, value = backend()
        with self.assertRaisesRegex(
            LinuxProbeRoutingError,
            "outside reserved probe",
        ):
            value.add_rule(
                ProbeRuleSpec(
                    owner=ProbePolicyOwner("corp", PATH),
                    priority=0x2000,
                    process_uid=4242,
                    target=TARGET,
                    table=0x80000000,
                )
            )
        with self.assertRaisesRegex(
            LinuxProbeRoutingError,
            "outside reserved probe",
        ):
            value.add_route(
                ManagedRouteSpec(
                    table=0x80000000,
                    destination=IPv4Network(f"{TARGET}/32"),
                    route_type=ManagedRouteType.UNICAST,
                    protocol=NG3_LINUX_POLICY_PLATFORM.path_route_protocol,
                    metric=1,
                    path_id=PATH,
                    endpoint=VPN,
                )
            )
        self.assertEqual(runner.commands, [])

    def test_delete_rejects_non_probe_selector_shape(self):
        runner, value = backend()
        with self.assertRaisesRegex(
            LinuxProbeRoutingError,
            "not an exact Release-1 probe",
        ):
            value.delete_rule(
                ObservedManagedRule(
                    priority=PRIORITY,
                    table=TABLE,
                    ingress=None,
                    destination=IPv4Network(f"{TARGET}/32"),
                    fwmark=0x1234,
                    fwmask=0xFFFF,
                )
            )
        self.assertEqual(runner.commands, [])

    def test_route_role_mismatch_is_rejected_before_mutation(self):
        runner, value = backend()
        with self.assertRaisesRegex(
            LinuxProbeRoutingError,
            "protocol/metric",
        ):
            value.add_route(
                ManagedRouteSpec(
                    table=TABLE,
                    destination=IPv4Network(f"{TARGET}/32"),
                    route_type=ManagedRouteType.UNICAST,
                    protocol=NG3_LINUX_POLICY_PLATFORM.guard_route_protocol,
                    metric=1,
                    path_id=PATH,
                    endpoint=VPN,
                )
            )
        self.assertEqual(runner.commands, [])


if __name__ == "__main__":
    unittest.main()
