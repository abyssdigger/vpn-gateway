from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
import unittest

from rou.binding import LogicalPathId
from rou.interface_identity import InterfaceIdentity
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.payload_profile import PayloadProfileRequest
from rou.probe_desired import (
    ProbeDesiredAssemblyError,
    build_probe_desired_assembly,
)
from rou.probe_policy import ProbeLocalPlatform
from rou.release1_config import parse_release1_config
from rou.route_priority_inventory import RoutePriorityPathRoute
from rou.domain import Direction


WG = LogicalPathId("wg", 0, 0)
OC = LogicalPathId("oc", 0, 0)
WG_EP = InterfaceIdentity("wg0", 10)
OC_EP = InterfaceIdentity("oc0", 20)
LOCAL = ProbeLocalPlatform(4242, 0x20000001)


def profile(profile_id, paths):
    return PayloadProfileRequest(
        profile_id,
        Direction.OUTBOUND,
        (IPv4Network("10.0.0.0/8"),),
        tuple(paths),
    )


class ProbeDesiredAssemblyTests(unittest.TestCase):
    def test_shared_layout_contains_payload_and_probe_owners(self):
        cfg = parse_release1_config("""
[device.wg]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = false

[device.wg.availability_check]
mechanism = "icmp"
target = "198.51.100.10"

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["wg"]
availability_check = "default"
""")
        result = build_probe_desired_assembly(
            cfg,
            (profile("corp", (WG,)),),
            (RoutePriorityPathRoute(WG, WG_EP),),
            NG3_LINUX_POLICY_PLATFORM,
            LOCAL,
        )
        self.assertEqual(len(result.layout.payload), 1)
        self.assertEqual(len(result.layout.probe), 1)
        self.assertEqual(result.layout.probe[0].owner.profile_id, "corp")
        self.assertEqual(result.layout.probe[0].owner.path_id, WG)
        self.assertEqual(len(result.probe.routes), 2)
        self.assertEqual(len(result.probe.rules), 1)
        self.assertEqual(len(result.probe.local_rules), 2)

    def test_no_profile_availability_allocates_no_probe_owner(self):
        cfg = parse_release1_config("""
[device.wg]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = false

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["wg"]
""")
        result = build_probe_desired_assembly(
            cfg,
            (profile("corp", (WG,)),),
            (RoutePriorityPathRoute(WG, WG_EP),),
            NG3_LINUX_POLICY_PLATFORM,
            LOCAL,
        )
        self.assertEqual(result.layout.probe, ())
        self.assertEqual(result.probe.routes, ())
        self.assertEqual(result.probe.rules, ())
        self.assertEqual(result.probe.local_rules, ())

    def test_same_target_two_paths_get_distinct_probe_allocations(self):
        cfg = parse_release1_config("""
[device.wg]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = false

[device.wg.availability_check]
mechanism = "icmp"
target = "198.51.100.10"

[device.oc]
enabled = true
expected_interfaces = ["oc0"]
use_outbound_nat = false

[device.oc.availability_check]
mechanism = "icmp"
target = "198.51.100.10"

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["wg", "oc"]
availability_check = "default"
""")
        result = build_probe_desired_assembly(
            cfg,
            (profile("corp", (WG, OC)),),
            (
                RoutePriorityPathRoute(WG, WG_EP),
                RoutePriorityPathRoute(OC, OC_EP),
            ),
            NG3_LINUX_POLICY_PLATFORM,
            LOCAL,
        )
        self.assertEqual(len(result.layout.probe), 2)
        self.assertEqual(
            len({item.table for item in result.layout.probe}),
            2,
        )
        self.assertEqual(
            len({item.rule_priority for item in result.layout.probe}),
            2,
        )
        self.assertEqual(
            {rule.endpoint for rule in result.probe.rules},
            {WG_EP, OC_EP},
        )
        self.assertEqual(
            {rule.target for rule in result.probe.rules},
            {IPv4Address("198.51.100.10")},
        )

    def test_duplicate_path_route_is_rejected_at_assembly_boundary(self):
        cfg = parse_release1_config("""
[device.wg]
enabled = true
expected_interfaces = ["wg0"]
use_outbound_nat = false

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["wg"]
""")
        with self.assertRaisesRegex(
            ProbeDesiredAssemblyError,
            "duplicate logical path",
        ):
            build_probe_desired_assembly(
                cfg,
                (profile("corp", (WG,)),),
                (
                    RoutePriorityPathRoute(WG, WG_EP),
                    RoutePriorityPathRoute(WG, InterfaceIdentity("wg1", 11)),
                ),
                NG3_LINUX_POLICY_PLATFORM,
                LOCAL,
            )


if __name__ == "__main__":
    unittest.main()
