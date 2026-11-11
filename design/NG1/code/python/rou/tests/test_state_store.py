import ipaddress
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.device_engine import (
    DeviceBindingState,
    ExpectedBindingState,
    InterfaceIdentity,
)
from rou.domain import ActiveConfig, Device, Direction, ExpectedInterface, InterfaceMatch, MatchKind, Profile
from rou.planner import PlannerRuntimeState
from rou.state_store import JsonRuntimeStateStore, StateStoreError
from rou.traffic_state import TrafficRuntimeState


def make_config(*, direction=Direction.OUTBOUND, quota=2, destination="10.0.0.0/8"):
    return ActiveConfig(
        {
            "oc": Device(
                "oc",
                True,
                (
                    ExpectedInterface(
                        InterfaceMatch(MatchKind.PREFIX, "vpns"),
                        quota,
                    ),
                ),
            )
        },
        {
            "corp": Profile(
                "corp",
                True,
                direction,
                (ipaddress.IPv4Network(destination),),
                ("oc",),
            )
        },
    )


def make_state():
    first = InterfaceIdentity("vpns00", 10)
    second = InterfaceIdentity("vpns01", 11)
    return PlannerRuntimeState(
        devices=DeviceBindingState(
            {
                ("oc", 0): ExpectedBindingState(
                    "oc",
                    0,
                    (first, second),
                )
            }
        ),
        traffic=TrafficRuntimeState(
            {
                ("corp", first): 1,
                ("corp", second): 2,
            }
        ),
    )


class StateStoreTests(unittest.TestCase):
    def test_round_trip_preserves_candidate_order_and_metrics(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            store = JsonRuntimeStateStore(path)
            state = make_state()

            store.save(state)
            loaded = store.load(make_config())

            self.assertEqual(loaded.state, state)
            self.assertEqual(loaded.dropped_entries, 0)
            self.assertEqual(
                stat.S_IMODE(path.stat().st_mode),
                0o600,
            )

    def test_policy_only_config_change_preserves_runtime_history(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            store = JsonRuntimeStateStore(path)
            store.save(make_state())

            loaded = store.load(
                make_config(
                    direction=Direction.BIDIRECTIONAL,
                    destination="192.168.0.0/16",
                )
            )
            self.assertEqual(loaded.state, make_state())
            self.assertEqual(loaded.dropped_entries, 0)

    def test_quota_reduction_drops_metric_outside_new_layout(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            store = JsonRuntimeStateStore(path)
            store.save(make_state())

            loaded = store.load(make_config(quota=1))
            metrics = loaded.state.traffic.normal_metrics

            self.assertEqual(
                metrics,
                {("corp", InterfaceIdentity("vpns00", 10)): 1},
            )
            self.assertGreaterEqual(loaded.dropped_entries, 1)

    def test_selector_change_drops_incompatible_candidate_and_metric(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            store = JsonRuntimeStateStore(path)
            store.save(make_state())

            config = ActiveConfig(
                {
                    "oc": Device(
                        "oc",
                        True,
                        (
                            ExpectedInterface(
                                InterfaceMatch(MatchKind.PREFIX, "wg"),
                                2,
                            ),
                        ),
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
            loaded = store.load(config)
            self.assertEqual(
                loaded.state.devices.expectations[("oc", 0)].candidate_order,
                (),
            )
            self.assertEqual(loaded.state.traffic.normal_metrics, {})
            self.assertGreater(loaded.dropped_entries, 0)

    def test_malformed_state_is_not_silently_treated_as_empty(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            path.write_text("{ definitely not json", encoding="utf-8")
            with self.assertRaises(StateStoreError):
                JsonRuntimeStateStore(path).load(make_config())

    def test_unknown_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 99,
                        "device_expectations": [],
                        "traffic_metrics": [],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(StateStoreError, "version"):
                JsonRuntimeStateStore(path).load(make_config())


if __name__ == "__main__":
    unittest.main()
