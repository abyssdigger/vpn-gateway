from __future__ import annotations

from ipaddress import IPv4Address
import json
import unittest

from rou.host_local_ipv4 import (
    HostLocalIPv4ObservationError,
    observe_host_local_ipv4_addresses,
)


class Runner:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def run(self, argv):
        self.calls.append(tuple(argv))
        return self.value


class HostLocalIPv4Tests(unittest.TestCase):
    def test_observation_is_fresh_sorted_and_deduplicated(self):
        runner = Runner(json.dumps([
            {
                "ifname": "eth0",
                "addr_info": [
                    {"family": "inet", "local": "192.0.2.10", "prefixlen": 24},
                ],
            },
            {
                "ifname": "lo",
                "addr_info": [
                    {"family": "inet", "local": "127.0.0.1", "prefixlen": 8},
                    {"family": "inet", "local": "192.0.2.10", "prefixlen": 32},
                ],
            },
        ]))
        self.assertEqual(
            observe_host_local_ipv4_addresses(runner),
            (
                IPv4Address("127.0.0.1"),
                IPv4Address("192.0.2.10"),
            ),
        )
        self.assertEqual(
            runner.calls,
            [("ip", "-j", "-4", "addr", "show")],
        )

    def test_unnumbered_interfaces_do_not_create_fake_addresses(self):
        runner = Runner(json.dumps([
            {"ifname": "vpng0", "addr_info": []},
            {
                "ifname": "lo",
                "addr_info": [
                    {"family": "inet", "local": "127.0.0.1", "prefixlen": 8},
                ],
            },
        ]))
        self.assertEqual(
            observe_host_local_ipv4_addresses(runner),
            (IPv4Address("127.0.0.1"),),
        )

    def test_invalid_snapshot_is_not_treated_as_empty(self):
        for value in ("{}", "not-json", '[{"ifname":"eth0","addr_info":{}}]'):
            with self.subTest(value=value):
                with self.assertRaises(HostLocalIPv4ObservationError):
                    observe_host_local_ipv4_addresses(Runner(value))


if __name__ == "__main__":
    unittest.main()
