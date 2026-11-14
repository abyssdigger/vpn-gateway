import json
from ipaddress import IPv4Network
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.linux_driver import (
    CommandResult,
    LinuxNetworkDriver,
)
from rou.linux_network import compile_linux_network_desired
from rou.linux_routing import LinuxRoutingAllocationState
from rou.network_rules import (
    DispatchRuleSpec,
    FlowInitiationAllowSpec,
    NetworkEndpoint,
    NetworkRulesSpec,
    RoutingDomainSpec,
    TerminalDisposition,
    TrafficAllowSpec,
    TrafficPredicate,
)
from rou.network_rules_composition import (
    OwnedNetworkRules,
    OwnerToken,
    compose_network_rules,
)


class StatefulFakeRunner:
    def __init__(self, desired):
        self.desired = desired
        self.forwarding = False
        self.materialized = False
        self.commands = []
        self.nft_filter = False
        self.nft_nat = False

    def run(self, argv, *, input_text=None, check=True):
        self.commands.append((argv, input_text, check))

        if argv[:3] == ("sysctl", "-q", "-w"):
            self.forwarding = argv[3].endswith("=1")
            return CommandResult(0, "", "")

        if argv == ("sysctl", "-n", "net.ipv4.ip_forward"):
            return CommandResult(
                0,
                "1\n" if self.forwarding else "0\n",
                "",
            )

        if argv == ("ip", "-j", "link", "show"):
            return CommandResult(
                0,
                json.dumps(
                    [
                        {"ifname": "host0", "ifindex": 2},
                        {"ifname": "vpns00", "ifindex": 10},
                    ]
                ),
                "",
            )

        if argv == (
            "ip", "-j", "-4", "route", "show", "table", "all"
        ):
            return CommandResult(
                0,
                json.dumps(
                    self._routes_json()
                    if self.materialized
                    else []
                ),
                "",
            )

        if argv == ("ip", "-j", "-4", "rule", "show"):
            base = [
                {"priority": 0, "table": "local"},
                {"priority": 32766, "table": "main"},
                {"priority": 32767, "table": "default"},
            ]
            if self.materialized:
                base[1:1] = self._rules_json()
            return CommandResult(0, json.dumps(base), "")

        if argv[:4] == ("ip", "route", "flush", "table"):
            return CommandResult(
                2,
                "",
                "Error: ipv4: FIB table does not exist.\n",
            )

        if argv[:3] == ("ip", "route", "add"):
            self.materialized = True
            return CommandResult(0, "", "")

        if argv[:3] == ("ip", "rule", "add"):
            self.materialized = True
            return CommandResult(0, "", "")

        if argv[:4] == ("ip", "rule", "del", "priority"):
            return CommandResult(0, "", "")

        if argv[:6] == ("nft", "-j", "-n", "list", "table", "ip"):
            table = argv[6]
            present = (
                self.nft_filter
                if table == "vpng2_filter"
                else self.nft_nat
            )
            if not present:
                return CommandResult(
                    1,
                    "",
                    "No such file or directory",
                )
            desired = (
                self.desired.filter
                if table == "vpng2_filter"
                else self.desired.nat
            )
            comments = [
                marker.comment
                for marker in desired.markers
            ]
            return CommandResult(
                0,
                json.dumps(
                    {
                        "nftables": [
                            *[
                                {"rule": {"comment": comment}}
                                for comment in comments
                            ]
                        ]
                    }
                ),
                "",
            )

        if argv[:5] == ("nft", "-n", "list", "table", "ip"):
            table = argv[5]
            desired = (
                self.desired.filter
                if table == "vpng2_filter"
                else self.desired.nat
            )
            return CommandResult(0, desired.definition, "")

        if argv == ("nft", "-f", "-"):
            if "vpng2_filter" in input_text:
                self.nft_filter = True
            if "vpng2_nat" in input_text:
                self.nft_nat = True
            return CommandResult(0, "", "")

        if argv[:4] == ("nft", "delete", "table", "ip"):
            if argv[4] == "vpng2_filter":
                self.nft_filter = False
            if argv[4] == "vpng2_nat":
                self.nft_nat = False
            return CommandResult(0, "", "")

        raise AssertionError(f"unexpected command: {argv!r}")

    def _routes_json(self):
        out = []
        for route in self.desired.routing.routes:
            item = {
                "table": route.table_id,
                "dst": (
                    "default"
                    if route.destination.prefixlen == 0
                    else route.destination.with_prefixlen
                ),
                "type": route.kind.value,
                "protocol": route.protocol,
                "metric": route.metric,
            }
            if route.path is not None:
                item["dev"] = route.path.ifname
            out.append(item)
        return out

    def _rules_json(self):
        return [
            {
                "priority": rule.priority,
                "iif": rule.source_ifname,
                "dst": str(rule.destination.network_address),
                "dstlen": rule.destination.prefixlen,
                "table": rule.table_id,
            }
            for rule in self.desired.routing.dispatch_rules
        ]


