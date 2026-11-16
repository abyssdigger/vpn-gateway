from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
import json
import unittest

from rou.binding import LogicalPathId
from rou.interface_identity import InterfaceIdentity
from rou.iproute_priority_backend import (
    IproutePriorityBackend,
    IproutePriorityBackendError,
)
from rou.route_priority import RoutePriorityMove
from rou.route_priority_convergence import RoutePriorityDeleteDuplicate
from rou.route_priority_inventory import RoutePriorityPathRoute


A = LogicalPathId("oc", 0, 0)
B = LogicalPathId("wg", 0, 0)
EP_A = InterfaceIdentity("tun0", 10)
EP_B = InterfaceIdentity("wg0", 20)
DEST = IPv4Network("10.0.0.0/8")


def link_json(a=EP_A, b=EP_B):
    return json.dumps(
        [
            {"ifname": a.ifname, "ifindex": a.ifindex},
            {"ifname": b.ifname, "ifindex": b.ifindex},
        ]
    )


def route_row(path, metric):
    if path == A:
        return {
            "dst": "10.0.0.0/8",
            "dev": "tun0",
            "gateway": "172.20.0.1",
            "metric": metric,
            "flags": ["onlink"],
        }
    return {
        "dst": "10.0.0.0/8",
        "dev": "wg0",
        "metric": metric,
    }


def routes_json(a_metrics, b_metrics):
    rows = [
        route_row(A, metric)
        for metric in a_metrics
    ]
    rows.extend(route_row(B, metric) for metric in b_metrics)
    return json.dumps(rows)


class ScriptedRunner:
    def __init__(self, route_payloads, link_payloads=None):
        self.route_payloads = list(route_payloads)
        self.link_payloads = list(link_payloads or [])
        self.commands = []

    def run(self, argv):
        command = tuple(argv)
        self.commands.append(command)

        if command[-2:] == ("link", "show"):
            if self.link_payloads:
                return self.link_payloads.pop(0)
            return link_json()

        if "route" in command and "show" in command:
            if not self.route_payloads:
                raise AssertionError("unexpected route observation")
            return self.route_payloads.pop(0)

        return ""


def backend(runner):
    return IproutePriorityBackend(
        runner=runner,
        namespace="vpng-test",
        table=100,
        owner_protocol=202,
        destination=DEST,
        path_routes=(
            RoutePriorityPathRoute(
                path_id=A,
                endpoint=EP_A,
                gateway=IPv4Address("172.20.0.1"),
                onlink=True,
            ),
            RoutePriorityPathRoute(
                path_id=B,
                endpoint=EP_B,
            ),
        ),
    )


class IproutePriorityBackendTests(unittest.TestCase):
    def test_observation_uses_link_sandwich_and_filtered_route_context(self):
        runner = ScriptedRunner([routes_json((10,), (20,))])
        snapshot = backend(runner).observe_route_priority()

        self.assertEqual(snapshot.routes[A], frozenset((10,)))
        self.assertEqual(snapshot.routes[B], frozenset((20,)))
        self.assertEqual(
            runner.commands,
            [
                ("ip", "-n", "vpng-test", "-j", "link", "show"),
                (
                    "ip", "-n", "vpng-test", "-j", "-N", "-4",
                    "route", "show", "table", "100", "proto", "202",
                ),
                ("ip", "-n", "vpng-test", "-j", "link", "show"),
            ],
        )

    def test_same_name_ifindex_change_during_observation_is_rejected(self):
        changed = InterfaceIdentity("tun0", 11)
        runner = ScriptedRunner(
            [routes_json((10,), (20,))],
            [link_json(), link_json(a=changed)],
        )
        with self.assertRaisesRegex(
            IproutePriorityBackendError,
            "changed during route observation",
        ):
            backend(runner).observe_route_priority()

    def test_semantic_move_is_add_verify_delete_verify(self):
        runner = ScriptedRunner(
            [
                routes_json((10,), (20,)),
                routes_json((10, 30), (20,)),
                routes_json((30,), (20,)),
            ]
        )
        backend(runner).move_route_priority(RoutePriorityMove(A, 10, 30))

        add = (
            "ip", "-n", "vpng-test", "-4", "route", "add", "unicast",
            "10.0.0.0/8", "table", "100", "proto", "202", "metric", "30",
            "via", "172.20.0.1", "dev", "tun0", "onlink",
        )
        delete = (
            "ip", "-n", "vpng-test", "-4", "route", "del", "unicast",
            "10.0.0.0/8", "table", "100", "proto", "202", "metric", "10",
            "via", "172.20.0.1", "dev", "tun0", "onlink",
        )
        self.assertIn(add, runner.commands)
        self.assertIn(delete, runner.commands)
        self.assertLess(runner.commands.index(add), runner.commands.index(delete))

    def test_unverified_add_never_reaches_delete_old(self):
        runner = ScriptedRunner(
            [
                routes_json((10,), (20,)),
                routes_json((10,), (20,)),
            ]
        )
        with self.assertRaisesRegex(
            IproutePriorityBackendError,
            "not authoritatively verified before delete",
        ):
            backend(runner).move_route_priority(RoutePriorityMove(A, 10, 30))

        deletes = [
            command
            for command in runner.commands
            if "route" in command and "del" in command
        ]
        self.assertEqual(deletes, [])

    def test_duplicate_delete_is_prechecked_and_verified(self):
        runner = ScriptedRunner(
            [
                routes_json((10, 30), (20,)),
                routes_json((30,), (20,)),
            ]
        )
        backend(runner).delete_duplicate_route(
            RoutePriorityDeleteDuplicate(A, 10)
        )

        self.assertIn(
            (
                "ip", "-n", "vpng-test", "-4", "route", "del", "unicast",
                "10.0.0.0/8", "table", "100", "proto", "202", "metric", "10",
                "via", "172.20.0.1", "dev", "tun0", "onlink",
            ),
            runner.commands,
        )

    def test_duplicate_delete_refuses_last_route_copy(self):
        runner = ScriptedRunner([routes_json((10,), (20,))])
        with self.assertRaisesRegex(
            IproutePriorityBackendError,
            "not safe",
        ):
            backend(runner).delete_duplicate_route(
                RoutePriorityDeleteDuplicate(A, 10)
            )
        self.assertFalse(
            any("del" in command for command in runner.commands)
        )

    def test_move_refuses_when_another_eligible_path_is_missing(self):
        runner = ScriptedRunner([routes_json((10,), ())])
        with self.assertRaisesRegex(
            IproutePriorityBackendError,
            "missing eligible paths",
        ):
            backend(runner).move_route_priority(RoutePriorityMove(A, 10, 30))

    def test_direct_path_command_has_no_gateway_or_onlink(self):
        runner = ScriptedRunner(
            [
                routes_json((10,), (20,)),
                routes_json((10,), (20, 30)),
                routes_json((10,), (30,)),
            ]
        )
        backend(runner).move_route_priority(RoutePriorityMove(B, 20, 30))

        add_commands = [
            command
            for command in runner.commands
            if "route" in command and "add" in command
        ]
        self.assertEqual(len(add_commands), 1)
        self.assertNotIn("via", add_commands[0])
        self.assertNotIn("onlink", add_commands[0])
        self.assertEqual(add_commands[0][-2:], ("dev", "wg0"))


if __name__ == "__main__":
    unittest.main()
