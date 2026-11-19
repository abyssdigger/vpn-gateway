from __future__ import annotations

import json
from ipaddress import IPv4Interface
import unittest

from rou.forwarding_gate import ForwardingGateState
from rou.managed_l3_boundary import ManagedL3BoundaryBackend
from rou.managed_network_domain import ManagedNetworkDomainSpec
from rou.release1_config import parse_release1_config
from rou.selected_host_boundary import (
    SelectedHostBoundaryObservation,
    SelectedHostBoundaryRuntimeStatus,
    SelectedLinuxHostBoundaryContribution,
    build_selected_host_boundary_desired,
    reconcile_selected_host_boundary_runtime_once,
)


DOMAIN = ManagedNetworkDomainSpec(
    namespace="vpn-gate-alpha",
    host_interface="vnga-host0",
    inner_interface="vnga-inner0",
    host_address=IPv4Interface("198.19.255.1/30"),
    inner_address=IPv4Interface("198.19.255.2/30"),
)

ROUTED_DOMAIN = ManagedNetworkDomainSpec(
    namespace="vpn-gate-alpha",
    host_interface="vnga-host0",
    inner_interface="vnga-inner0",
    host_address=None,
    inner_address=IPv4Interface("198.19.255.2/32"),
    primary_backend=ManagedL3BoundaryBackend.ROUTED_VETH_PROXY_ARP,
)


def config(direction: str):
    outbound_nat = (
        "use_outbound_nat = false\n"
        if direction.startswith("outbound") or direction.startswith("bidirectional")
        else ""
    )
    return parse_release1_config(
        f"""
[device.vpn]
enabled = true
expected_interfaces = ["vpn0"]
{outbound_nat}
[profile.p]
enabled = true
direction = "{direction}"
destinations = ["10.0.0.0/24"]
device_order = ["vpn"]
"""
    )


class Observation:
    def __init__(self, *, exact=True, conflicts=()):
        self.exact = exact
        self.conflicts = tuple(conflicts)


class RouteBackend:
    def __init__(self, routes=(), rules=()):
        self.runner = self
        self.routes = list(routes)
        self.rules = list(rules)

    def _cmd(self, *args):
        return args

    def run(self, argv):
        if "route" in argv:
            return json.dumps(self.routes)
        return json.dumps(self.rules)


class BootstrapBackend:
    def __init__(self, observation):
        self.observation = observation
        self.converged = 0
        self.cleaned = 0

    def observe(self, desired):
        return self.observation


class NftBackend:
    def __init__(self, observation):
        self.observation = observation

    def observe(self, desired):
        return self.observation


class Gate:
    def __init__(self, state=ForwardingGateState.ENABLED, *, fail_set=False):
        self.state = state
        self.fail_set = fail_set
        self.set_calls = 0

    def observe_forwarding_gate(self):
        return self.state

    def set_forwarding_gate(self, desired):
        self.set_calls += 1
        if self.fail_set:
            raise RuntimeError("synthetic gate write failure")
        self.state = desired


class RuntimeContribution(SelectedLinuxHostBoundaryContribution):
    def __init__(self, observations, *, fail_converge=False):
        self.observations = list(observations)
        self.fail_converge = fail_converge
        self.converge_calls = 0

    def observe(self):
        return self.observations.pop(0)

    def converge(self):
        self.converge_calls += 1
        if self.fail_converge:
            raise RuntimeError("synthetic boundary convergence failure")


