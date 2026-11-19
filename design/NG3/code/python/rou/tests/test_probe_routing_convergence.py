from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.binding import LogicalPathId
from rou.interface_identity import InterfaceIdentity
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.network_policy_layout import (
    ProbePolicyOwner,
    ProbeRoutingDemand,
    allocate_network_policy_layout,
)
from rou.payload_routing_desired import ManagedRouteType
from rou.probe_policy import (
    AvailabilityProbeIntent,
    ProbeLocalPlatform,
    build_probe_network_policy_desired_state,
)
from rou.probe_routing_convergence import (
    ProbeRoutingConvergenceStatus,
    ProbeRoutingPhysicalSnapshot,
    ProbeRoutingTransactionStatus,
    converge_probe_routing,
    converge_probe_routing_step_once,
)
from rou.route_priority_inventory import RoutePriorityPathRoute
from rou.structural_routing_inventory import (
    ObservedManagedRoute,
    ObservedManagedRule,
    ReservedOwnerKind,
    ReservedPolicyConflict,
    StructuralRoutingObservation,
)


PATH = LogicalPathId("device", 0, 0)
EP = InterfaceIdentity("vpn0", 20)
OLD_EP = InterfaceIdentity("vpn0", 19)
TARGET = IPv4Address("198.51.100.7")
LOCAL = ProbeLocalPlatform(4242, 0x20000001)


def desired_state():
    owner = ProbePolicyOwner("corp", PATH)
    layout = allocate_network_policy_layout(
        (),
        (ProbeRoutingDemand(owner),),
        NG3_LINUX_POLICY_PLATFORM,
    )
    return build_probe_network_policy_desired_state(
        (AvailabilityProbeIntent(owner, TARGET),),
        layout,
        (RoutePriorityPathRoute(PATH, EP),),
        NG3_LINUX_POLICY_PLATFORM,
        LOCAL,
    )


def observe_route(spec, endpoint=None):
    return ObservedManagedRoute(
        table=spec.table,
        destination=spec.destination,
        route_type=spec.route_type,
        protocol=spec.protocol,
        metric=spec.metric,
        scope=(
            None
            if spec.route_type is ManagedRouteType.BLACKHOLE
            else 253
        ),
        endpoint=(
            endpoint
            if spec.route_type is ManagedRouteType.UNICAST
            else None
        )
        if endpoint is not None
        else spec.endpoint,
        gateway=spec.gateway,
        onlink=spec.onlink,
    )


def observe_rule(spec):
    return ObservedManagedRule(
        priority=spec.priority,
        table=spec.table,
        ingress=None,
        destination=IPv4Network(f"{spec.target}/32"),
        uid_start=spec.process_uid,
        uid_end=spec.process_uid,
        ipproto=1,
    )


class MemoryBackend:
    def __init__(
        self,
        desired,
        *,
        routes=(),
        rules=(),
        conflicts=(),
        interfaces=(EP,),
        change_interfaces_after_write=False,
    ):
        self.desired = desired
        self.routes = list(routes)
        self.rules = list(rules)
        self.conflicts = tuple(conflicts)
        self.interfaces = tuple(interfaces)
        self.change_interfaces_after_write = change_interfaces_after_write
        self.actions = []
        self._writes = 0

    def observe_probe_routing_snapshot(self):
        return ProbeRoutingPhysicalSnapshot(
            self.interfaces,
            StructuralRoutingObservation(
                tuple(self.routes),
                tuple(self.rules),
                self.conflicts,
            ),
        )

    def _after_write(self):
        self._writes += 1
        if self.change_interfaces_after_write and self._writes == 1:
            self.interfaces = (
                InterfaceIdentity("vpn0", EP.ifindex + 1),
            )

    def add_route(self, spec):
        self.actions.append(("add_route", spec))
        self.routes.append(observe_route(spec))
        self._after_write()

    def delete_route(self, route):
        self.actions.append(("delete_route", route))
        self.routes.remove(route)
        self._after_write()

    def add_rule(self, spec):
        self.actions.append(("add_rule", spec))
        self.rules.append(observe_rule(spec))
        self._after_write()

    def delete_rule(self, rule):
        self.actions.append(("delete_rule", rule))
        self.rules.remove(rule)
        self._after_write()


