from __future__ import annotations

from ipaddress import IPv4Address
import unittest

from rou.alpha_runtime import AlphaPreparedPolicy
from rou.availability_confirmation import AvailabilityOutcome
from rou.interface_identity import InterfaceIdentity
from rou.payload_routing_desired import ManagedRouteType
from rou.probe_runtime import ProbeEvidence


CONFIG = """
[device.primary]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false

[device.backup]
enabled = true
expected_interfaces = ["vpn1"]
use_outbound_nat = false

[profile.alpha]
enabled = true
direction = "outbound"
destinations = ["10.253.0.1/32"]
device_order = ["primary", "backup"]

[profile.alpha.availability_check]
mechanism = "icmp"
target = "10.253.0.1"
"""


class AlphaAvailabilityStateTests(unittest.TestCase):
    def test_structural_rebuild_preserves_current_effective_failover_order(self):
        prepared = AlphaPreparedPolicy.from_text(
            CONFIG,
            local_address=IPv4Address("198.19.255.2"),
        )
        host = InterfaceIdentity("vnga-inner0", 7)
        primary = InterfaceIdentity("vpn0", 11)
        backup = InterfaceIdentity("vpn1", 12)
        interfaces = (InterfaceIdentity("lo", 1), host, primary, backup)

        first = prepared.build_current(host, interfaces)
        initial_metrics = {
            route.endpoint.ifname: route.metric
            for route in first.routing.routes
            if route.route_type is ManagedRouteType.UNICAST
        }
        self.assertEqual(initial_metrics, {"vpn0": 1, "vpn1": 2})

        primary_context = next(
            context
            for context in prepared.availability_runtime.current_contexts
            if context.intent.owner.path_id.device_id == "primary"
        )
        for _ in range(2):
            prepared.availability_manager.apply_evidence(
                ProbeEvidence(
                    primary_context,
                    AvailabilityOutcome.NEGATIVE,
                ),
                prepared.last_baseline_profiles,
                prepared.config,
            )

        rebuilt = prepared.build_current(host, interfaces)
        rebuilt_metrics = {
            route.endpoint.ifname: route.metric
            for route in rebuilt.routing.routes
            if route.route_type is ManagedRouteType.UNICAST
        }
        self.assertEqual(rebuilt_metrics, {"vpn0": 2, "vpn1": 1})
        self.assertEqual(
            tuple(
                path.device_id
                for path in prepared.last_profiles[0].ordered_paths
            ),
            ("backup", "primary"),
        )


if __name__ == "__main__":
    unittest.main()
