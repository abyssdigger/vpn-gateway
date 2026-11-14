from ipaddress import IPv4Network
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.linux_local_process import LinuxLocalProcessConfig
from rou.linux_routing import (
    DomainTableAllocation,
    FIRST_PATH_METRIC,
    LinuxRouteKind,
    LinuxRouteSpec,
    LinuxRoutingAllocationState,
    LinuxRoutingError,
    PATH_METRIC_STEP,
    TERMINAL_METRIC,
    TERMINAL_ROUTE_PROTOCOL,
    UNICAST_ROUTE_PROTOCOL,
    compile_linux_routing_desired,
    plan_linux_route_priority_moves,
)
from rou.network_rules import (
    DispatchRuleSpec,
    NetworkEndpoint,
    NetworkRulesSpec,
    RoutingDomainSpec,
    TerminalDisposition,
    TrafficProtocol,
)
from rou.network_rules_composition import (
    OwnedNetworkRules,
    OwnerToken,
    OwnedRoutingDomainRef,
    compose_network_rules,
)


def _owner_rules(
    token: int,
    name: str,
    destination: str,
    paths=(),
    *,
    source=None,
    priority_prefix_length=None,
) -> OwnedNetworkRules:
    network = IPv4Network(destination)
    if source is None:
        source = NetworkEndpoint.local_network()
    return OwnedNetworkRules(
        OwnerToken(token),
        NetworkRulesSpec(
            routing_domains=(
                RoutingDomainSpec(
                    name=name,
                    destinations=(network,),
                    ordered_paths=tuple(paths),
                    terminal_disposition=TerminalDisposition.DROP,
                    priority_prefix_length=priority_prefix_length,
                ),
            ),
            dispatch_rules=(
                DispatchRuleSpec(
                    destination=network,
                    routing_domain=name,
                    source=source,
                ),
            ),
        ),
    )


