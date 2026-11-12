from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.availability import annotate_bindings, normalize_availability
from rou.device_engine import (
    BoundInterface,
    DeviceBindingSnapshot,
    InterfaceIdentity,
)
from rou.domain import Availability


class AvailabilityBoundaryTests(unittest.TestCase):
    def bindings(self):
        return DeviceBindingSnapshot(
            bound=(
                BoundInterface(
                    "oc",
                    0,
                    InterfaceIdentity("vpns00", 10),
                ),
            ),
            over_quota=(
                BoundInterface(
                    "oc",
                    0,
                    InterfaceIdentity("vpns01", 11),
                ),
            ),
        )

    def test_stale_same_name_generation_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "non-current binding identity vpns00@9",
        ):
            normalize_availability(
                self.bindings(),
                {
                    InterfaceIdentity("vpns00", 9):
                    Availability.UNAVAILABLE,
                },
            )

    def test_non_enum_availability_is_rejected(self):
        with self.assertRaisesRegex(
            TypeError,
            "normalized Availability enum",
        ):
            normalize_availability(
                self.bindings(),
                {
                    InterfaceIdentity("vpns00", 10):
                    "unavailable",  # type: ignore[dict-item]
                },
            )

    def test_annotation_preserves_binding_order_and_identity(self):
        before = self.bindings()
        after = annotate_bindings(
            before,
            {
                InterfaceIdentity("vpns00", 10):
                Availability.UNAVAILABLE,
            },
        )

        self.assertEqual(
            [item.identity for item in before.bound],
            [item.identity for item in after.bound],
        )
        self.assertEqual(
            [item.identity for item in before.over_quota],
            [item.identity for item in after.over_quota],
        )
        self.assertEqual(
            after.bound[0].availability,
            Availability.UNAVAILABLE,
        )
        self.assertEqual(
            after.over_quota[0].availability,
            Availability.UNKNOWN,
        )


if __name__ == "__main__":
    unittest.main()
