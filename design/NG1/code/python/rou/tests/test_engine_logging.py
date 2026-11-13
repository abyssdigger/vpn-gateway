import ipaddress
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.command_backend import CommandResult
from rou.device_engine import (
    DeviceBindingState,
    EnvironmentInterface,
    InterfaceIdentity,
    reconcile_devices,
)
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
from rou.kernel_allocation import compile_kernel_allocation
from rou.kernel_state import compile_kernel_desired_state
from rou.nft_policy import compile_nft_filter_state, compile_nft_nat_state
from rou.planner import PlannerRuntimeState, reconcile_once
from _nft_fake import FakeNftBackend
from rou.traffic_state import (
    TrafficRuntimeState,
    project_normal_metrics,
)


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


def sysctls():
    return (
        ("net.ipv4.ip_forward", "1"),
        ("net.ipv4.conf.all.rp_filter", "0"),
        ("net.ipv4.conf.default.rp_filter", "0"),
        ("net.ipv6.conf.all.forwarding", "0"),
        ("net.ipv6.conf.default.forwarding", "0"),
        ("net.ipv6.conf.default.disable_ipv6", "1"),
        ("net.ipv4.conf.host0.rp_filter", "0"),
        ("net.ipv6.conf.host0.disable_ipv6", "1"),
        ("net.ipv4.conf.vpns00.rp_filter", "0"),
        ("net.ipv6.conf.vpns00.disable_ipv6", "1"),
    )


class EngineLoggingTests(unittest.TestCase):
    def test_device_and_traffic_emit_stable_debug_subjects(self):
        cfg = config()
        with self.assertLogs("rou.device_engine", level="DEBUG") as device_logs:
            devices = reconcile_devices(
                cfg,
                DeviceBindingState.empty(),
                interfaces(),
            )
        self.assertTrue(
            any("device-reconcile-start" in line for line in device_logs.output)
        )
        self.assertTrue(
            any("device-reconcile-result" in line for line in device_logs.output)
        )

        with self.assertLogs("rou.traffic_state", level="DEBUG") as traffic_logs:
            project_normal_metrics(
                cfg,
                devices.snapshot,
                TrafficRuntimeState.empty(),
            )
        self.assertTrue(
            any("traffic-project-start" in line for line in traffic_logs.output)
        )
        self.assertTrue(
            any("traffic-project-result" in line for line in traffic_logs.output)
        )

    def test_planner_steady_state_logs_decision_and_commit(self):
        cfg = config()
        devices = reconcile_devices(
            cfg,
            DeviceBindingState.empty(),
            interfaces(),
        )
        metrics = project_normal_metrics(
            cfg,
            devices.snapshot,
            TrafficRuntimeState.empty(),
        )
        allocation = compile_kernel_allocation(cfg)
        kernel = compile_kernel_desired_state(
            cfg,
            devices.snapshot,
            metrics,
            allocation,
        )
        firewall = compile_nft_filter_state(cfg, devices.snapshot)
        nat = compile_nft_nat_state(cfg, devices.snapshot)

        snapshot = EnvironmentSnapshot(
            interfaces=interfaces(),
            routes=tuple(
                KernelRoute(
                    item.table,
                    item.destination,
                    item.route_type,
                    item.protocol,
                    item.metric,
                    item.ifname,
                    item.nexthops,
                )
                for item in kernel.routes
            ),
            rules=tuple(
                KernelRule(
                    item.priority,
                    item.table,
                    item.action,
                    destination=item.destination,
                    iif=item.iif,
                )
                for item in kernel.rules
            ),
            sysctls=sysctls(),
        )
        backend = FakeNftBackend(firewall, nat)

        with self.assertLogs("rou.planner", level="DEBUG") as planner_logs:
            result = reconcile_once(
                cfg,
                "rou0",
                PlannerRuntimeState.empty(),
                backend,
                collect_snapshot=lambda _ns, _backend: snapshot,
            )

        self.assertFalse(result.changed_kernel)
        self.assertTrue(
            any(
                "planner-decision steady-verified-open" in line
                for line in planner_logs.output
            )
        )
        self.assertTrue(
            any("planner-commit steady" in line for line in planner_logs.output)
        )


if __name__ == "__main__":
    unittest.main()