class ProbeRoutingConvergenceTests(unittest.TestCase):
    def test_empty_state_converges_guard_path_rule(self):
        desired = desired_state()
        backend = MemoryBackend(desired)

        result = converge_probe_routing(
            backend,
            desired,
            NG3_LINUX_POLICY_PLATFORM,
        )

        self.assertEqual(
            result.status,
            ProbeRoutingTransactionStatus.CONFIRMED,
        )
        self.assertTrue(result.confirmed)
        self.assertEqual(
            [name for name, _ in backend.actions],
            ["add_route", "add_route", "add_rule"],
        )
        self.assertEqual(
            backend.actions[0][1].route_type,
            ManagedRouteType.BLACKHOLE,
        )
        self.assertEqual(
            backend.actions[1][1].route_type,
            ManagedRouteType.UNICAST,
        )

    def test_drifted_table_with_current_rule_withdraws_rule_first(self):
        desired = desired_state()
        guard = next(
            route
            for route in desired.routes
            if route.route_type is ManagedRouteType.BLACKHOLE
        )
        path = next(
            route
            for route in desired.routes
            if route.route_type is ManagedRouteType.UNICAST
        )
        old_path = ObservedManagedRoute(
            table=path.table,
            destination=path.destination,
            route_type=path.route_type,
            protocol=path.protocol,
            metric=path.metric,
            scope=253,
            endpoint=OLD_EP,
            gateway=path.gateway,
            onlink=path.onlink,
        )
        rule = observe_rule(desired.rules[0])
        backend = MemoryBackend(
            desired,
            routes=(observe_route(guard), old_path),
            rules=(rule,),
            interfaces=(EP, OLD_EP),
        )

        result = converge_probe_routing(
            backend,
            desired,
            NG3_LINUX_POLICY_PLATFORM,
        )

        self.assertTrue(result.confirmed)
        self.assertEqual(backend.actions[0], ("delete_rule", rule))
        self.assertEqual(
            [name for name, _ in backend.actions],
            [
                "delete_rule",
                "delete_route",
                "add_route",
                "add_rule",
            ],
        )

    def test_one_step_rejects_interface_generation_change(self):
        desired = desired_state()
        backend = MemoryBackend(
            desired,
            change_interfaces_after_write=True,
        )
        result = converge_probe_routing_step_once(
            backend,
            desired,
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertEqual(
            result.status,
            ProbeRoutingConvergenceStatus.POSTCONDITION_FAILED,
        )
        self.assertFalse(result.confirmed)

    def test_probe_conflict_stops_without_mutation(self):
        desired = desired_state()
        conflict = ReservedPolicyConflict(
            ReservedOwnerKind.PROBE,
            "rule priority=8192",
            "synthetic probe conflict",
        )
        backend = MemoryBackend(
            desired,
            conflicts=(conflict,),
        )
        result = converge_probe_routing(
            backend,
            desired,
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertEqual(
            result.status,
            ProbeRoutingTransactionStatus.FAILED,
        )
        self.assertEqual(backend.actions, [])
        self.assertIn("synthetic probe conflict", result.diagnostic)

    def test_exact_state_is_confirmed_without_write(self):
        desired = desired_state()
        backend = MemoryBackend(
            desired,
            routes=tuple(observe_route(route) for route in desired.routes),
            rules=tuple(observe_rule(rule) for rule in desired.rules),
        )
        result = converge_probe_routing(
            backend,
            desired,
            NG3_LINUX_POLICY_PLATFORM,
        )
        self.assertTrue(result.confirmed)
        self.assertEqual(backend.actions, [])


if __name__ == "__main__":
    unittest.main()
