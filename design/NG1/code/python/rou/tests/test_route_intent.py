import ipaddress
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.device_engine import BoundInterface, DeviceBindingSnapshot, InterfaceIdentity
from rou.domain import (
    NatMode,
    ActiveConfig,
    Device,
    Direction,
    ExpectedInterface,
    InterfaceMatch,
    MatchKind,
    Profile,
)
from rou.metrics import BLACKHOLE_METRIC
from rou.route_intent import compile_profile_route_intents
from rou.traffic_state import MetricAssignment, TrafficProjection


def make_config() -> ActiveConfig:
    device = Device(
        "oc",
        True,
        (
            ExpectedInterface(
                InterfaceMatch(MatchKind.PREFIX, "vpns"),
                2,
            ),
        ),
        nat=NatMode.NONE,
    )
    profile = Profile(
        "corp",
        True,
        Direction.OUTBOUND,
        (
            ipaddress.IPv4Network("10.0.0.0/8"),
            ipaddress.IPv4Network("192.168.1.0/24"),
        ),
        ("oc",),
    )
    return ActiveConfig({"oc": device}, {"corp": profile})


class RouteIntentTests(unittest.TestCase):
    def test_all_metric_assigned_bound_members_get_normal_routes(self):
        first = InterfaceIdentity("vpns00", 10)
        second = InterfaceIdentity("vpns01", 11)
        bindings = DeviceBindingSnapshot(
            (
                BoundInterface("oc", 0, first),
                BoundInterface("oc", 0, second),
            ),
            (),
        )
        metrics = TrafficProjection(
            (
                MetricAssignment("corp", "oc", 0, first, 1),
                MetricAssignment("corp", "oc", 0, second, 2),
            ),
            (),
        )

        out = compile_profile_route_intents(make_config(), bindings, metrics)[0]

        self.assertEqual(out.terminal_blackhole_metric, BLACKHOLE_METRIC)
        self.assertEqual(
            [
                (str(item.destination), item.identity.ifname, item.metric)
                for item in out.normal_routes
            ],
            [
                ("10.0.0.0/8", "vpns00", 1),
                ("10.0.0.0/8", "vpns01", 2),
                ("192.168.1.0/24", "vpns00", 1),
                ("192.168.1.0/24", "vpns01", 2),
            ],
        )

    def test_waiting_member_has_no_route_until_metric_is_assigned(self):
        first = InterfaceIdentity("vpns00", 10)
        second = InterfaceIdentity("vpns01", 11)
        bindings = DeviceBindingSnapshot(
            (
                BoundInterface("oc", 0, first),
                BoundInterface("oc", 0, second),
            ),
            (),
        )
        metrics = TrafficProjection(
            (MetricAssignment("corp", "oc", 0, first, 1),),
            (("corp", second),),
        )

        out = compile_profile_route_intents(make_config(), bindings, metrics)[0]

        self.assertEqual(
            {item.identity.ifname for item in out.normal_routes},
            {"vpns00"},
        )

    def test_profile_without_path_is_blackhole_only(self):
        out = compile_profile_route_intents(
            make_config(),
            DeviceBindingSnapshot((), ()),
            TrafficProjection((), ()),
        )[0]

        self.assertEqual(out.normal_routes, ())
        self.assertEqual(out.terminal_blackhole_metric, BLACKHOLE_METRIC)

    def test_metric_assignment_must_reference_bound_interface(self):
        identity = InterfaceIdentity("vpns00", 10)
        metrics = TrafficProjection(
            (MetricAssignment("corp", "oc", 0, identity, 1),),
            (),
        )

        with self.assertRaisesRegex(ValueError, "unbound interface"):
            compile_profile_route_intents(
                make_config(),
                DeviceBindingSnapshot((), ()),
                metrics,
            )

    def test_metric_assignment_expected_index_must_match_binding(self):
        identity = InterfaceIdentity("vpns00", 10)
        bindings = DeviceBindingSnapshot(
            (BoundInterface("oc", 0, identity),),
            (),
        )
        metrics = TrafficProjection(
            (MetricAssignment("corp", "oc", 1, identity, 1),),
            (),
        )

        with self.assertRaisesRegex(ValueError, "ExpectedInterface mismatch"):
            compile_profile_route_intents(make_config(), bindings, metrics)

    def test_metric_assignment_profile_must_be_enabled(self):
        identity = InterfaceIdentity("vpns00", 10)
        bindings = DeviceBindingSnapshot(
            (BoundInterface("oc", 0, identity),),
            (),
        )
        metrics = TrafficProjection(
            (MetricAssignment("missing", "oc", 0, identity, 1),),
            (),
        )

        with self.assertRaisesRegex(ValueError, "unknown/disabled Profile"):
            compile_profile_route_intents(make_config(), bindings, metrics)


if __name__ == "__main__":
    unittest.main()
