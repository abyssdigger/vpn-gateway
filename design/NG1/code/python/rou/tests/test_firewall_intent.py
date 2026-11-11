import ipaddress
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.domain import ActiveConfig, Device, Direction, Profile
from rou.firewall_intent import FlowDirection, Verdict, compile_new_flow_intents


def enabled_device(name: str) -> Device:
    return Device(name=name, enabled=True)


class FirewallIntentTests(unittest.TestCase):
    def test_every_profile_device_prefix_has_both_explicit_verdicts(self):
        config = ActiveConfig(
            devices={"oc-main": enabled_device("oc-main")},
            profiles={
                "corp": Profile(
                    "corp",
                    True,
                    Direction.OUTBOUND,
                    (ipaddress.IPv4Network("10.20.0.0/16"),),
                    ("oc-main",),
                )
            },
        )

        rules = compile_new_flow_intents(config)

        self.assertEqual(len(rules), 2)
        self.assertEqual(
            {
                rule.direction: rule.verdict
                for rule in rules
            },
            {
                FlowDirection.HOST_TO_DEVICE: Verdict.ACCEPT,
                FlowDirection.DEVICE_TO_HOST: Verdict.DROP,
            },
        )

    def test_device_to_host_specific_drop_precedes_broad_accept(self):
        config = ActiveConfig(
            devices={"oc-main": enabled_device("oc-main")},
            profiles={
                "restricted": Profile(
                    "restricted",
                    True,
                    Direction.OUTBOUND,
                    (ipaddress.IPv4Network("10.20.0.0/16"),),
                    ("oc-main",),
                ),
                "broad": Profile(
                    "broad",
                    True,
                    Direction.BIDIRECTIONAL,
                    (ipaddress.IPv4Network("10.0.0.0/8"),),
                    ("oc-main",),
                ),
            },
        )

        rules = [
            rule
            for rule in compile_new_flow_intents(config)
            if rule.direction is FlowDirection.DEVICE_TO_HOST
        ]

        self.assertEqual(
            [
                (str(rule.remote_prefix), rule.verdict)
                for rule in rules
            ],
            [
                ("10.20.0.0/16", Verdict.DROP),
                ("10.0.0.0/8", Verdict.ACCEPT),
            ],
        )

    def test_host_to_device_specific_drop_precedes_broad_accept(self):
        config = ActiveConfig(
            devices={"oc-main": enabled_device("oc-main")},
            profiles={
                "restricted": Profile(
                    "restricted",
                    True,
                    Direction.INBOUND,
                    (ipaddress.IPv4Network("10.20.0.0/16"),),
                    ("oc-main",),
                ),
                "broad": Profile(
                    "broad",
                    True,
                    Direction.BIDIRECTIONAL,
                    (ipaddress.IPv4Network("10.0.0.0/8"),),
                    ("oc-main",),
                ),
            },
        )

        rules = [
            rule
            for rule in compile_new_flow_intents(config)
            if rule.direction is FlowDirection.HOST_TO_DEVICE
        ]

        self.assertEqual(
            [
                (str(rule.remote_prefix), rule.verdict)
                for rule in rules
            ],
            [
                ("10.20.0.0/16", Verdict.DROP),
                ("10.0.0.0/8", Verdict.ACCEPT),
            ],
        )

    def test_bidirectional_is_accept_on_both_sides(self):
        config = ActiveConfig(
            devices={"oc-main": enabled_device("oc-main")},
            profiles={
                "support": Profile(
                    "support",
                    True,
                    Direction.BIDIRECTIONAL,
                    (ipaddress.IPv4Network("192.168.50.0/24"),),
                    ("oc-main",),
                )
            },
        )

        self.assertTrue(
            all(
                rule.verdict is Verdict.ACCEPT
                for rule in compile_new_flow_intents(config)
            )
        )

    def test_disabled_device_has_no_materialized_new_rules(self):
        config = ActiveConfig(
            devices={"oc-main": Device(name="oc-main", enabled=False)},
            profiles={
                "corp": Profile(
                    "corp",
                    True,
                    Direction.OUTBOUND,
                    (ipaddress.IPv4Network("10.0.0.0/8"),),
                    ("oc-main",),
                )
            },
        )

        self.assertEqual(compile_new_flow_intents(config), ())


if __name__ == "__main__":
    unittest.main()
