from __future__ import annotations

import unittest

from rou.aggressive_host_routing_manager import (
    AggressiveHostRoutingManagerStatus,
)


class AggressiveHostRoutingManagerShapeTests(unittest.TestCase):
    def test_projection_statuses_are_explicit(self):
        self.assertEqual(
            {item.value for item in AggressiveHostRoutingManagerStatus},
            {"inactive", "active", "degraded", "problem"},
        )


if __name__ == "__main__":
    unittest.main()
