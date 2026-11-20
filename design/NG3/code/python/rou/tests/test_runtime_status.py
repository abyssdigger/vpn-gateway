from __future__ import annotations

import json
from ipaddress import IPv4Network
from pathlib import Path
import tempfile
import unittest

from rou.binding import LogicalPathId, PathBinding
from rou.domain import Direction
from rou.interface_identity import InterfaceIdentity
from rou.network_policy_layout import ProbePolicyOwner
from rou.payload_profile import PayloadProfileRequest
from rou.release1_config import parse_release1_config
from rou.runtime_status import (
    RuntimeReadiness,
    RuntimeStatusAgent,
    build_configured_intent_status,
    write_runtime_status_json,
)


CONFIG = """
[device.ovpn]
enabled = true
expected_interfaces = ["vpn*/2"]
use_outbound_nat = true
allow_vpn_client = "udp:11941>198.19.254.2:11940"
publish_vpn_server = "tcp/eth0:443>8443"
firewall = ["out allow icmp to 10.253.0.0/24"]

[profile.alpha]
enabled = true
direction = "outbound"
destinations = ["10.253.0.0/24"]
device_order = ["ovpn"]
"""


class RuntimeStatusTests(unittest.TestCase):
    def configured(self):
        return build_configured_intent_status(parse_release1_config(CONFIG))

    def test_configured_projection_contains_accepted_policy_intent(self):
        configured = self.configured()
        self.assertEqual(configured.host_routing, "auto")
        self.assertEqual(len(configured.devices), 1)
        device = configured.devices[0]
        self.assertEqual(device.device_id, "ovpn")
        self.assertEqual(device.expected_interfaces, ("vpn*/2",))
        self.assertTrue(device.use_outbound_nat)
        self.assertEqual(
            device.vpn_client_transports,
            ("udp:11941>198.19.254.2:11940",),
        )
        self.assertEqual(device.server_publications, ("tcp/eth0:443>8443",))
        self.assertEqual(
            device.firewall_rules,
            ("out allow icmp to 10.253.0.0/24",),
        )

        profile = configured.profiles[0]
        self.assertEqual(profile.profile_id, "alpha")
        self.assertEqual(profile.direction, "outbound")
        self.assertEqual(profile.destinations, ("10.253.0.0/24",))
        self.assertEqual(profile.device_order, ("ovpn",))
        self.assertIsNone(profile.availability_check)

    def test_status_exposes_manual_host_routing_intent(self):
        configured = build_configured_intent_status(
            parse_release1_config('host_routing = "manual"')
        )
        self.assertEqual(configured.host_routing, "manual")
        self.assertEqual(
            RuntimeStatusAgent(configured).snapshot().configured_intent.host_routing,
            "manual",
        )

    def test_status_exposes_device_default_and_profile_selection(self):
        configured = build_configured_intent_status(parse_release1_config("""
[device.ovpn]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false

[device.ovpn.availability_check]
mechanism = "icmp"
target = "198.51.100.10"

[profile.alpha]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["ovpn"]
availability_check = "default"
"""))
        self.assertEqual(
            configured.devices[0].availability_check,
            "icmp/198.51.100.10",
        )
        self.assertEqual(
            configured.profiles[0].availability_check,
            "default",
        )
        self.assertEqual(
            RuntimeStatusAgent(configured).snapshot().availability_state[0].state,
            "unconfirmed",
        )

    def test_availability_status_reports_monitoring_problem_and_unconfirmed(self):
        configured = build_configured_intent_status(parse_release1_config("""
[device.ovpn]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false

[device.ovpn.availability_check]
mechanism = "icmp"
target = "198.51.100.10"

[profile.alpha]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["ovpn"]
availability_check = "default"
"""))
        agent = RuntimeStatusAgent(configured)
        agent.confirm_availability(())
        self.assertEqual(
            agent.snapshot().availability_state[0].state,
            "monitoring",
        )

        owner = ProbePolicyOwner(
            "alpha",
            LogicalPathId("ovpn", 0, 0),
        )
        agent.confirm_availability((owner,))
        self.assertEqual(
            agent.snapshot().availability_state[0].state,
            "problem",
        )

        agent.mark_unconfirmed(
            readiness=RuntimeReadiness.DEGRADED,
            problem="availability runtime is not exact",
        )
        self.assertEqual(
            agent.snapshot().availability_state[0].state,
            "unconfirmed",
        )

    def test_confirmed_effective_state_reports_current_order_and_endpoint(self):
        agent = RuntimeStatusAgent(self.configured())
        path = LogicalPathId("ovpn", 0, 0)
        endpoint = InterfaceIdentity("vpn0", 11)
        agent.confirm_effective(
            (
                PayloadProfileRequest(
                    "alpha",
                    Direction.OUTBOUND,
                    (IPv4Network("10.253.0.0/24"),),
                    (path,),
                ),
            ),
            (PathBinding(path, endpoint),),
        )

        snapshot = agent.snapshot()
        self.assertIs(snapshot.readiness, RuntimeReadiness.READY)
        self.assertEqual(snapshot.blocking_problems, ())
        self.assertEqual(snapshot.unknown_or_unconfirmed_fields, ())
        self.assertEqual(
            snapshot.availability_state[0].state,
            "disabled",
        )
        effective = snapshot.confirmed_effective_state
        self.assertIsNotNone(effective)
        self.assertEqual(effective[0].profile_id, "alpha")
        self.assertEqual(effective[0].ordered_paths[0].ifname, "vpn0")
        self.assertEqual(effective[0].ordered_paths[0].ifindex, 11)

    def test_failure_invalidates_previous_confirmed_effective_state(self):
        agent = RuntimeStatusAgent(self.configured())
        path = LogicalPathId("ovpn", 0, 0)
        agent.confirm_effective(
            (
                PayloadProfileRequest(
                    "alpha",
                    Direction.OUTBOUND,
                    (IPv4Network("10.253.0.0/24"),),
                    (path,),
                ),
            ),
            (PathBinding(path, InterfaceIdentity("vpn0", 11)),),
        )
        agent.mark_unconfirmed(
            readiness=RuntimeReadiness.DEGRADED,
            problem="network policy exact postcondition is not confirmed",
        )

        snapshot = agent.snapshot()
        self.assertIsNone(snapshot.confirmed_effective_state)
        self.assertEqual(
            snapshot.blocking_problems,
            ("network policy exact postcondition is not confirmed",),
        )
        self.assertEqual(
            snapshot.unknown_or_unconfirmed_fields,
            ("confirmed_effective_state",),
        )

    def test_json_publisher_replaces_one_current_snapshot(self):
        agent = RuntimeStatusAgent(self.configured())
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "status.json"
            write_runtime_status_json(path, agent.snapshot())
            first = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(first["readiness"], "starting")
            self.assertIsNone(first["confirmed_effective_state"])

            path_id = LogicalPathId("ovpn", 0, 0)
            agent.confirm_effective(
                (
                    PayloadProfileRequest(
                        "alpha",
                        Direction.OUTBOUND,
                        (IPv4Network("10.253.0.0/24"),),
                        (path_id,),
                    ),
                ),
                (PathBinding(path_id, InterfaceIdentity("vpn0", 12)),),
            )
            write_runtime_status_json(path, agent.snapshot())
            second = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(second["readiness"], "ready")
            self.assertEqual(
                second["confirmed_effective_state"][0]["ordered_paths"][0]["ifindex"],
                12,
            )
            self.assertEqual(
                tuple(item.name for item in Path(root).iterdir()),
                ("status.json",),
            )


if __name__ == "__main__":
    unittest.main()
