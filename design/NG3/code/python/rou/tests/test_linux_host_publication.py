from __future__ import annotations

from ipaddress import IPv4Address
import json
import unittest

from rou.host_publication_policy import (
    HostPublicationDesiredState,
    HostPublicationRuleSpec,
    HostPublicationSelectorKind,
)
from rou.linux_host_publication import (
    HOST_PUBLICATION_CHAIN,
    HOST_PUBLICATION_CHAIN_COMMENT,
    HOST_PUBLICATION_RULE_COMMENT,
    HOST_PUBLICATION_TABLE,
    HOST_PUBLICATION_TABLE_COMMENT,
    HostPublicationConvergenceStatus,
    LinuxHostPublicationDriver,
    converge_host_publication_once,
)
from rou.local_publication_policy import PublicationProtocol


RULE = HostPublicationRuleSpec(
    protocol=PublicationProtocol.TCP,
    selector_kind=HostPublicationSelectorKind.INTERFACE,
    selector_value="eth0",
    host_port=443,
    internal_address=IPv4Address("192.0.2.2"),
    internal_port=8443,
)
DESIRED = HostPublicationDesiredState((RULE,))


def ruleset(rule=RULE):
    expr = [
        {
            "match": {
                "op": "==",
                "left": {"fib": {"result": "type", "flags": ["daddr"]}},
                "right": "local",
            }
        },
        {
            "match": {
                "op": "==",
                "left": {"meta": {"key": "iifname"}},
                "right": str(rule.selector_value),
            }
        },
        {
            "match": {
                "op": "==",
                "left": {
                    "payload": {
                        "protocol": rule.protocol.value,
                        "field": "dport",
                    }
                },
                "right": rule.host_port,
            }
        },
        {
            "dnat": {
                "addr": str(rule.internal_address),
                "port": rule.internal_port,
            }
        },
    ]
    return json.dumps(
        {
            "nftables": [
                {"metainfo": {"json_schema_version": 1}},
                {
                    "table": {
                        "family": "ip",
                        "name": HOST_PUBLICATION_TABLE,
                        "handle": 1,
                        "comment": HOST_PUBLICATION_TABLE_COMMENT,
                    }
                },
                {
                    "chain": {
                        "family": "ip",
                        "table": HOST_PUBLICATION_TABLE,
                        "name": HOST_PUBLICATION_CHAIN,
                        "handle": 2,
                        "type": "nat",
                        "hook": "prerouting",
                        "prio": -100,
                        "policy": "accept",
                        "comment": HOST_PUBLICATION_CHAIN_COMMENT,
                    }
                },
                {
                    "rule": {
                        "family": "ip",
                        "table": HOST_PUBLICATION_TABLE,
                        "chain": HOST_PUBLICATION_CHAIN,
                        "handle": 3,
                        "comment": HOST_PUBLICATION_RULE_COMMENT,
                        "expr": expr,
                    }
                },
            ]
        }
    )


class FakeRunner:
    def __init__(
        self,
        *,
        forwarding="1",
        nft=None,
        links=None,
        addresses=None,
    ):
        self.forwarding = forwarding
        self.nft = nft or json.dumps({"nftables": [{"metainfo": {}}]})
        self.links = links or [{"ifname": "eth0", "flags": ["UP", "LOWER_UP"]}]
        self.addresses = addresses or [
            {
                "ifname": "eth0",
                "addr_info": [
                    {"family": "inet", "local": "198.51.100.10", "prefixlen": 24}
                ],
            }
        ]
        self.scripts = []

    def run(self, argv):
        if tuple(argv[-3:]) == ("sysctl", "-n", "net.ipv4.ip_forward"):
            return self.forwarding + "\n"
        if "nft" in argv and "list" in argv and "ruleset" in argv:
            return self.nft
        if "ip" in argv and "link" in argv and "show" in argv:
            return json.dumps(self.links)
        if "ip" in argv and "addr" in argv and "show" in argv:
            return json.dumps(self.addresses)
        raise AssertionError(argv)

    def run_script(self, argv, script):
        self.scripts.append((tuple(argv), script))
        if "delete table" in script and "add table" not in script:
            self.nft = json.dumps({"nftables": [{"metainfo": {}}]})
        else:
            self.nft = ruleset()