class SelectedHostBoundaryTests(unittest.TestCase):
    def test_inbound_route_return_uses_selected_bootstrap_without_stateful_owner(self):
        desired = build_selected_host_boundary_desired(
            config("inbound+route-return"),
            DOMAIN,
        )
        self.assertEqual(
            tuple(item.destination.with_prefixlen for item in desired.bootstrap_owner.routes),
            ("10.0.0.0/24",),
        )
        self.assertIsNotNone(desired.bootstrap_owner.bypass)
        self.assertEqual(len(desired.bootstrap_owner.pairs), 1)
        self.assertIsNone(desired.return_owner.return_route)
        self.assertIsNone(desired.return_owner.return_rule)
        self.assertIsNone(desired.return_owner.return_nft)
        self.assertEqual(desired.return_owner.bootstrap_routes, ())
        self.assertEqual(desired.return_owner.underlay_pins, ())

    def test_routed_domain_uses_device_only_bootstrap_and_return_routes(self):
        desired = build_selected_host_boundary_desired(
            config("bidirectional"),
            ROUTED_DOMAIN,
        )
        self.assertTrue(desired.bootstrap_owner.routes)
        self.assertTrue(
            all(route.via is None for route in desired.bootstrap_owner.routes)
        )
        self.assertIsNotNone(desired.return_owner.return_route)
        self.assertIsNone(desired.return_owner.return_route.via)

    def test_inbound_default_has_stateful_return_and_no_bootstrap(self):
        desired = build_selected_host_boundary_desired(
            config("inbound"),
            DOMAIN,
        )
        self.assertEqual(desired.bootstrap_owner.routes, ())
        self.assertIsNone(desired.bootstrap_owner.bypass)
        self.assertIsNotNone(desired.return_owner.return_route)
        self.assertIsNotNone(desired.return_owner.return_rule)
        self.assertIsNotNone(desired.return_owner.return_nft)

    def test_bidirectional_default_has_both_bootstrap_and_stateful_return(self):
        desired = build_selected_host_boundary_desired(
            config("bidirectional"),
            DOMAIN,
        )
        self.assertEqual(len(desired.bootstrap_owner.routes), 1)
        self.assertIsNotNone(desired.return_owner.return_route)
        self.assertIsNotNone(desired.return_owner.return_rule)
        self.assertIsNotNone(desired.return_owner.return_nft)

    def test_absent_return_owner_is_exact_only_when_reserved_scope_is_empty(self):
        desired = build_selected_host_boundary_desired(
            config("inbound+route-return"),
            DOMAIN,
        )
        contribution = SelectedLinuxHostBoundaryContribution(
            route_backend=RouteBackend(),
            return_nft_backend=NftBackend(Observation()),
            bootstrap_backend=BootstrapBackend(Observation()),
            desired=desired,
        )
        self.assertTrue(contribution.observe().exact)

        contribution.route_backend.routes.append(
            {
                "table": 2147418113,
                "dst": "default",
                "gateway": "192.0.2.1",
                "dev": "foreign0",
                "protocol": 99,
            }
        )
        observed = contribution.observe()
        self.assertFalse(observed.exact)
        self.assertTrue(observed.conflicts)

    def test_exact_stateful_return_owner_is_observed_exact(self):
        desired = build_selected_host_boundary_desired(
            config("inbound"),
            DOMAIN,
        )
        route = desired.return_owner.return_route
        rule = desired.return_owner.return_rule
        contribution = SelectedLinuxHostBoundaryContribution(
            route_backend=RouteBackend(
                routes=(
                    {
                        "table": route.table,
                        "dst": "default",
                        "gateway": str(route.via),
                        "dev": route.interface,
                        "protocol": route.protocol,
                    },
                ),
                rules=(
                    {
                        "priority": rule.priority,
                        "src": "all",
                        "fwmark": hex(rule.mark),
                        "table": rule.table,
                    },
                ),
            ),
            return_nft_backend=NftBackend(Observation()),
            bootstrap_backend=BootstrapBackend(Observation()),
            desired=desired,
        )
        self.assertTrue(contribution.observe().exact)

    def test_exact_device_only_stateful_return_owner_is_observed_exact(self):
        desired = build_selected_host_boundary_desired(
            config("inbound"),
            ROUTED_DOMAIN,
        )
        route = desired.return_owner.return_route
        rule = desired.return_owner.return_rule
        contribution = SelectedLinuxHostBoundaryContribution(
            route_backend=RouteBackend(
                routes=(
                    {
                        "table": route.table,
                        "dst": "default",
                        "dev": route.interface,
                        "protocol": route.protocol,
                    },
                ),
                rules=(
                    {
                        "priority": rule.priority,
                        "src": "all",
                        "fwmark": hex(rule.mark),
                        "table": rule.table,
                    },
                ),
            ),
            return_nft_backend=NftBackend(Observation()),
            bootstrap_backend=BootstrapBackend(Observation()),
            desired=desired,
        )
        self.assertTrue(contribution.observe().exact)

    def test_foreign_reserved_return_rule_is_conflict(self):
        desired = build_selected_host_boundary_desired(
            config("inbound"),
            DOMAIN,
        )
        route = desired.return_owner.return_route
        rule = desired.return_owner.return_rule
        contribution = SelectedLinuxHostBoundaryContribution(
            route_backend=RouteBackend(
                routes=(
                    {
                        "table": route.table,
                        "dst": "default",
                        "gateway": str(route.via),
                        "dev": route.interface,
                        "protocol": route.protocol,
                    },
                ),
                rules=(
                    {
                        "priority": rule.priority,
                        "src": "all",
                        "fwmark": "0x1234",
                        "table": rule.table,
                    },
                ),
            ),
            return_nft_backend=NftBackend(Observation()),
            bootstrap_backend=BootstrapBackend(Observation()),
            desired=desired,
        )
        observed = contribution.observe()
        self.assertFalse(observed.exact)
        self.assertIn("reserved host return RPDB rule differs", observed.conflicts[0])


    def test_runtime_exact_boundary_does_not_close_forwarding(self):
        gate = Gate()
        contribution = RuntimeContribution(
            (SelectedHostBoundaryObservation(True, ()),)
        )
        result = reconcile_selected_host_boundary_runtime_once(
            gate,
            contribution,
        )
        self.assertEqual(result.status, SelectedHostBoundaryRuntimeStatus.EXACT)
        self.assertTrue(result.confirmed)
        self.assertEqual(gate.set_calls, 0)
        self.assertEqual(contribution.converge_calls, 0)

    def test_runtime_drift_closes_forwarding_before_repair(self):
        gate = Gate()
        contribution = RuntimeContribution(
            (
                SelectedHostBoundaryObservation(False, ()),
                SelectedHostBoundaryObservation(True, ()),
            )
        )
        result = reconcile_selected_host_boundary_runtime_once(
            gate,
            contribution,
        )
        self.assertEqual(
            result.status,
            SelectedHostBoundaryRuntimeStatus.RECONCILED,
        )
        self.assertTrue(result.confirmed)
        self.assertIs(gate.state, ForwardingGateState.DISABLED)
        self.assertEqual(gate.set_calls, 1)
        self.assertEqual(contribution.converge_calls, 1)

    def test_runtime_conflict_contains_without_adoption(self):
        gate = Gate()
        contribution = RuntimeContribution(
            (SelectedHostBoundaryObservation(False, ("foreign owner",)),)
        )
        result = reconcile_selected_host_boundary_runtime_once(
            gate,
            contribution,
        )
        self.assertEqual(
            result.status,
            SelectedHostBoundaryRuntimeStatus.CONFLICT,
        )
        self.assertFalse(result.confirmed)
        self.assertIs(gate.state, ForwardingGateState.DISABLED)
        self.assertEqual(contribution.converge_calls, 0)


if __name__ == "__main__":
    unittest.main()
