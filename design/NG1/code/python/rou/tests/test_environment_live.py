import ipaddress
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.environment import (
    EnvironmentCollectError,
    EnvironmentParseError,
    collect_environment_snapshot,
    parse_ip_addr_json,
    parse_ip_route_json,
    parse_ip_rule_json,
)
from rou.device_engine import EnvironmentInterface, InterfaceIdentity


class EnvironmentLiveTests(unittest.TestCase):
    def test_parse_addr_binds_to_ifindex_identity(self):
        interfaces = (
            EnvironmentInterface(InterfaceIdentity("host0", 7)),
            EnvironmentInterface(InterfaceIdentity("vpns00", 9)),
        )
        out = parse_ip_addr_json(
            """[
              {"ifindex":7,"ifname":"host0","addr_info":[
                {"family":"inet","local":"192.0.2.2","prefixlen":30},
                {"family":"inet6","local":"fe80::1","prefixlen":64}
              ]},
              {"ifindex":9,"ifname":"vpns00","addr_info":[
                {"family":"inet","local":"172.20.130.1","prefixlen":32}
              ]}
            ]""",
            interfaces,
        )
        self.assertEqual(
            [
                (item.identity.ifname, str(item.address), item.prefixlen)
                for item in out
            ],
            [
                ("host0", "192.0.2.2", 30),
                ("vpns00", "172.20.130.1", 32),
            ],
        )

    def test_parse_route_handles_direct_multipath_and_blackhole(self):
        routes = parse_ip_route_json(
            """[
              {
                "dst":"172.21.201.19/32",
                "table":313,
                "protocol":202,
                "metric":65535,
                "multipath":[
                  {"dev":"vpns00","weight":1},
                  {"dev":"vpns01","weight":1}
                ]
              },
              {
                "type":"blackhole",
                "dst":"default",
                "table":313,
                "protocol":201,
                "metric":65536
              }
            ]"""
        )
        self.assertEqual(routes[0].table, 313)
        self.assertEqual(str(routes[0].destination), "172.21.201.19/32")
        self.assertEqual(
            [(n.ifname, n.weight) for n in routes[0].nexthops],
            [("vpns00", 1), ("vpns01", 1)],
        )
        self.assertEqual(routes[1].route_type, "blackhole")
        self.assertEqual(str(routes[1].destination), "0.0.0.0/0")

    def test_parse_rule_handles_local_and_profile_dispatch(self):
        rules = parse_ip_rule_json(
            """[
              {"priority":0,"src":"all","table":"local"},
              {"priority":10,"src":"all","dst":"10.20.0.0/16","iif":"host0","table":11},
              {"priority":32766,"src":"all","table":"main"}
            ]"""
        )
        self.assertEqual(rules[0].table, 255)
        self.assertEqual(rules[1].priority, 10)
        self.assertEqual(str(rules[1].destination), "10.20.0.0/16")
        self.assertEqual(rules[1].iif, "host0")
        self.assertEqual(rules[2].table, 254)

    def test_addr_rejects_unknown_interface(self):
        with self.assertRaisesRegex(EnvironmentParseError, "unobserved interface"):
            parse_ip_addr_json(
                '[{"ifname":"ghost0","addr_info":[]}]',
                (EnvironmentInterface(InterfaceIdentity("host0", 7)),),
            )

    def test_collect_snapshot_uses_single_namespace_and_no_partial_result(self):
        responses = {
            ("ip", "netns", "exec", "rou0", "ip", "-j", "link", "show"):
                '[{"ifindex":1,"ifname":"lo"},{"ifindex":7,"ifname":"host0"}]',
            ("ip", "netns", "exec", "rou0", "ip", "-j", "-4", "addr", "show"):
                '[{"ifindex":1,"ifname":"lo","addr_info":[{"family":"inet","local":"127.0.0.1","prefixlen":8}]},{"ifindex":7,"ifname":"host0","addr_info":[{"family":"inet","local":"192.0.2.2","prefixlen":30}]}]',
            ("ip", "netns", "exec", "rou0", "ip", "-j", "-4", "route", "show", "table", "all"):
                '[{"dst":"default","table":"main","dev":"host0","protocol":"static"}]',
            ("ip", "netns", "exec", "rou0", "ip", "-j", "-4", "rule", "show"):
                '[{"priority":0,"table":"local"},{"priority":32766,"table":"main"},{"priority":32767,"table":"default"}]',
            ("ip", "netns", "exec", "rou0", "sysctl", "-n", "net.ipv4.ip_forward"): "1\n",
            ("ip", "netns", "exec", "rou0", "sysctl", "-n", "net.ipv6.conf.all.forwarding"): "0\n",
        }
        seen = []

        def run(command):
            seen.append(command)
            return responses[command]

        snap = collect_environment_snapshot("rou0", run)
        self.assertEqual([x.identity.ifname for x in snap.interfaces], ["lo", "host0"])
        self.assertEqual(snap.sysctl_map["net.ipv4.ip_forward"], "1")
        self.assertEqual(len(seen), 6)

    def test_collect_wraps_runner_failure(self):
        def run(_command):
            raise OSError("boom")

        with self.assertRaisesRegex(EnvironmentCollectError, "boom"):
            collect_environment_snapshot("rou0", run)


if __name__ == "__main__":
    unittest.main()