class LinuxHostPublicationTests(unittest.TestCase):
    def test_exact_observation_is_confirmed(self):
        backend = LinuxHostPublicationDriver(FakeRunner(nft=ruleset()))
        result = converge_host_publication_once(backend, DESIRED)
        self.assertEqual(result.status, HostPublicationConvergenceStatus.CONFIRMED)
        self.assertFalse(result.mutation_attempted)

    def test_disabled_forwarding_is_unready_and_never_mutates_positive_state(self):
        runner = FakeRunner(forwarding="0")
        backend = LinuxHostPublicationDriver(runner)
        result = converge_host_publication_once(backend, DESIRED)
        self.assertEqual(result.status, HostPublicationConvergenceStatus.UNREADY)
        self.assertEqual(runner.scripts, [])

    def test_absent_owner_is_created_and_freshly_verified(self):
        runner = FakeRunner()
        backend = LinuxHostPublicationDriver(runner)
        result = converge_host_publication_once(backend, DESIRED)
        self.assertEqual(result.status, HostPublicationConvergenceStatus.APPLIED)
        self.assertTrue(result.confirmed)
        self.assertEqual(len(runner.scripts), 1)
        self.assertIn("fib daddr type local", runner.scripts[0][1])
        self.assertIn('iifname "eth0"', runner.scripts[0][1])

    def test_cleanup_does_not_require_forwarding(self):
        runner = FakeRunner(forwarding="0", nft=ruleset())
        backend = LinuxHostPublicationDriver(runner)
        result = converge_host_publication_once(
            backend,
            HostPublicationDesiredState(()),
        )
        self.assertEqual(result.status, HostPublicationConvergenceStatus.APPLIED)
        self.assertTrue(result.confirmed)
        self.assertIn("delete table", runner.scripts[0][1])


    def test_missing_interface_selector_is_unready(self):
        runner = FakeRunner(links=[{"ifname": "eth1", "flags": ["UP"]}])
        result = converge_host_publication_once(
            LinuxHostPublicationDriver(runner),
            DESIRED,
        )
        self.assertEqual(result.status, HostPublicationConvergenceStatus.UNREADY)
        self.assertIn("interface 'eth0' is absent", result.diagnostic)
        self.assertEqual(runner.scripts, [])

    def test_down_interface_selector_is_unready(self):
        runner = FakeRunner(links=[{"ifname": "eth0", "flags": ["BROADCAST"]}])
        result = converge_host_publication_once(
            LinuxHostPublicationDriver(runner),
            DESIRED,
        )
        self.assertEqual(result.status, HostPublicationConvergenceStatus.UNREADY)
        self.assertIn("interface 'eth0' is not UP", result.diagnostic)

    def test_missing_exact_ipv4_selector_is_unready(self):
        ipv4_rule = HostPublicationRuleSpec(
            protocol=PublicationProtocol.TCP,
            selector_kind=HostPublicationSelectorKind.IPV4,
            selector_value=IPv4Address("198.51.100.99"),
            host_port=443,
            internal_address=IPv4Address("192.0.2.2"),
            internal_port=8443,
        )
        result = converge_host_publication_once(
            LinuxHostPublicationDriver(FakeRunner()),
            HostPublicationDesiredState((ipv4_rule,)),
        )
        self.assertEqual(result.status, HostPublicationConvergenceStatus.UNREADY)
        self.assertIn("198.51.100.99 is not assigned locally", result.diagnostic)

    def test_foreign_rule_in_owned_table_is_conflict(self):
        root = json.loads(ruleset())
        root["nftables"].append(
            {
                "rule": {
                    "family": "ip",
                    "table": HOST_PUBLICATION_TABLE,
                    "chain": HOST_PUBLICATION_CHAIN,
                    "handle": 4,
                    "comment": "foreign",
                    "expr": [],
                }
            }
        )
        runner = FakeRunner(nft=json.dumps(root))
        result = converge_host_publication_once(
            LinuxHostPublicationDriver(runner),
            DESIRED,
        )
        self.assertEqual(result.status, HostPublicationConvergenceStatus.CONFLICT)
        self.assertEqual(runner.scripts, [])


if __name__ == "__main__":
    unittest.main()
