from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.alpha_probe_projection import (
    AlphaProbeProjectionError,
    build_alpha_explicit_probe_projection,
)
from rou.binding import LogicalPathId
from rou.domain import Direction
from rou.payload_profile import PayloadProfileRequest
from rou.release1_config import (
    AvailabilityCheckConfig,
    ProfileRelease1Config,
)


A = LogicalPathId("wg", 0, 0)
B = LogicalPathId("oc", 0, 0)


def profile(profile_id="corp", paths=(A, B)):
    return PayloadProfileRequest(
        profile_id=profile_id,
        direction=Direction.OUTBOUND,
        destinations=(IPv4Network("10.0.0.0/8"),),
        ordered_paths=tuple(paths),
    )


def config(check):
    return ProfileRelease1Config(
        ordinary_gateway_nat=False,
        route_return=False,
        availability_check=check,
    )


class AlphaProbeProjectionTests(unittest.TestCase):
    def test_explicit_target_expands_to_every_current_path(self):
        projection = build_alpha_explicit_probe_projection(
            (profile(),),
            {
                "corp": config(
                    AvailabilityCheckConfig(
                        "icmp",
                        IPv4Address("198.51.100.7"),
                    )
                )
            },
        )
        self.assertEqual(
            tuple(item.owner.profile_id for item in projection.intents),
            ("corp", "corp"),
        )
        self.assertEqual(
            tuple(item.owner.path_id for item in projection.intents),
            (A, B),
        )
        self.assertEqual(
            tuple(item.target for item in projection.intents),
            (
                IPv4Address("198.51.100.7"),
                IPv4Address("198.51.100.7"),
            ),
        )
        self.assertEqual(
            tuple(demand.owner for demand in projection.routing_demands),
            tuple(item.owner for item in projection.intents),
        )

    def test_profile_without_check_contributes_no_probe_demand(self):
        projection = build_alpha_explicit_probe_projection(
            (profile(),),
            {"corp": config(None)},
        )
        self.assertEqual(projection.intents, ())
        self.assertEqual(projection.routing_demands, ())

    def test_profile_without_current_paths_has_no_probe_subject_yet(self):
        projection = build_alpha_explicit_probe_projection(
            (profile(paths=()),),
            {
                "corp": config(
                    AvailabilityCheckConfig(
                        "icmp",
                        IPv4Address("198.51.100.7"),
                    )
                )
            },
        )
        self.assertEqual(projection.intents, ())
        self.assertEqual(projection.routing_demands, ())

    def test_bare_icmp_is_rejected_not_guessed(self):
        with self.assertRaisesRegex(
            AlphaProbeProjectionError,
            "target derivation requires integration-specific evidence",
        ):
            build_alpha_explicit_probe_projection(
                (profile(),),
                {
                    "corp": config(
                        AvailabilityCheckConfig("icmp", None)
                    )
                },
            )

    def test_missing_release1_profile_config_is_rejected(self):
        with self.assertRaisesRegex(
            AlphaProbeProjectionError,
            "missing Release-1 config",
        ):
            build_alpha_explicit_probe_projection(
                (profile(),),
                {},
            )


if __name__ == "__main__":
    unittest.main()
