import ipaddress
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.command_backend import CommandResult, NamespaceBackend
from rou.device_engine import EnvironmentInterface, InterfaceIdentity
from rou.domain import (
    ActiveConfig,
    Device,
    Direction,
    ExpectedInterface,
    InterfaceMatch,
    MatchKind,
    NatMode,
    Profile,
)
from rou.environment import EnvironmentSnapshot, KernelRoute, KernelRule
from rou.nat_state import ConfigNatProvider
from rou.planner import PlannerRuntimeState, compile_planner_projection
from rou.status import inspect_runtime_status


def config():
    return ActiveConfig(
        {
            "oc": Device(
                "oc",
                True,
                (
                    ExpectedInterface(
                        InterfaceMatch(MatchKind.PREFIX, "vpns"),
                        1,
                    ),
                ),
                nat=NatMode.NONE,
            )
        },
        {
            "corp": Profile(
                "corp",
                True,
                Direction.OUTBOUND,
                (ipaddress.IPv4Network("10.0.0.0/8"),),
                ("oc",),
            )
        },
    )


def interfaces():
    return (
        EnvironmentInterface(InterfaceIdentity("host0", 2)),
        EnvironmentInterface(InterfaceIdentity("vpns00", 10)),
    )


def sysctls(forwarding=True):
    return (
        ("net.ipv4.ip_forward", "1" if forwarding else "0"),
        ("net.ipv4.conf.all.rp_filter", "0"),
        ("net.ipv4.conf.default.rp_filter", "0"),
        ("net.ipv4.fib_multipath_hash_policy", "0"),
        ("net.ipv6.conf.all.forwarding", "0"),
        ("net.ipv6.conf.default.forwarding", "0"),
        ("net.ipv6.conf.default.disable_ipv6", "1"),
        ("net.ipv4.conf.host0.rp_filter", "0"),
        ("net.ipv6.conf.host0.disable_ipv6", "1"),
        ("net.ipv4.conf.vpns00.rp_filter", "0"),
        ("net.ipv6.conf.vpns00.disable_ipv6", "1"),
    )


class FakeHostBackend:
    def __init__(self, filter_text: str, nat_text: str):
        self.filter_text = filter_text
        self.nat_text = nat_text

    def run(self, argv, *, input_text=None, check=True):
        stdout = ""
        if argv[-4:] == ("iptables-legacy-save", "-c", "-t", "filter"):
            stdout = self.filter_text
        elif argv[-4:] == ("iptables-legacy-save", "-c", "-t", "nat"):
            stdout = self.nat_text
        return CommandResult(argv, 0, stdout, "")


def observed_from_projection(projection, *, extra_routes=()):
    routes = tuple(
        KernelRoute(
            item.table,
            item.destination,
            item.route_type,
            item.protocol,
            item.metric,
            item.ifname,
            item.nexthops,
        )
        for item in projection.kernel.routes
    ) + tuple(extra_routes)
    rules = tuple(
        KernelRule(
            item.priority,
            item.table,
            item.action,
            destination=item.destination,
            iif=item.iif,
        )
        for item in projection.kernel.rules
    )
    return EnvironmentSnapshot(
        interfaces=interfaces(),
        routes=routes,
        rules=rules,
        sysctls=sysctls(True),
    )


class RuntimeStatusTests(unittest.TestCase):
    def make_projection(self):
        cfg = config()
        seed = EnvironmentSnapshot(
            interfaces=interfaces(),
            sysctls=sysctls(True),
        )
        projection = compile_planner_projection(
            cfg,
            PlannerRuntimeState.empty(),
            seed,
            ConfigNatProvider(),
            None,
            None,
        )
        return cfg, projection

    def test_complete_live_state_is_verified(self):
        cfg, projection = self.make_projection()
        observed = observed_from_projection(projection)
        host = FakeHostBackend(
            projection.firewall.canonical_save,
            projection.nat.canonical_save,
        )
        result = inspect_runtime_status(
            cfg,
            "rou0",
            PlannerRuntimeState.empty(),
            observed,
            NamespaceBackend("rou0", host),
            ConfigNatProvider(),
        )
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(
            [item.identity.ifname for item in result.projection.bindings.bound],
            ["vpns00"],
        )

    def test_route_drift_is_reported(self):
        cfg, projection = self.make_projection()
        foreign = KernelRoute(
            projection.kernel.owned_tables[0],
            ipaddress.IPv4Network("203.0.113.0/24"),
            "unicast",
            99,
            5,
            "vpns00",
            (),
        )
        observed = observed_from_projection(
            projection,
            extra_routes=(foreign,),
        )
        host = FakeHostBackend(
            projection.firewall.canonical_save,
            projection.nat.canonical_save,
        )
        result = inspect_runtime_status(
            cfg,
            "rou0",
            PlannerRuntimeState.empty(),
            observed,
            NamespaceBackend("rou0", host),
            ConfigNatProvider(),
        )
        self.assertFalse(result.ok)
        self.assertTrue(
            any("unexpected routes" in error for error in result.errors)
        )

    def test_namespace_mismatch_is_rejected(self):
        cfg, projection = self.make_projection()
        with self.assertRaisesRegex(ValueError, "namespace mismatch"):
            inspect_runtime_status(
                cfg,
                "rou0",
                PlannerRuntimeState.empty(),
                observed_from_projection(projection),
                NamespaceBackend(
                    "other",
                    FakeHostBackend(
                        projection.firewall.canonical_save,
                        projection.nat.canonical_save,
                    ),
                ),
                ConfigNatProvider(),
            )


if __name__ == "__main__":
    unittest.main()