def _desired():
    path_identity = InterfaceIdentity("vpns00", 10)
    path = NetworkEndpoint.interface_path(path_identity)
    local = NetworkEndpoint.local_network()
    network = IPv4Network("10.0.0.0/8")
    rules = NetworkRulesSpec(
        routing_domains=(
            RoutingDomainSpec(
                "corp",
                (network,),
                (path_identity,),
                TerminalDisposition.DROP,
            ),
        ),
        dispatch_rules=(
            DispatchRuleSpec(
                network,
                "corp",
                source=local,
            ),
        ),
        traffic_allows=(
            TrafficAllowSpec(
                local,
                path,
                TrafficPredicate.always(),
            ),
            TrafficAllowSpec(
                path,
                local,
                TrafficPredicate.always(),
            ),
        ),
        flow_initiation_allows=(
            FlowInitiationAllowSpec(
                local,
                path,
                TrafficPredicate.always(),
            ),
        ),
    )
    return compile_linux_network_desired(
        compose_network_rules(
            (OwnedNetworkRules(OwnerToken(1), rules),)
        ),
        LinuxRoutingAllocationState(),
        local_interface="host0",
    )


class LinuxNetworkDriverTests(unittest.TestCase):
    def test_structural_apply_closes_barrier_and_freshly_verifies(self):
        desired = _desired()
        runner = StatefulFakeRunner(desired)
        driver = LinuxNetworkDriver(runner)

        result = driver.materialize_structural(desired)

        self.assertTrue(result.success, result.diagnostic)
        self.assertTrue(runner.forwarding)
        sysctl_writes = [
            argv
            for argv, _input, _check in runner.commands
            if argv[:3] == ("sysctl", "-q", "-w")
        ]
        self.assertEqual(
            sysctl_writes[0][-1],
            "net.ipv4.ip_forward=0",
        )
        self.assertEqual(
            sysctl_writes[-1][-1],
            "net.ipv4.ip_forward=1",
        )
        link_reads = [
            argv
            for argv, _input, _check in runner.commands
            if argv == ("ip", "-j", "link", "show")
        ]
        self.assertGreaterEqual(len(link_reads), 6)

    def test_failure_best_effort_closes_forwarding(self):
        desired = _desired()

        class FailingRunner(StatefulFakeRunner):
            def run(self, argv, *, input_text=None, check=True):
                if argv[:3] == ("ip", "route", "add"):
                    raise RuntimeError("injected route failure")
                return super().run(
                    argv,
                    input_text=input_text,
                    check=check,
                )

        runner = FailingRunner(desired)
        runner.forwarding = True
        driver = LinuxNetworkDriver(runner)

        result = driver.materialize_structural(desired)

        self.assertFalse(result.success)
        self.assertFalse(runner.forwarding)
        self.assertIn("injected route failure", result.diagnostic)

    def test_empty_desired_deletes_owned_nft_tables_and_leaves_forwarding_off(self):
        desired = compile_linux_network_desired(
            compose_network_rules(()),
            LinuxRoutingAllocationState(),
            local_interface="host0",
        )
        runner = StatefulFakeRunner(desired)
        runner.nft_filter = True
        runner.nft_nat = True
        driver = LinuxNetworkDriver(runner)

        result = driver.materialize_structural(desired)

        self.assertTrue(result.success, result.diagnostic)
        self.assertFalse(runner.forwarding)
        self.assertFalse(runner.nft_filter)
        self.assertFalse(runner.nft_nat)


if __name__ == "__main__":
    unittest.main()
