import ipaddress
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.command_backend import CommandResult
from rou.device_engine import (
    DeviceBindingSnapshot,
    EnvironmentInterface,
    InterfaceIdentity,
    reconcile_devices,
)
from rou.domain import ActiveConfig, Device, NatMode, Direction, ExpectedInterface, InterfaceMatch, MatchKind, Profile
from rou.environment import EnvironmentSnapshot, KernelRoute, KernelRule
from rou.firewall_state import compile_filter_state
from rou.kernel_allocation import compile_kernel_allocation
from rou.kernel_state import compile_kernel_desired_state
from rou.nat_state import ExplicitNoNatProvider, UnresolvedNatProvider
from rou.planner import (
    PlannerError,
    PlannerRetryRequired,
    PlannerRuntimeState,
    reconcile_once,
)
from rou.traffic_state import committed_state_from_verified, project_normal_metrics


class FakeHostBackend:
    def __init__(self, filter_save: str, nat_save: str):
        self.filter_save = filter_save
        self.nat_save = nat_save
        self.calls = []

    def run(self, argv, *, input_text=None, check=True):
        self.calls.append((argv, input_text, check))
        stdout = ""
        if argv[-1:] == ("iptables-legacy-restore",) and input_text:
            if input_text.startswith("*filter"):
                self.filter_save = input_text.strip()
            elif input_text.startswith("*nat"):
                self.nat_save = input_text.strip()
        if argv[-4:] == ("iptables-legacy-save", "-c", "-t", "filter"):
            stdout = self.filter_save
        elif argv[-4:] == ("iptables-legacy-save", "-c", "-t", "nat"):
            stdout = self.nat_save
        return CommandResult(argv, 0, stdout, "")