class LinuxRoutingAllocationTests(unittest.TestCase):
    def test_owner_scoped_same_name_gets_distinct_tables(self):
        composed = compose_network_rules(
            (
                _owner_rules(1, "default", "10.0.0.0/8"),
                _owner_rules(2, "default", "192.168.0.0/16"),
            )
        )

        desired = compile_linux_routing_desired(
            composed,
            LinuxRoutingAllocationState(),
            local_interface="host0",
        )

        tables = desired.allocation.table_by_domain
        self.assertNotEqual(
            tables[OwnedRoutingDomainRef(OwnerToken(1), "default")],
            tables[OwnedRoutingDomainRef(OwnerToken(2), "default")],
        )

    def test_surviving_domain_keeps_table_when_other_owner_removed(self):
        first = _owner_rules(1, "a", "10.0.0.0/8")
        second = _owner_rules(2, "b", "192.168.0.0/16")
        initial = compile_linux_routing_desired(
            compose_network_rules((first, second)),
            LinuxRoutingAllocationState(),
            local_interface="host0",
        )
        committed = initial.allocation

        after = compile_linux_routing_desired(
            compose_network_rules((second,)),
            committed,
            local_interface="host0",
        )

        domain = OwnedRoutingDomainRef(OwnerToken(2), "b")
        self.assertEqual(
            after.allocation.table_by_domain[domain],
            committed.table_by_domain[domain],
        )

    def test_removed_table_id_is_not_reused_before_verified_commit(self):
        first = _owner_rules(1, "a", "10.0.0.0/8")
        second = _owner_rules(2, "b", "192.168.0.0/16")
        initial = compile_linux_routing_desired(
            compose_network_rules((first, second)),
            LinuxRoutingAllocationState(),
            local_interface="host0",
        )
        committed = initial.allocation
        removed_table = committed.table_by_domain[
            OwnedRoutingDomainRef(OwnerToken(1), "a")
        ]

        third = _owner_rules(3, "c", "172.16.0.0/12")
        projected = compile_linux_routing_desired(
            compose_network_rules((second, third)),
            committed,
            local_interface="host0",
        )

        self.assertNotEqual(
            projected.allocation.table_by_domain[
                OwnedRoutingDomainRef(OwnerToken(3), "c")
            ],
            removed_table,
        )

        # After verified commit of the removal, the old table ID becomes free.
        committed_after = projected.allocation
        fourth = _owner_rules(4, "d", "100.64.0.0/10")
        next_projection = compile_linux_routing_desired(
            compose_network_rules((second, third, fourth)),
            committed_after,
            local_interface="host0",
        )
        self.assertEqual(
            next_projection.allocation.table_by_domain[
                OwnedRoutingDomainRef(OwnerToken(4), "d")
            ],
            removed_table,
        )

    def test_path_metrics_follow_semantic_order_and_stay_below_terminal(self):
        a = InterfaceIdentity("vpns00", 10)
        b = InterfaceIdentity("vpns01", 11)
        composed = compose_network_rules(
            (_owner_rules(1, "a", "10.0.0.0/8", (a, b)),)
        )

        desired = compile_linux_routing_desired(
            composed,
            LinuxRoutingAllocationState(),
            local_interface="host0",
        )

        normal = [
            item
            for item in desired.routes
            if item.kind is LinuxRouteKind.UNICAST
        ]
        self.assertEqual(
            [item.metric for item in normal],
            [FIRST_PATH_METRIC, FIRST_PATH_METRIC + PATH_METRIC_STEP],
        )
        self.assertTrue(all(item.metric < TERMINAL_METRIC for item in normal))

    def test_priority_prefix_projects_one_persistent_empty_slot(self):
        paths = tuple(
            InterfaceIdentity(f"vpns0{index}", 10 + index)
            for index in range(4)
        )
        desired = compile_linux_routing_desired(
            compose_network_rules(
                (
                    _owner_rules(
                        1,
                        "a",
                        "10.0.0.0/8",
                        paths,
                        priority_prefix_length=2,
                    ),
                )
            ),
            LinuxRoutingAllocationState(),
            local_interface="host0",
        )

        normal = [
            item
            for item in desired.routes
            if item.kind is LinuxRouteKind.UNICAST
        ]
        self.assertEqual(
            [(item.metric, item.path) for item in normal],
            [
                (10, paths[0]),
                (20, paths[1]),
                (40, paths[2]),
                (50, paths[3]),
            ],
        )
        self.assertEqual(len(desired.route_slot_gaps), 1)
        self.assertEqual(desired.route_slot_gaps[0].metric, 30)

    def test_empty_slot_planner_recovers_path_from_dead_tail(self):
        a, b, v, g, d, e, j = tuple(
            InterfaceIdentity(name, 10 + index)
            for index, name in enumerate(
                ("patha", "pathb", "pathv", "pathg", "pathd", "pathe", "pathj")
            )
        )

        current = compile_linux_routing_desired(
            compose_network_rules(
                (
                    _owner_rules(
                        1,
                        "a",
                        "10.0.0.0/8",
                        (a, b, g, d, v, e, j),
                        priority_prefix_length=4,
                    ),
                )
            ),
            LinuxRoutingAllocationState(),
            local_interface="host0",
        )
        desired = compile_linux_routing_desired(
            compose_network_rules(
                (
                    _owner_rules(
                        1,
                        "a",
                        "10.0.0.0/8",
                        (a, b, v, g, d, e, j),
                        priority_prefix_length=5,
                    ),
                )
            ),
            current.allocation,
            local_interface="host0",
        )

        moves = plan_linux_route_priority_moves(current, desired)

        self.assertEqual(
            [
                (
                    move.source.path,
                    move.source.metric,
                    move.target_metric,
                )
                for move in moves
            ],
            [
                (d, 40, 50),
                (g, 30, 40),
                (v, 60, 30),
            ],
        )

    def test_empty_slot_planner_handles_recovery_from_last_slot(self):
        a, b, v, g, d, e, j = tuple(
            InterfaceIdentity(name, 20 + index)
            for index, name in enumerate(
                ("patha", "pathb", "pathv", "pathg", "pathd", "pathe", "pathj")
            )
        )
        current = compile_linux_routing_desired(
            compose_network_rules(
                (
                    _owner_rules(
                        1,
                        "a",
                        "10.0.0.0/8",
                        (a, b, g, d, e, j, v),
                        priority_prefix_length=6,
                    ),
                )
            ),
            LinuxRoutingAllocationState(),
            local_interface="host0",
        )
        desired = compile_linux_routing_desired(
            compose_network_rules(
                (
                    _owner_rules(
                        1,
                        "a",
                        "10.0.0.0/8",
                        (a, b, v, g, d, e, j),
                        priority_prefix_length=7,
                    ),
                )
            ),
            current.allocation,
            local_interface="host0",
        )

        moves = plan_linux_route_priority_moves(current, desired)

        self.assertEqual(
            [
                (move.source.path, move.source.metric, move.target_metric)
                for move in moves
            ],
            [
                (j, 60, 70),
                (e, 50, 60),
                (d, 40, 50),
                (g, 30, 40),
                (v, 80, 30),
            ],
        )

    def test_empty_slot_planner_demotes_dead_path_without_dropping_membership(self):
        a, b, v, g, d, e, j = tuple(
            InterfaceIdentity(name, 30 + index)
            for index, name in enumerate(
                ("patha", "pathb", "pathv", "pathg", "pathd", "pathe", "pathj")
            )
        )
        current = compile_linux_routing_desired(
            compose_network_rules(
                (
                    _owner_rules(
                        1,
                        "a",
                        "10.0.0.0/8",
                        (a, b, v, g, d, e, j),
                        priority_prefix_length=5,
                    ),
                )
            ),
            LinuxRoutingAllocationState(),
            local_interface="host0",
        )
        desired = compile_linux_routing_desired(
            compose_network_rules(
                (
                    _owner_rules(
                        1,
                        "a",
                        "10.0.0.0/8",
                        (a, b, g, d, v, e, j),
                        priority_prefix_length=4,
                    ),
                )
            ),
            current.allocation,
            local_interface="host0",
        )

        moves = plan_linux_route_priority_moves(current, desired)

        self.assertEqual(
            [
                (move.source.path, move.source.metric, move.target_metric)
                for move in moves
            ],
            [
                (v, 30, 60),
                (g, 40, 30),
                (d, 50, 40),
            ],
        )

    def test_every_domain_has_one_terminal_blackhole_default(self):
        composed = compose_network_rules(
            (
                _owner_rules(1, "a", "10.0.0.0/8"),
                _owner_rules(2, "b", "192.168.0.0/16"),
            )
        )

        desired = compile_linux_routing_desired(
            composed,
            LinuxRoutingAllocationState(),
            local_interface="host0",
        )

        terminal = [
            item
            for item in desired.routes
            if item.kind is LinuxRouteKind.BLACKHOLE
        ]
        self.assertEqual(len(terminal), 2)
        self.assertTrue(
            all(
                item.destination == IPv4Network("0.0.0.0/0")
                and item.metric == TERMINAL_METRIC
                for item in terminal
            )
        )

    def test_dispatch_priorities_follow_global_composed_order(self):
        broad = _owner_rules(1, "broad", "10.0.0.0/8")
        narrow = _owner_rules(2, "narrow", "10.1.0.0/16")
        desired = compile_linux_routing_desired(
            compose_network_rules((broad, narrow)),
            LinuxRoutingAllocationState(),
            local_interface="host0",
        )

        self.assertEqual(
            [
                (item.priority, str(item.destination))
                for item in desired.dispatch_rules
            ],
            [(1, "10.1.0.0/16"), (2, "10.0.0.0/8")],
        )

    def test_live_owner_set_gets_terminal_host_ingress_guard(self):
        desired = compile_linux_routing_desired(
            compose_network_rules(
                (_owner_rules(1, "a", "10.0.0.0/8"),)
            ),
            LinuxRoutingAllocationState(),
            local_interface="host0",
        )

        self.assertIsNotNone(desired.terminal_rule)
        self.assertEqual(
            desired.terminal_rule.priority,
            len(desired.dispatch_rules) + 1,
        )
        self.assertEqual(
            desired.terminal_rule.source_ifname,
            "host0",
        )

    def test_empty_owner_set_has_no_terminal_guard(self):
        desired = compile_linux_routing_desired(
            compose_network_rules(()),
            LinuxRoutingAllocationState(),
            local_interface="host0",
        )

        self.assertIsNone(desired.terminal_rule)

    def test_local_process_dispatch_compiles_exact_probe_selector(self):
        target = IPv4Network("203.0.113.24/32")
        identity = InterfaceIdentity("vpns00", 10)
        path = NetworkEndpoint.interface_path(identity)
        rules = NetworkRulesSpec(
            routing_domains=(
                RoutingDomainSpec(
                    "probe",
                    (target,),
                    (identity,),
                    TerminalDisposition.DROP,
                ),
            ),
            dispatch_rules=(
                DispatchRuleSpec(
                    target,
                    "probe",
                    source=NetworkEndpoint.local_process(),
                    bound_output=path,
                    protocol=TrafficProtocol.ICMP,
                ),
            ),
        )
        desired = compile_linux_routing_desired(
            compose_network_rules(
                (OwnedNetworkRules(OwnerToken(1), rules),)
            ),
            LinuxRoutingAllocationState(),
            local_interface="host0",
            local_process_uid=LinuxLocalProcessConfig(
                uid=65534,
                ct_mark=0x24,
            ).uid,
        )

        self.assertEqual(len(desired.dispatch_rules), 1)
        dispatch = desired.dispatch_rules[0]
        self.assertIsNone(dispatch.source_ifname)
        self.assertEqual(dispatch.local_process_uid, 65534)
        self.assertIs(dispatch.protocol, TrafficProtocol.ICMP)
        self.assertEqual(dispatch.bound_output, identity)
        self.assertEqual(dispatch.destination, target)

    def test_local_process_non_icmp_dispatch_remains_fail_closed(self):
        target = IPv4Network("203.0.113.24/32")
        identity = InterfaceIdentity("vpns00", 10)
        path = NetworkEndpoint.interface_path(identity)
        rules = NetworkRulesSpec(
            routing_domains=(
                RoutingDomainSpec(
                    "probe",
                    (target,),
                    (identity,),
                    TerminalDisposition.DROP,
                ),
            ),
            dispatch_rules=(
                DispatchRuleSpec(
                    target,
                    "probe",
                    source=NetworkEndpoint.local_process(),
                    bound_output=path,
                    protocol=TrafficProtocol.UDP,
                ),
            ),
        )

        with self.assertRaisesRegex(
            LinuxRoutingError,
            "target-proven only for ICMP",
        ):
            compile_linux_routing_desired(
                compose_network_rules(
                    (OwnedNetworkRules(OwnerToken(1), rules),)
                ),
                LinuxRoutingAllocationState(),
                local_interface="host0",
                local_process_uid=LinuxLocalProcessConfig(
                    uid=65534,
                    ct_mark=0x24,
                ).uid,
            )

    def test_local_process_routing_rejects_root_uid_even_on_internal_api(self):
        target = IPv4Network("203.0.113.24/32")
        identity = InterfaceIdentity("vpns00", 10)
        path = NetworkEndpoint.interface_path(identity)
        rules = NetworkRulesSpec(
            routing_domains=(
                RoutingDomainSpec(
                    "probe",
                    (target,),
                    (identity,),
                    TerminalDisposition.DROP,
                ),
            ),
            dispatch_rules=(
                DispatchRuleSpec(
                    target,
                    "probe",
                    source=NetworkEndpoint.local_process(),
                    bound_output=path,
                    protocol=TrafficProtocol.ICMP,
                ),
            ),
        )

        with self.assertRaisesRegex(
            LinuxRoutingError,
            "non-root 32-bit uid",
        ):
            compile_linux_routing_desired(
                compose_network_rules(
                    (OwnedNetworkRules(OwnerToken(1), rules),)
                ),
                LinuxRoutingAllocationState(),
                local_interface="host0",
                local_process_uid=0,
            )

    def test_interface_dispatch_source_is_explicitly_unsupported(self):
        path = NetworkEndpoint.interface_path(
            InterfaceIdentity("vpns00", 10)
        )
        composed = compose_network_rules(
            (
                _owner_rules(
                    1,
                    "a",
                    "10.0.0.0/8",
                    source=path,
                ),
            )
        )

        with self.assertRaises(LinuxRoutingError):
            compile_linux_routing_desired(
                composed,
                LinuxRoutingAllocationState(),
                local_interface="host0",
            )

    def test_unicast_route_rejects_terminal_metric(self):
        domain = OwnedRoutingDomainRef(OwnerToken(1), "a")
        with self.assertRaises(LinuxRoutingError):
            LinuxRouteSpec(
                domain=domain,
                table_id=1,
                destination=IPv4Network("10.0.0.0/8"),
                kind=LinuxRouteKind.UNICAST,
                protocol=UNICAST_ROUTE_PROTOCOL,
                metric=TERMINAL_METRIC,
                path=InterfaceIdentity("vpns00", 10),
            )

    def test_terminal_blackhole_requires_owned_protocol_and_metric(self):
        domain = OwnedRoutingDomainRef(OwnerToken(1), "a")
        with self.assertRaises(LinuxRoutingError):
            LinuxRouteSpec(
                domain=domain,
                table_id=1,
                destination=IPv4Network("0.0.0.0/0"),
                kind=LinuxRouteKind.BLACKHOLE,
                protocol=TERMINAL_ROUTE_PROTOCOL,
                metric=TERMINAL_METRIC - 1,
            )

    def test_metric_space_exhaustion_fails_before_partial_result(self):
        # 6553 metrics are available: 10..65530. The next one would cross terminal 65536.
        paths = tuple(
            InterfaceIdentity(f"v{i % 10000}", i + 1)
            for i in range(6554)
        )
        composed = compose_network_rules(
            (_owner_rules(1, "a", "10.0.0.0/8", paths),)
        )

        with self.assertRaises(LinuxRoutingError):
            compile_linux_routing_desired(
                composed,
                LinuxRoutingAllocationState(),
                local_interface="host0",
            )


if __name__ == "__main__":
    unittest.main()
