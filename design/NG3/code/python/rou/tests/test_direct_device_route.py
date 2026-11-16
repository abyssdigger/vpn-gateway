from __future__ import annotations

import unittest

from rou.binding import LogicalPathId, PathBinding
from rou.direct_device_route import (
    DirectDeviceRouteRealizationError,
    realize_direct_device_path_routes,
)
from rou.interface_identity import InterfaceIdentity


A = LogicalPathId("a", 0, 0)
B = LogicalPathId("b", 1, 0)
EP_A = InterfaceIdentity("tun0", 10)
EP_B = InterfaceIdentity("wg0", 20)


class DirectDeviceRouteRealizationTests(unittest.TestCase):
    def test_realization_is_direct_device_and_deterministic(self):
        routes = realize_direct_device_path_routes(
            (
                PathBinding(B, EP_B),
                PathBinding(A, EP_A),
            )
        )

        self.assertEqual([route.path_id for route in routes], [A, B])
        self.assertEqual([route.endpoint for route in routes], [EP_A, EP_B])
        self.assertTrue(all(route.gateway is None for route in routes))
        self.assertTrue(all(route.onlink is False for route in routes))

    def test_empty_binding_set_is_valid_empty_realization(self):
        self.assertEqual(realize_direct_device_path_routes(()), ())

    def test_duplicate_path_binding_is_rejected(self):
        with self.assertRaisesRegex(
            DirectDeviceRouteRealizationError,
            "duplicate current binding",
        ):
            realize_direct_device_path_routes(
                (
                    PathBinding(A, EP_A),
                    PathBinding(A, EP_B),
                )
            )

    def test_one_endpoint_cannot_back_two_logical_paths(self):
        with self.assertRaisesRegex(
            DirectDeviceRouteRealizationError,
            "multiple logical paths",
        ):
            realize_direct_device_path_routes(
                (
                    PathBinding(A, EP_A),
                    PathBinding(B, EP_A),
                )
            )

    def test_non_binding_input_is_rejected(self):
        with self.assertRaisesRegex(
            DirectDeviceRouteRealizationError,
            "PathBinding",
        ):
            realize_direct_device_path_routes(
                (("not", "a binding"),)  # type: ignore[arg-type]
            )

    def test_malformed_direct_binding_contract_is_rejected(self):
        malformed = PathBinding(
            path_id="a",  # type: ignore[arg-type]
            endpoint=EP_A,
        )
        with self.assertRaisesRegex(
            DirectDeviceRouteRealizationError,
            "path_id",
        ):
            realize_direct_device_path_routes((malformed,))


if __name__ == "__main__":
    unittest.main()
