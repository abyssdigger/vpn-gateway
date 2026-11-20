from __future__ import annotations

from ipaddress import IPv4Interface
import unittest

from rou.forwarding_gate import ForwardingGateState
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
    host_interface="vpng0",
    inner_interface="vnga-inner0",
    inner_address=IPv4Interface("198.19.255.2/32"),
)
ROUTED_DOMAIN = DOMAIN

def config(direction: str, *, default_snat_address: str | None = None):
    outbound_nat = (
        "use_outbound_nat = false\n"
        if direction.startswith("outbound") or direction.startswith("bidirectional")
        else ""
    )
    default = (
        ""
        if default_snat_address is None
        else f'default_snat_address = "{default_snat_address}"\n'
    )
    return parse_release1_config(
        f"""
{default}
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
            raise RuntimeError("synthetic routing convergence failure")


class SelectedHostBoundaryTests(unittest.TestCase):
    def test_inbound_destination_is_managed_without_return_owner(self):
        desired = build_selected_host_boundary_desired(
            config("inbound"),
            DOMAIN,
        )
        self.assertEqual(
            tuple(item.destination.with_prefixlen for item in desired.routing.routes),
            ("10.0.0.0/24",),
        )
        self.assertIsNotNone(desired.routing.bypass)
        self.assertIsNotNone(desired.routing.dispatch)

    def test_routed_boundary_uses_device_only_managed_routes(self):
        desired = build_selected_host_boundary_desired(
            config("bidirectional"),
            ROUTED_DOMAIN,
        )
        self.assertEqual(desired.routing.routes[0].interface, "vpng0")
        self.assertEqual(
            desired.routing.bypass.interface,
            "vpng0",
        )

    def test_snat_identity_adds_exact_managed_route(self):
        desired = build_selected_host_boundary_desired(
            config(
                "inbound+snat",
                default_snat_address="198.19.255.10",
            ),
            ROUTED_DOMAIN,
        )
        self.assertEqual(
            {item.destination.with_prefixlen for item in desired.routing.routes},
            {"10.0.0.0/24", "198.19.255.10/32"},
        )
        by_destination = {
            item.destination.with_prefixlen: item
            for item in desired.routing.routes
        }
        remote = by_destination["10.0.0.0/24"]
        identity = by_destination["198.19.255.10/32"]
        self.assertIsNone(remote.gateway)
        self.assertFalse(remote.onlink)
        self.assertEqual(str(identity.gateway), "198.19.255.2")
        self.assertTrue(identity.onlink)

    def test_snat_identity_cannot_reuse_managed_boundary_service_address(self):
        with self.assertRaisesRegex(
            ValueError,
            "conflicts with managed-boundary",
        ):
            build_selected_host_boundary_desired(
                config(
                    "inbound+snat",
                    default_snat_address="198.19.255.2",
                ),
                ROUTED_DOMAIN,
            )

    def test_exact_runtime_needs_no_containment(self):
        contribution = RuntimeContribution(
            [SelectedHostBoundaryObservation(True, ())]
        )
        gate = Gate()
        result = reconcile_selected_host_boundary_runtime_once(
            gate,
            contribution,
        )
        self.assertEqual(result.status, SelectedHostBoundaryRuntimeStatus.EXACT)
        self.assertEqual(gate.set_calls, 0)
        self.assertEqual(contribution.converge_calls, 0)

    def test_drift_is_contained_then_reconciled(self):
        contribution = RuntimeContribution(
            [
                SelectedHostBoundaryObservation(False, ()),
                SelectedHostBoundaryObservation(True, ()),
            ]
        )
        gate = Gate()
        result = reconcile_selected_host_boundary_runtime_once(
            gate,
            contribution,
        )
        self.assertEqual(
            result.status,
            SelectedHostBoundaryRuntimeStatus.RECONCILED,
        )
        self.assertEqual(gate.state, ForwardingGateState.DISABLED)
        self.assertEqual(contribution.converge_calls, 1)

    def test_conflict_is_reported_after_containment(self):
        contribution = RuntimeContribution(
            [SelectedHostBoundaryObservation(False, ("foreign rule",))]
        )
        gate = Gate()
        result = reconcile_selected_host_boundary_runtime_once(
            gate,
            contribution,
        )
        self.assertEqual(
            result.status,
            SelectedHostBoundaryRuntimeStatus.CONFLICT,
        )
        self.assertEqual(gate.state, ForwardingGateState.DISABLED)
        self.assertEqual(contribution.converge_calls, 0)


if __name__ == "__main__":
    unittest.main()
