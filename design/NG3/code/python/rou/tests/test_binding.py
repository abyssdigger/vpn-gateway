from __future__ import annotations

import unittest

from rou.binding import (
    BindingProjectionError,
    DeviceBindingState,
    LogicalPathId,
    project_device_bindings,
)
from rou.domain import DeviceBindingIntent, ExpectedInterfaceSelector, SelectorKind
from rou.interface_identity import InterfaceIdentity
from support_structural_config import parse_structural_config


def prefix(device_id: str = "oc", quota: int = 2, value: str = "vpns") -> DeviceBindingIntent:
    return DeviceBindingIntent(
        device_id=device_id,
        expected_interfaces=(
            ExpectedInterfaceSelector(SelectorKind.PREFIX, value, quota),
        ),
    )


def ids(*pairs: tuple[str, int]) -> tuple[InterfaceIdentity, ...]:
    return tuple(InterfaceIdentity(ifname, ifindex) for ifname, ifindex in pairs)


class BindingProjectionTests(unittest.TestCase):
    def test_initial_snapshot_fills_slots_in_observation_order(self):
        result = project_device_bindings(
            (prefix(quota=2),),
            DeviceBindingState.empty(),
            ids(("vpns02", 12), ("vpns00", 10), ("vpns01", 11)),
        )
        self.assertEqual(
            [(item.path_id.slot_index, item.endpoint.ifname) for item in result.bindings],
            [(0, "vpns02"), (1, "vpns00")],
        )
        self.assertEqual([item.endpoint.ifname for item in result.waiting], ["vpns01"])

    def test_snapshot_reorder_does_not_move_survivors(self):
        first = project_device_bindings(
            (prefix(),),
            DeviceBindingState.empty(),
            ids(("vpns00", 10), ("vpns01", 11), ("vpns02", 12)),
        )
        second = project_device_bindings(
            (prefix(),),
            first.next_state,
            ids(("vpns02", 12), ("vpns01", 11), ("vpns00", 10)),
        )
        self.assertEqual(
            [(item.path_id.slot_index, item.endpoint.ifname) for item in second.bindings],
            [(0, "vpns00"), (1, "vpns01")],
        )
        self.assertEqual([item.endpoint.ifname for item in second.waiting], ["vpns02"])

    def test_disappearance_does_not_reuse_slot_until_later_commit(self):
        first = project_device_bindings(
            (prefix(),),
            DeviceBindingState.empty(),
            ids(("vpns00", 10), ("vpns01", 11), ("vpns02", 12)),
        )
        removal = project_device_bindings(
            (prefix(),),
            first.next_state,
            ids(("vpns01", 11), ("vpns02", 12)),
        )
        self.assertEqual(
            [(item.path_id.slot_index, item.endpoint.ifname) for item in removal.bindings],
            [(1, "vpns01")],
        )
        self.assertEqual([item.endpoint.ifname for item in removal.waiting], ["vpns02"])

        promoted = project_device_bindings(
            (prefix(),),
            removal.next_state,
            ids(("vpns02", 12), ("vpns01", 11)),
        )
        self.assertEqual(
            [(item.path_id.slot_index, item.endpoint.ifname) for item in promoted.bindings],
            [(0, "vpns02"), (1, "vpns01")],
        )

    def test_same_name_new_ifindex_is_fresh_and_waits_one_pass(self):
        first = project_device_bindings(
            (prefix(quota=1),),
            DeviceBindingState.empty(),
            ids(("vpns00", 10), ("vpns01", 11)),
        )
        replacement = project_device_bindings(
            (prefix(quota=1),),
            first.next_state,
            ids(("vpns00", 20), ("vpns01", 11)),
        )
        self.assertEqual(replacement.bindings, ())
        self.assertEqual(
            [item.endpoint for item in replacement.waiting],
            [InterfaceIdentity("vpns01", 11), InterfaceIdentity("vpns00", 20)],
        )
        promoted = project_device_bindings(
            (prefix(quota=1),),
            replacement.next_state,
            ids(("vpns00", 20), ("vpns01", 11)),
        )
        self.assertEqual(promoted.bindings[0].endpoint, InterfaceIdentity("vpns01", 11))
        self.assertEqual(promoted.bindings[0].path_id, LogicalPathId("oc", 0, 0))

    def test_newcomer_does_not_evict_survivor(self):
        first = project_device_bindings(
            (prefix(quota=1),),
            DeviceBindingState.empty(),
            ids(("vpns01", 11),),
        )
        second = project_device_bindings(
            (prefix(quota=1),),
            first.next_state,
            ids(("vpns00", 10), ("vpns01", 11)),
        )
        self.assertEqual(second.bindings[0].endpoint, InterfaceIdentity("vpns01", 11))
        self.assertEqual(second.waiting[0].endpoint, InterfaceIdentity("vpns00", 10))

    def test_selector_change_resets_only_selector_lifecycle(self):
        original = prefix(quota=1, value="vpns")
        first = project_device_bindings(
            (original,),
            DeviceBindingState.empty(),
            ids(("vpns00", 10),),
        )
        changed = DeviceBindingIntent(
            device_id="oc",
            expected_interfaces=(
                ExpectedInterfaceSelector(SelectorKind.EXACT, "vpns00", 1),
            ),
        )
        second = project_device_bindings(
            (changed,),
            first.next_state,
            ids(("vpns00", 10),),
        )
        self.assertEqual(second.bindings[0].endpoint, InterfaceIdentity("vpns00", 10))
        self.assertEqual(second.bindings[0].path_id, LogicalPathId("oc", 0, 0))

    def test_inactive_device_state_is_dropped(self):
        first = project_device_bindings(
            (prefix(),),
            DeviceBindingState.empty(),
            ids(("vpns00", 10),),
        )
        second = project_device_bindings((), first.next_state, ids(("vpns00", 10),))
        self.assertEqual(second.bindings, ())
        self.assertEqual(dict(second.next_state.selectors), {})

    def test_invalid_inventory_and_ambiguous_selector_fail(self):
        with self.assertRaisesRegex(BindingProjectionError, "repeats ifname"):
            project_device_bindings(
                (prefix(),),
                DeviceBindingState.empty(),
                ids(("vpns00", 10), ("vpns00", 20)),
            )
        with self.assertRaisesRegex(BindingProjectionError, "multiple active selectors"):
            project_device_bindings(
                (prefix("a", 1, "vpn"), prefix("b", 1, "vpn0")),
                DeviceBindingState.empty(),
                ids(("vpn0", 10),),
            )

    def test_structural_config_binding_seam_preserves_selector_policy_order(self):
        cfg = parse_structural_config("""
[device.oc]
enabled = true
expected_interfaces = ["wg0", "vpns*/2"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")
        result = project_device_bindings(
            cfg.device_binding_intents,
            DeviceBindingState.empty(),
            ids(("vpns01", 12), ("wg0", 7), ("vpns00", 11)),
        )
        self.assertEqual(
            [
                (item.path_id.selector_index, item.path_id.slot_index, item.endpoint.ifname)
                for item in result.bindings
            ],
            [(0, 0, "wg0"), (1, 0, "vpns01"), (1, 1, "vpns00")],
        )


if __name__ == "__main__":
    unittest.main()