def config():
    return ActiveConfig(
        {
            "oc": Device(
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


def interfaces(ifindex=10):
    return (
        EnvironmentInterface(InterfaceIdentity("host0", 2)),
        EnvironmentInterface(InterfaceIdentity("vpns00", ifindex)),
    )



def interfaces_two():
    return (
        EnvironmentInterface(InterfaceIdentity("host0", 2)),
        EnvironmentInterface(InterfaceIdentity("vpns00", 10)),
        EnvironmentInterface(InterfaceIdentity("vpns01", 11)),
    )


def interfaces_survivor():
    return (
        EnvironmentInterface(InterfaceIdentity("host0", 2)),
        EnvironmentInterface(InterfaceIdentity("vpns01", 11)),
    )

def sysctls(forwarding: bool, ifname="vpns00"):
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
        (f"net.ipv4.conf.{ifname}.rp_filter", "0"),
        (f"net.ipv6.conf.{ifname}.disable_ipv6", "1"),
    )


def expected_for(initial_interfaces):
    cfg = config()
    state = PlannerRuntimeState.empty()
    devices = reconcile_devices(cfg, state.devices, initial_interfaces)
    metrics = project_normal_metrics(cfg, devices.snapshot, state.traffic)
    allocation = compile_kernel_allocation(cfg)
    kernel = compile_kernel_desired_state(
        cfg,
        devices.snapshot,
        metrics,
        allocation,
    )
    firewall = compile_filter_state(cfg, devices.snapshot)
    nat = ExplicitNoNatProvider().compile(cfg, devices.snapshot)
    return devices, metrics, kernel, firewall, nat


def observed_kernel_snapshot(kernel, *, forwarding, ifs=None):
    if ifs is None:
        ifs = interfaces()
    routes = tuple(
        KernelRoute(
            r.table,
            r.destination,
            r.route_type,
            r.protocol,
            r.metric,
            r.ifname,
            r.nexthops,
        )
        for r in kernel.routes
    )
    rules = tuple(
        KernelRule(
            r.priority,
            r.table,
            r.action,
            destination=r.destination,
            iif=r.iif,
        )
        for r in kernel.rules
    )
    vpn_name = next(
        (item.identity.ifname for item in ifs if item.identity.ifname.startswith("vpns")),
        "vpns00",
    )
    return EnvironmentSnapshot(
        interfaces=ifs,
        routes=routes,
        rules=rules,
        sysctls=sysctls(forwarding, vpn_name),
    )


class SnapshotQueue:
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.calls = 0

    def __call__(self, namespace, backend):
        self.calls += 1
        if not self.snapshots:
            raise AssertionError("unexpected snapshot collection")
        return self.snapshots.pop(0)


class PlannerTests(unittest.TestCase):
    def test_verified_open_state_commits_without_mutation(self):
        _, _, kernel, firewall, nat = expected_for(interfaces())
        snap = observed_kernel_snapshot(kernel, forwarding=True)
        backend = FakeHostBackend(firewall.canonical_save, nat.canonical_save)
        queue = SnapshotQueue([snap])

        result = reconcile_once(
            config(),
            "rou0",
            PlannerRuntimeState.empty(),
            backend,
            ExplicitNoNatProvider(),
            collect_snapshot=queue,
        )

        self.assertFalse(result.changed_kernel)
        self.assertFalse(result.needs_immediate_reconcile)
        self.assertEqual(queue.calls, 1)
        self.assertFalse(
            any("net.ipv4.ip_forward=0" in call[0] for call in backend.calls)
        )

    def test_drift_rebuilds_under_barrier_then_opens_after_final_verify(self):
        _, _, kernel, firewall, nat = expected_for(interfaces())
        initial = EnvironmentSnapshot(
            interfaces=interfaces(),
            routes=(),
            rules=(),
            sysctls=sysctls(True),
        )
        barrier = EnvironmentSnapshot(
            interfaces=interfaces(),
            routes=(),
            rules=(),
            sysctls=sysctls(False),
        )
        prepared = barrier
        applied = observed_kernel_snapshot(kernel, forwarding=False)
        final = observed_kernel_snapshot(kernel, forwarding=True)
        backend = FakeHostBackend(firewall.canonical_save, nat.canonical_save)
        queue = SnapshotQueue([initial, barrier, prepared, applied, final])

        result = reconcile_once(
            config(),
            "rou0",
            PlannerRuntimeState.empty(),
            backend,
            ExplicitNoNatProvider(),
            collect_snapshot=queue,
        )

        self.assertTrue(result.changed_kernel)
        writes = [
            arg
            for call, _stdin, _check in backend.calls
            for arg in call
            if arg.startswith("net.ipv4.ip_forward=")
        ]
        self.assertGreaterEqual(writes.count("net.ipv4.ip_forward=0"), 1)
        self.assertEqual(writes[-1], "net.ipv4.ip_forward=1")


    def test_bound_member_disappearance_repairs_without_global_barrier(self):
        cfg = config()

        previous_devices = reconcile_devices(
            cfg,
            PlannerRuntimeState.empty().devices,
            interfaces_two(),
        )
        previous_metrics = project_normal_metrics(
            cfg,
            previous_devices.snapshot,
            PlannerRuntimeState.empty().traffic,
        )
        committed = PlannerRuntimeState(
            previous_devices.next_state,
            committed_state_from_verified(previous_metrics),
        )
        allocation = compile_kernel_allocation(cfg)
        previous_firewall = compile_filter_state(
            cfg,
            previous_devices.snapshot,
        )
        previous_nat = ExplicitNoNatProvider().compile(
            cfg,
            previous_devices.snapshot,
        )

        current_devices = reconcile_devices(
            cfg,
            committed.devices,
            interfaces_survivor(),
        )
        current_metrics = project_normal_metrics(
            cfg,
            current_devices.snapshot,
            committed.traffic,
        )
        current_kernel = compile_kernel_desired_state(
            cfg,
            current_devices.snapshot,
            current_metrics,
            allocation,
        )

        observed_routes = tuple(
            KernelRoute(
                r.table,
                r.destination,
                r.route_type,
                r.protocol,
                r.metric,
                r.ifname,
                r.nexthops,
            )
            for r in current_kernel.routes
            if r.metric != 65535
        )
        observed_rules = tuple(
            KernelRule(
                r.priority,
                r.table,
                r.action,
                destination=r.destination,
                iif=r.iif,
            )
            for r in current_kernel.rules
        )
        initial = EnvironmentSnapshot(
            interfaces=interfaces_survivor(),
            routes=observed_routes,
            rules=observed_rules,
            sysctls=sysctls(True, "vpns01"),
        )
        applied = observed_kernel_snapshot(
            current_kernel,
            forwarding=True,
            ifs=interfaces_survivor(),
        )

        backend = FakeHostBackend(
            previous_firewall.canonical_save,
            previous_nat.canonical_save,
        )
        queue = SnapshotQueue([initial, initial, applied])

        result = reconcile_once(
            cfg,
            "rou0",
            committed,
            backend,
            ExplicitNoNatProvider(),
            collect_snapshot=queue,
        )

        self.assertTrue(result.changed_kernel)
        self.assertEqual(queue.calls, 3)
        forwarding_writes = [
            arg
            for call, _stdin, _check in backend.calls
            for arg in call
            if arg.startswith("net.ipv4.ip_forward=")
        ]
        self.assertEqual(forwarding_writes, [])
        self.assertTrue(
            any(
                call[-5:] == ("ip", "route", "flush", "table", "1")
                for call, _stdin, _check in backend.calls
            )
        )
        self.assertFalse(
            any(
                len(call) >= 6
                and call[-3:-1] == ("ip", "rule")
                for call, _stdin, _check in backend.calls
            )
        )

    def test_verified_state_is_persisted_before_forwarding_open(self):
        _, _, kernel, firewall, nat = expected_for(interfaces())
        initial = EnvironmentSnapshot(
            interfaces=interfaces(),
            routes=(),
            rules=(),
            sysctls=sysctls(True),
        )
        barrier = EnvironmentSnapshot(
            interfaces=interfaces(),
            routes=(),
            rules=(),
            sysctls=sysctls(False),
        )
        applied = observed_kernel_snapshot(kernel, forwarding=False)
        final = observed_kernel_snapshot(kernel, forwarding=True)
        backend = FakeHostBackend(firewall.canonical_save, nat.canonical_save)
        queue = SnapshotQueue([initial, barrier, barrier, applied, final])
        events = []

        def persist(state):
            events.append(("persist", state))

        original_run = backend.run
        def recording_run(argv, *, input_text=None, check=True):
            if "net.ipv4.ip_forward=1" in argv:
                events.append(("open", argv))
            return original_run(argv, input_text=input_text, check=check)
        backend.run = recording_run

        reconcile_once(
            config(),
            "rou0",
            PlannerRuntimeState.empty(),
            backend,
            ExplicitNoNatProvider(),
            collect_snapshot=queue,
            persist_verified_state=persist,
        )

        self.assertEqual(events[0][0], "persist")
        self.assertEqual(events[1][0], "open")

    def test_persistence_failure_prevents_forwarding_open(self):
        _, _, _kernel, firewall, nat = expected_for(interfaces())
        initial = EnvironmentSnapshot(
            interfaces=interfaces(),
            routes=(),
            rules=(),
            sysctls=sysctls(True),
        )
        barrier = EnvironmentSnapshot(
            interfaces=interfaces(),
            routes=(),
            rules=(),
            sysctls=sysctls(False),
        )
        backend = FakeHostBackend(firewall.canonical_save, nat.canonical_save)
        queue = SnapshotQueue([initial, barrier, barrier])

        def fail_persist(_state):
            raise OSError("disk full")

        with self.assertRaisesRegex(PlannerError, "disk full"):
            reconcile_once(
                config(),
                "rou0",
                PlannerRuntimeState.empty(),
                backend,
                ExplicitNoNatProvider(),
                collect_snapshot=queue,
                persist_verified_state=fail_persist,
            )

        writes = [
            arg
            for call, _stdin, _check in backend.calls
            for arg in call
            if arg.startswith("net.ipv4.ip_forward=")
        ]
        self.assertNotIn("net.ipv4.ip_forward=1", writes)

    def test_interface_churn_during_preparation_requests_retry_and_stays_closed(self):
        _, _, _kernel, firewall, nat = expected_for(interfaces())
        initial = EnvironmentSnapshot(
            interfaces=interfaces(),
            sysctls=sysctls(True),
        )
        barrier = EnvironmentSnapshot(
            interfaces=interfaces(),
            sysctls=sysctls(False),
        )
        changed_ifs = interfaces(ifindex=11)
        prepared = EnvironmentSnapshot(
            interfaces=changed_ifs,
            sysctls=sysctls(False),
        )
        backend = FakeHostBackend(firewall.canonical_save, nat.canonical_save)
        queue = SnapshotQueue([initial, barrier, prepared])

        with self.assertRaises(PlannerRetryRequired):
            reconcile_once(
                config(),
                "rou0",
                PlannerRuntimeState.empty(),
                backend,
                ExplicitNoNatProvider(),
                collect_snapshot=queue,
            )

        writes = [
            arg
            for call, _stdin, _check in backend.calls
            for arg in call
            if arg.startswith("net.ipv4.ip_forward=")
        ]
        self.assertIn("net.ipv4.ip_forward=0", writes)
        self.assertNotIn("net.ipv4.ip_forward=1", writes)

    def test_unresolved_nat_policy_fails_closed(self):
        initial = EnvironmentSnapshot(
            interfaces=interfaces(),
            sysctls=sysctls(True),
        )
        backend = FakeHostBackend("", "")
        queue = SnapshotQueue([initial])

        with self.assertRaisesRegex(PlannerError, "NAT policy"):
            reconcile_once(
                config(),
                "rou0",
                PlannerRuntimeState.empty(),
                backend,
                UnresolvedNatProvider(),
                collect_snapshot=queue,
            )

        self.assertTrue(
            any(
                "net.ipv4.ip_forward=0" in call[0]
                for call in backend.calls
            )
        )


if __name__ == "__main__":
    unittest.main()
