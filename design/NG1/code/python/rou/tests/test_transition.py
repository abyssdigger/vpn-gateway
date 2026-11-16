import ipaddress
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.device_engine import BoundInterface, DeviceBindingSnapshot, InterfaceIdentity
from rou.domain import Availability
from rou.environment import EnvironmentSnapshot, KernelRoute, KernelRule
from rou.firewall_state import FirewallDesiredState
from rou.kernel_state import KernelDesiredState, KernelRouteSpec, KernelRuleSpec
from rou.nat_state import NatDesiredState
from rou.transition import TransitionKind, assess_binding_lifecycle


def bindings(ifindex: int | None):
    if ifindex is None:
        return DeviceBindingSnapshot((), ())
    return DeviceBindingSnapshot(
        (
            BoundInterface(
                "oc",
                0,
                InterfaceIdentity("vpns00", ifindex),
                Availability.UNKNOWN,
            ),
        ),
        (),
    )


def desired(ifname: str | None):
    routes = []
    if ifname is not None:
        routes.append(
            KernelRouteSpec(
                1,
                ipaddress.IPv4Network("10.0.0.0/8"),
                "unicast",
                202,
                1,
                ifname,
                (),
            )
        )
    routes.append(
        KernelRouteSpec(
            1,
            ipaddress.IPv4Network("0.0.0.0/0"),
            "blackhole",
            201,
            65536,
            None,
            (),
        )
    )
    routes = tuple(routes)
    rules = (
        KernelRuleSpec(
            1,
            "host0",
            ipaddress.IPv4Network("10.0.0.0/8"),
            1,
            "to_tbl",
        ),
        KernelRuleSpec(
            2,
            "host0",
            None,
            None,
            "unreachable",
        ),
    )
    return KernelDesiredState(routes, rules, (1,))


def observed_from(
    routes,
    rules,
):
    return EnvironmentSnapshot(
        (),
        routes=tuple(routes),
        rules=tuple(rules),
        sysctls=(("net.ipv4.ip_forward", "1"),),
    )


def rule_observed():
    return (
        KernelRule(
            1,
            1,
            "to_tbl",
            destination=ipaddress.IPv4Network("10.0.0.0/8"),
            iif="host0",
        ),
        KernelRule(
            2,
            None,
            "unreachable",
            iif="host0",
        ),
    )


class TransitionTests(unittest.TestCase):
    def test_bound_member_disappearance_is_lifecycle_when_owned_state_is_known(self):
        previous = desired("vpns00")
        current = desired(None)
        result = assess_binding_lifecycle(
            previous,
            current,
            FirewallDesiredState("", "old-filter"),
            FirewallDesiredState("", "new-filter"),
            NatDesiredState("", "old-nat"),
            NatDesiredState("", "new-nat"),
            bindings(10),
            bindings(None),
            observed_from(
                (
                    KernelRoute(
                        1,
                        ipaddress.IPv4Network("0.0.0.0/0"),
                        "blackhole",
                        201,
                        65536,
                        None,
                        (),
                    ),
                ),
                rule_observed(),
            ),
            "old-filter",
            "old-nat",
        )
        self.assertEqual(result.kind, TransitionKind.BINDING_LIFECYCLE)

    def test_foreign_route_in_owned_table_is_structural(self):
        previous = desired("vpns00")
        current = desired(None)
        foreign = KernelRoute(
            1,
            ipaddress.IPv4Network("192.0.2.0/24"),
            "unicast",
            99,
            10,
            "host0",
            (),
        )
        result = assess_binding_lifecycle(
            previous,
            current,
            FirewallDesiredState("", "old-filter"),
            FirewallDesiredState("", "new-filter"),
            NatDesiredState("", "old-nat"),
            NatDesiredState("", "new-nat"),
            bindings(10),
            bindings(None),
            observed_from(
                (
                    foreign,
                    KernelRoute(
                        1,
                        ipaddress.IPv4Network("0.0.0.0/0"),
                        "blackhole",
                        201,
                        65536,
                        None,
                        (),
                    ),
                ),
                rule_observed(),
            ),
            "old-filter",
            "old-nat",
        )
        self.assertEqual(result.kind, TransitionKind.STRUCTURAL)
        self.assertTrue(
            any("outside previous/new" in reason for reason in result.reasons)
        )

    def test_foreign_filter_generation_is_structural(self):
        result = assess_binding_lifecycle(
            desired("vpns00"),
            desired(None),
            FirewallDesiredState("", "old-filter"),
            FirewallDesiredState("", "new-filter"),
            NatDesiredState("", "old-nat"),
            NatDesiredState("", "new-nat"),
            bindings(10),
            bindings(None),
            observed_from((), rule_observed()),
            "foreign-filter",
            "old-nat",
        )
        self.assertEqual(result.kind, TransitionKind.STRUCTURAL)

    def test_same_name_new_ifindex_requires_structural_barrier(self):
        result = assess_binding_lifecycle(
            desired("vpns00"),
            desired("vpns00"),
            FirewallDesiredState("", "same-filter"),
            FirewallDesiredState("", "same-filter"),
            NatDesiredState("", "same-nat"),
            NatDesiredState("", "same-nat"),
            bindings(10),
            bindings(11),
            observed_from(
                (
                    KernelRoute(
                        1,
                        ipaddress.IPv4Network("10.0.0.0/8"),
                        "unicast",
                        202,
                        1,
                        "vpns00",
                        (),
                    ),
                    KernelRoute(
                        1,
                        ipaddress.IPv4Network("0.0.0.0/0"),
                        "blackhole",
                        201,
                        65536,
                        None,
                        (),
                    ),
                ),
                rule_observed(),
            ),
            "same-filter",
            "same-nat",
        )
        self.assertEqual(result.kind, TransitionKind.STRUCTURAL)
        self.assertTrue(
            any("same-name/new-ifindex" in reason for reason in result.reasons)
        )


    def test_foreign_rule_above_terminal_is_structural(self):
        previous = desired("vpns00")
        current = desired(None)
        rules = list(rule_observed())
        rules.append(
            KernelRule(
                1000,
                254,
                "to_tbl",
                destination=ipaddress.IPv4Network("203.0.113.0/24"),
                iif="host0",
            )
        )
        result = assess_binding_lifecycle(
            previous,
            current,
            FirewallDesiredState("", "old-filter"),
            FirewallDesiredState("", "new-filter"),
            NatDesiredState("", "old-nat"),
            NatDesiredState("", "new-nat"),
            bindings(10),
            bindings(None),
            observed_from((), tuple(rules)),
            "old-filter",
            "old-nat",
        )
        self.assertEqual(result.kind, TransitionKind.STRUCTURAL)
        self.assertTrue(
            any("RPDB" in reason for reason in result.reasons)
        )


    def test_missing_terminal_blackhole_is_structural(self):
        result = assess_binding_lifecycle(
            desired("vpns00"),
            desired(None),
            FirewallDesiredState("", "old-filter"),
            FirewallDesiredState("", "new-filter"),
            NatDesiredState("", "old-nat"),
            NatDesiredState("", "new-nat"),
            bindings(10),
            bindings(None),
            observed_from((), rule_observed()),
            "old-filter",
            "old-nat",
        )
        self.assertEqual(result.kind, TransitionKind.STRUCTURAL)
        self.assertTrue(
            any("terminal Profile blackhole" in reason for reason in result.reasons)
        )


if __name__ == "__main__":
    unittest.main()
