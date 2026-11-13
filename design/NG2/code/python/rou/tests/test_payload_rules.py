from ipaddress import IPv4Network
import unittest

from rou.network_rules import (
    InterfaceIdentity,
    NetworkRulesError,
    TerminalAction,
)
from rou.payload_rules import (
    PayloadPath,
    PayloadProfileRequest,
    PayloadRulesCalculator,
    PayloadTrafficStateRequest,
)


class PayloadRulesCalculatorTests(unittest.TestCase):
    def _calculate(self, *profiles: PayloadProfileRequest):
        return PayloadRulesCalculator().calculate(
            PayloadTrafficStateRequest(profiles)
        )

    def test_preserves_ordered_paths(self):
        profile = PayloadProfileRequest(
            "profile-a",
            (IPv4Network("10.0.0.0/8"),),
            (
                PayloadPath("pri", InterfaceIdentity("vpns00", 10)),
                PayloadPath("sec", InterfaceIdentity("vpns01", 11)),
            ),
        )

        spec = self._calculate(profile)

        self.assertEqual(
            [
                (item.ifname, item.ifindex)
                for item in spec.routing_domains[0].ordered_paths
            ],
            [("vpns00", 10), ("vpns01", 11)],
        )

    def test_zero_path_keeps_terminal_blackhole(self):
        profile = PayloadProfileRequest(
            "profile-a",
            (IPv4Network("10.0.0.0/8"),),
            (),
        )

        spec = self._calculate(profile)

        self.assertEqual(spec.routing_domains[0].ordered_paths, ())
        self.assertIs(
            spec.routing_domains[0].terminal_action,
            TerminalAction.BLACKHOLE,
        )

    def test_dispatch_is_longest_prefix_first(self):
        broad = PayloadProfileRequest(
            "broad",
            (IPv4Network("10.0.0.0/8"),),
            (),
        )
        narrow = PayloadProfileRequest(
            "narrow",
            (IPv4Network("10.1.0.0/16"),),
            (),
        )

        spec = self._calculate(broad, narrow)

        self.assertEqual(
            [str(item.destination) for item in spec.dispatch_rules],
            ["10.1.0.0/16", "10.0.0.0/8"],
        )

    def test_same_destination_in_two_profiles_is_ambiguous(self):
        first = PayloadProfileRequest(
            "first",
            (IPv4Network("10.0.0.0/8"),),
            (),
        )
        second = PayloadProfileRequest(
            "second",
            (IPv4Network("10.0.0.0/8"),),
            (),
        )

        with self.assertRaises(NetworkRulesError):
            self._calculate(first, second)

    def test_same_name_new_ifindex_remains_distinct(self):
        profile = PayloadProfileRequest(
            "profile-a",
            (IPv4Network("10.0.0.0/8"),),
            (
                PayloadPath("pri", InterfaceIdentity("vpns00", 10)),
                PayloadPath("sec", InterfaceIdentity("vpns00", 11)),
            ),
        )

        spec = self._calculate(profile)

        self.assertEqual(
            [item.ifindex for item in spec.routing_domains[0].ordered_paths],
            [10, 11],
        )


if __name__ == "__main__":
    unittest.main()
