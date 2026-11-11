import ipaddress
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.device_engine import (
    DeviceBindingState,
    EnvironmentInterface,
    InterfaceIdentity,
    reconcile_devices,
)
from rou.domain import (
    ActiveConfig,
    Availability,
    Device,
    Direction,
    ExpectedInterface,
    InterfaceMatch,
    MatchKind,
    Profile,
)
from rou.traffic_state import (
    TrafficRuntimeState,
    committed_state_from_verified,
    project_normal_metrics,
)


def make_config(quota: int = 2) -> ActiveConfig:
    device = Device(
        name="oc",
        enabled=True,
        expected_interfaces=(
            ExpectedInterface(InterfaceMatch(MatchKind.PREFIX, "vpns"), quota),
        ),
    )
    profile = Profile(
        name="corp",
        enabled=True,
        direction=Direction.OUTBOUND,
        destinations=(ipaddress.IPv4Network("10.0.0.0/8"),),
        device_order=("oc",),
    )
    return ActiveConfig(devices={"oc": device}, profiles={"corp": profile})


def environment(*pairs: tuple[str, int]) -> tuple[EnvironmentInterface, ...]:
    return tuple(
        EnvironmentInterface(InterfaceIdentity(ifname, ifindex))
        for ifname, ifindex in pairs
    )


class DeviceEngineTests(unittest.TestCase):
    def test_initial_snapshot_order_is_admission_order(self):
        result = reconcile_devices(
            make_config(),
            DeviceBindingState.empty(),
            environment(("vpns02", 12), ("vpns00", 10), ("vpns01", 11)),
        )
        self.assertEqual(
            [item.identity.ifname for item in result.snapshot.bound],
            ["vpns02", "vpns00"],
        )
        self.assertEqual(
            [item.identity.ifname for item in result.snapshot.over_quota],
            ["vpns01"],
        )

    def test_survivors_not_reordered_by_new_snapshot_order(self):
        first = reconcile_devices(
            make_config(),
            DeviceBindingState.empty(),
            environment(("vpns00", 10), ("vpns01", 11), ("vpns02", 12)),
        )
        second = reconcile_devices(
            make_config(),
            first.next_state,
            environment(("vpns02", 12), ("vpns01", 11), ("vpns00", 10)),
        )
        self.assertEqual(
            [item.identity.ifname for item in second.snapshot.bound],
            ["vpns00", "vpns01"],
        )

    def test_overquota_promotes_after_bound_disappears(self):
        first = reconcile_devices(
            make_config(),
            DeviceBindingState.empty(),
            environment(("vpns00", 10), ("vpns01", 11), ("vpns02", 12)),
        )
        second = reconcile_devices(
            make_config(),
            first.next_state,
            environment(("vpns01", 11), ("vpns02", 12)),
        )
        self.assertEqual(
            [item.identity.ifname for item in second.snapshot.bound],
            ["vpns01", "vpns02"],
        )

    def test_same_name_new_ifindex_is_fresh_candidate(self):
        first = reconcile_devices(
            make_config(1),
            DeviceBindingState.empty(),
            environment(("vpns00", 10), ("vpns01", 11)),
        )
        second = reconcile_devices(
            make_config(1),
            first.next_state,
            environment(("vpns00", 20), ("vpns01", 11)),
        )
        self.assertEqual(
            second.snapshot.bound[0].identity,
            InterfaceIdentity("vpns01", 11),
        )
        self.assertEqual(
            second.snapshot.over_quota[0].identity,
            InterfaceIdentity("vpns00", 20),
        )

    def test_availability_is_normalized_without_changing_binding(self):
        identity = InterfaceIdentity("vpns00", 10)
        result = reconcile_devices(
            make_config(1),
            DeviceBindingState.empty(),
            environment(("vpns00", 10)),
            {identity: Availability.UNAVAILABLE},
        )
        self.assertEqual(
            result.snapshot.bound[0].availability,
            Availability.UNAVAILABLE,
        )

    def test_inactive_device_is_not_discovered(self):
        device = Device(
            name="oc",
            enabled=True,
            expected_interfaces=(
                ExpectedInterface(InterfaceMatch(MatchKind.PREFIX, "vpns"), 2),
            ),
        )
        config = ActiveConfig(devices={"oc": device}, profiles={})
        result = reconcile_devices(
            config,
            DeviceBindingState.empty(),
            environment(("vpns00", 10)),
        )
        self.assertEqual(result.snapshot.bound, ())
        self.assertEqual(dict(result.next_state.expectations), {})


class TrafficStateTests(unittest.TestCase):
    def test_metrics_follow_bound_order_and_stay_stable(self):
        device_first = reconcile_devices(
            make_config(),
            DeviceBindingState.empty(),
            environment(("vpns00", 10), ("vpns01", 11)),
        )
        projection_first = project_normal_metrics(
            make_config(),
            device_first.snapshot,
            TrafficRuntimeState.empty(),
        )
        self.assertEqual(
            [item.metric for item in projection_first.assignments],
            [1, 2],
        )
        committed = committed_state_from_verified(projection_first)

        device_second = reconcile_devices(
            make_config(),
            device_first.next_state,
            environment(("vpns01", 11), ("vpns00", 10)),
        )
        projection_second = project_normal_metrics(
            make_config(),
            device_second.snapshot,
            committed,
        )
        self.assertEqual(
            [
                (item.identity.ifname, item.metric)
                for item in projection_second.assignments
            ],
            [("vpns00", 1), ("vpns01", 2)],
        )

    def test_removed_slot_not_reused_before_verified_commit(self):
        device_first = reconcile_devices(
            make_config(),
            DeviceBindingState.empty(),
            environment(("vpns00", 10), ("vpns01", 11)),
        )
        committed = committed_state_from_verified(
            project_normal_metrics(
                make_config(),
                device_first.snapshot,
                TrafficRuntimeState.empty(),
            )
        )

        device_second = reconcile_devices(
            make_config(),
            device_first.next_state,
            environment(("vpns01", 11), ("vpns02", 12)),
        )
        projection_second = project_normal_metrics(
            make_config(),
            device_second.snapshot,
            committed,
        )
        self.assertEqual(
            [
                (item.identity.ifname, item.metric)
                for item in projection_second.assignments
            ],
            [("vpns01", 2)],
        )
        self.assertEqual(
            projection_second.waiting_for_slot,
            (("corp", InterfaceIdentity("vpns02", 12)),),
        )

    def test_slot_reusable_after_verified_removal_commit(self):
        device_first = reconcile_devices(
            make_config(),
            DeviceBindingState.empty(),
            environment(("vpns00", 10), ("vpns01", 11)),
        )
        committed_first = committed_state_from_verified(
            project_normal_metrics(
                make_config(),
                device_first.snapshot,
                TrafficRuntimeState.empty(),
            )
        )
        device_second = reconcile_devices(
            make_config(),
            device_first.next_state,
            environment(("vpns01", 11), ("vpns02", 12)),
        )
        removal_projection = project_normal_metrics(
            make_config(),
            device_second.snapshot,
            committed_first,
        )

        committed_after_removal = committed_state_from_verified(removal_projection)
        final_projection = project_normal_metrics(
            make_config(),
            device_second.snapshot,
            committed_after_removal,
        )
        self.assertEqual(
            {
                item.identity.ifname: item.metric
                for item in final_projection.assignments
            },
            {"vpns01": 2, "vpns02": 1},
        )
        self.assertEqual(final_projection.waiting_for_slot, ())


if __name__ == "__main__":
    unittest.main()
