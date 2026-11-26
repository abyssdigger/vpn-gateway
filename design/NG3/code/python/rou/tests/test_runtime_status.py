from __future__ import annotations

import json
from ipaddress import IPv4Network
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rou.binding import LogicalPathId, PathBinding
from rou.domain import Direction
from rou.interface_identity import InterfaceIdentity
from rou.managed_device_manager import (
    ManagedDeviceDesiredState,
    ManagedDeviceRealization,
)
from rou.managed_wireguard_adapter import ManagedWireGuardState
from rou.network_policy_layout import ProbePolicyOwner
from rou.payload_profile import PayloadProfileRequest
from rou.release1_config import parse_current_config, parse_release1_config
from rou.managed_device_demand import project_final
from rou.wireguard_peer_manager import (
    WireGuardGroupOwnershipRecord,
    WireGuardPeerRealization,
)
from rou.runtime_status import (
    RuntimeReadiness,
    RuntimeStatusAgent,
    RuntimeStatusFilePublisher,
    build_configured_intent_status,
    read_release_version,
    render_runtime_status_text,
    write_runtime_status_json,
    write_runtime_status_text,
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
        self.assertEqual(configured.helper_routing_interfaces, ":none")
        self.assertEqual(configured.helper_routing_policy, "peaceful")
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

    def test_current_status_preserves_configured_warm_target_and_observed_demand(self):
        config = parse_current_config(CONFIG + "warm_paths = 2\n")
        agent = RuntimeStatusAgent(build_configured_intent_status(config))
        self.assertEqual(agent.snapshot().configured_intent.profiles[0].warm_paths, 2)
        self.assertIsNone(agent.snapshot().managed_profile_demands)
        observed = PathBinding(LogicalPathId("ovpn", 0, 0), InterfaceIdentity("vpn0", 11))
        agent.confirm_managed_demand(project_final(config, (observed,)))
        encoded = json.loads(json.dumps(agent.snapshot().to_dict()))
        demand = encoded["managed_profile_demands"][0]
        self.assertEqual(demand["regular_target"], 2)
        self.assertEqual(demand["regular_present"], 1)
        self.assertEqual(demand["regular_deficit"], 1)
        self.assertEqual(demand["ordinary_device_ids"], [])
        self.assertEqual(demand["external_ordinary_present"], 1)
        self.assertEqual(demand["managed_ordinary_contributions"], [])
        agent.confirm_managed_demand(None)
        self.assertIsNone(agent.snapshot().managed_profile_demands)

    def test_status_carries_ordered_observed_managed_contributions(self):
        devices = "".join(f"""
[device.{name}]
enabled = true
use_outbound_nat = true
[device.{name}.managed_vpn]
kind = "wireguard"
interface = "wg{index}"
address = "10.200.0.{index}/32"
private_key_file = "/secret/{name}.key"
[[device.{name}.managed_vpn.peers]]
id = "peer"
public_key = "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="
endpoint = "198.51.100.{index}:51820"
probe_target = "10.201.0.{index}"
""" for name, index in (("a", 1), ("b", 2)))
        config = parse_current_config(devices + CONFIG.replace(
            'device_order = ["ovpn"]', 'device_order = ["b", "ovpn", "a"]'
        ) + "warm_paths = 2\n")
        agent = RuntimeStatusAgent(build_configured_intent_status(config))
        agent.confirm_managed_demand(project_final(config, (
            PathBinding(LogicalPathId("a", 0, 0), InterfaceIdentity("wg1", 12)),
            PathBinding(LogicalPathId("ovpn", 0, 0), InterfaceIdentity("vpn0", 11)),
        )))
        demand = json.loads(json.dumps(agent.snapshot().to_dict()))["managed_profile_demands"][0]
        self.assertEqual(demand["regular_present"], 2)
        self.assertEqual(demand["external_ordinary_present"], 1)
        self.assertEqual(demand["managed_ordinary_contributions"], [
            {"device_id": "b", "fresh_path_count": 0},
            {"device_id": "a", "fresh_path_count": 1},
        ])
        self.assertEqual(demand["ordinary_device_ids"], ["a"])

    def test_status_exposes_scoped_helper_routing_intent(self):
        configured = build_configured_intent_status(
            parse_release1_config(
                'helper_routing_interfaces = ":local,eth0"'
            )
        )
        self.assertEqual(configured.helper_routing_interfaces, ":local,eth0")
        self.assertEqual(configured.helper_routing_policy, "peaceful")
        snapshot = RuntimeStatusAgent(configured).snapshot().configured_intent
        self.assertEqual(snapshot.helper_routing_interfaces, ":local,eth0")
        self.assertEqual(snapshot.helper_routing_policy, "peaceful")

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

    def test_status_carries_authoritative_managed_device_realization(self):
        agent = RuntimeStatusAgent(self.configured())
        agent.confirm_managed_devices(
            (
                ManagedDeviceRealization(
                    device_id="ovpn",
                    desired_state=ManagedDeviceDesiredState.PRESENT,
                    desired_generation="desired-a",
                    confirmed_state=ManagedWireGuardState.PRESENT,
                    confirmed_generation="desired-a",
                ),
            )
        )

        snapshot = agent.snapshot()
        self.assertEqual(len(snapshot.managed_device_realizations), 1)
        item = snapshot.managed_device_realizations[0]
        self.assertEqual(item.desired_generation, "desired-a")
        self.assertEqual(item.confirmed_generation, "desired-a")
        self.assertEqual(
            snapshot.to_dict()["managed_device_realizations"][0]["confirmed_state"],
            ManagedWireGuardState.PRESENT,
        )

    def test_status_carries_authoritative_wireguard_peer_realization(self):
        agent = RuntimeStatusAgent(self.configured())
        realization = WireGuardPeerRealization(
            device_id="wg-main",
            base_generation="base-a",
            interface_ifname="wg0",
            interface_ifindex=17,
            group_owners=(
                WireGuardGroupOwnershipRecord("alpha", "edge-a"),
            ),
            generation="peer-generation-a",
        )
        agent.confirm_wireguard_peers((realization,))

        snapshot = agent.snapshot()
        self.assertEqual(snapshot.wireguard_peer_realizations, (realization,))
        encoded = snapshot.to_dict()["wireguard_peer_realizations"][0]
        self.assertEqual(encoded["device_id"], "wg-main")
        self.assertEqual(encoded["generation"], "peer-generation-a")
        self.assertEqual(
            encoded["group_owners"][0],
            {"profile_id": "alpha", "owner_peer_id": "edge-a"},
        )

    def test_status_rejects_duplicate_wireguard_peer_realization(self):
        agent = RuntimeStatusAgent(self.configured())
        realization = WireGuardPeerRealization(
            device_id="wg-main",
            base_generation="base-a",
            interface_ifname="wg0",
            interface_ifindex=17,
            group_owners=(),
            generation="peer-generation-a",
        )
        with self.assertRaisesRegex(
            ValueError,
            "duplicate WireGuard peer realization",
        ):
            agent.confirm_wireguard_peers((realization, realization))

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

    def test_degraded_owner_problem_preserves_confirmed_effective_state(self):
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
        agent.mark_degraded(
            problem="D.002 current realization is unconfirmed",
            unknown_fields=("wireguard_peer_realizations",),
        )

        snapshot = agent.snapshot()
        self.assertIs(snapshot.readiness, RuntimeReadiness.DEGRADED)
        self.assertIsNotNone(snapshot.confirmed_effective_state)
        self.assertEqual(
            snapshot.confirmed_effective_state[0].ordered_paths[0].ifindex,
            11,
        )
        self.assertEqual(
            snapshot.blocking_problems,
            ("D.002 current realization is unconfirmed",),
        )
        self.assertEqual(
            snapshot.unknown_or_unconfirmed_fields,
            ("wireguard_peer_realizations",),
        )

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


    def test_human_status_renders_effective_order_and_per_path_availability(self):
        configured = build_configured_intent_status(parse_release1_config("""
[device.ovpn]
enabled = true
expected_interfaces = ["vpn*/2"]
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
        first = LogicalPathId("ovpn", 0, 0)
        second = LogicalPathId("ovpn", 0, 1)
        agent.confirm_effective(
            (
                PayloadProfileRequest(
                    "alpha",
                    Direction.OUTBOUND,
                    (IPv4Network("10.0.0.0/8"),),
                    (first, second),
                ),
            ),
            (
                PathBinding(first, InterfaceIdentity("vpn0", 11)),
                PathBinding(second, InterfaceIdentity("vpn1", 12)),
            ),
        )
        agent.confirm_availability((ProbePolicyOwner("alpha", second),))

        self.assertEqual(
            render_runtime_status_text(agent.snapshot()),
            """VPN-GATE development
Devices
    ovpn: vpn0, vpn1
Profiles
    alpha
        01. vpn0 available (icmp/198.51.100.10)
        02. vpn1 not available (icmp/198.51.100.10)""",
        )

    def test_human_status_reports_unconfirmed_state_as_unknown(self):
        agent = RuntimeStatusAgent(self.configured())
        self.assertEqual(
            render_runtime_status_text(agent.snapshot()),
            """VPN-GATE development
Devices
    ovpn: unknown
Profiles
    alpha: unknown""",
        )

    def test_file_publisher_skips_equivalent_snapshot_and_publishes_change(self):
        agent = RuntimeStatusAgent(self.configured())
        publisher = RuntimeStatusFilePublisher(
            Path("/run/test-status.json"),
            Path("/run/test-status.txt"),
        )
        with (
            patch("rou.runtime_status.write_runtime_status_json") as write_json,
            patch("rou.runtime_status.write_runtime_status_text") as write_text,
        ):
            first = agent.snapshot()
            self.assertTrue(publisher.publish(first))
            self.assertFalse(publisher.publish(agent.snapshot()))
            self.assertEqual(write_json.call_count, 1)
            self.assertEqual(write_text.call_count, 1)

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
            self.assertTrue(publisher.publish(agent.snapshot()))
            self.assertEqual(write_json.call_count, 2)
            self.assertEqual(write_text.call_count, 2)

    def test_text_publisher_replaces_one_current_snapshot(self):
        agent = RuntimeStatusAgent(self.configured())
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "status.txt"
            write_runtime_status_text(path, agent.snapshot())
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                """VPN-GATE development
Devices
    ovpn: unknown
Profiles
    alpha: unknown
""",
            )
            self.assertEqual(
                tuple(item.name for item in Path(root).iterdir()),
                ("status.txt",),
            )

    def test_release_version_reader_uses_canonical_semver_text(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "VERSION"
            path.write_text("0.1.0\n", encoding="ascii")
            self.assertEqual(read_release_version(path), "0.1.0")
            path.write_text("release-1\n", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "Semantic Versioning"):
                read_release_version(path)

    def test_json_publisher_replaces_one_current_snapshot(self):
        agent = RuntimeStatusAgent(self.configured())
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "status.json"
            write_runtime_status_json(path, agent.snapshot())
            first = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(first["version"], "development")
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
