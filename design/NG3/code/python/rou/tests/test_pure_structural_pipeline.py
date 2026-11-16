from __future__ import annotations

import ipaddress
import unittest

from rou import (
    AvailabilityPriorityError,
    DeviceBindingState,
    InterfaceIdentity,
    LogicalPathId,
    RoutePriorityPathRoute,
    build_payload_profile_requests,
    calculate_effective_path_order,
    classify_inbound_profile,
    classify_outbound_profile,
    compile_payload_forward_policy,
    parse_ip_link_inventory,
    parse_structural_config,
    project_device_bindings,
)


class PureStructuralPipelineIntegrationTests(unittest.TestCase):
    def test_outbound_pipeline_preserves_policy_and_changes_priority_only(self):
        cfg = parse_structural_config("""
[device.oc]
enabled = true
expected_interfaces = ["fixed0", "vpns*/2"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
""")
        inventory = parse_ip_link_inventory(
            '[{"ifindex":12,"ifname":"vpns01"},'
            '{"ifindex":7,"ifname":"fixed0"},'
            '{"ifindex":11,"ifname":"vpns00"}]'
        )
        binding = project_device_bindings(
            cfg.device_binding_intents,
            DeviceBindingState.empty(),
            inventory,
        )
        request = build_payload_profile_requests(
            cfg.profiles.values(),
            binding.bindings,
        )[0]

        self.assertEqual(
            request.ordered_paths,
            (
                LogicalPathId("oc", 0, 0),
                LogicalPathId("oc", 1, 0),
                LogicalPathId("oc", 1, 1),
            ),
        )
        classified = classify_outbound_profile(
            (request,),
            ipaddress.IPv4Address("10.20.30.40"),
        )
        self.assertEqual(classified, request)

        effective = calculate_effective_path_order(
            request.ordered_paths,
            (LogicalPathId("oc", 0, 0),),
        )
        self.assertEqual(
            effective,
            (
                LogicalPathId("oc", 1, 0),
                LogicalPathId("oc", 1, 1),
                LogicalPathId("oc", 0, 0),
            ),
        )
        self.assertEqual(set(effective), set(request.ordered_paths))

        host_boundary = InterfaceIdentity("host0", 100)
        route_facts = tuple(
            RoutePriorityPathRoute(item.path_id, item.endpoint)
            for item in binding.bindings
        )
        forward = compile_payload_forward_policy(
            (request,),
            route_facts,
            host_boundary,
        )
        self.assertEqual(len(forward.rules), 6)
        self.assertEqual(
            {
                (item.ingress, item.egress)
                for item in forward.rules
            },
            {
                (host_boundary, item.endpoint)
                for item in binding.bindings
            }
            | {
                (item.endpoint, host_boundary)
                for item in binding.bindings
            },
        )

    def test_zero_binding_profile_remains_classifiable_policy_domain(self):
        cfg = parse_structural_config("""
[device.future]
enabled = false

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["future"]
""")
        binding = project_device_bindings(
            cfg.device_binding_intents,
            DeviceBindingState.empty(),
            (),
        )
        request = build_payload_profile_requests(
            cfg.profiles.values(),
            binding.bindings,
        )[0]

        self.assertEqual(request.ordered_paths, ())
        self.assertEqual(
            classify_outbound_profile(
                (request,),
                ipaddress.IPv4Address("10.1.2.3"),
            ),
            request,
        )
        self.assertEqual(
            calculate_effective_path_order(request.ordered_paths, ()),
            (),
        )
        forward = compile_payload_forward_policy(
            (request,),
            (),
            InterfaceIdentity("host0", 100),
        )
        self.assertEqual(forward.rules, ())

    def test_release1_inbound_pipeline_requires_actual_single_ingress_path(self):
        cfg = parse_structural_config("""
[device.wg]
enabled = true
expected_interfaces = ["wg0"]

[profile.support]
enabled = true
direction = "inbound"
destinations = ["10.0.0.0/8"]
device_order = ["wg"]
""")
        inventory = parse_ip_link_inventory(
            '[{"ifindex":9,"ifname":"wg0"}]'
        )
        binding = project_device_bindings(
            cfg.device_binding_intents,
            DeviceBindingState.empty(),
            inventory,
        )
        request = build_payload_profile_requests(
            cfg.profiles.values(),
            binding.bindings,
        )[0]
        ingress = LogicalPathId("wg", 0, 0)

        self.assertEqual(request.ordered_paths, (ingress,))
        self.assertEqual(
            classify_inbound_profile(
                (request,),
                ingress,
                ipaddress.IPv4Address("10.9.8.7"),
            ),
            request,
        )
        self.assertIsNone(
            classify_inbound_profile(
                (request,),
                LogicalPathId("other", 0, 0),
                ipaddress.IPv4Address("10.9.8.7"),
            )
        )

        host_boundary = InterfaceIdentity("host0", 100)
        route_facts = tuple(
            RoutePriorityPathRoute(item.path_id, item.endpoint)
            for item in binding.bindings
        )
        forward = compile_payload_forward_policy(
            (request,),
            route_facts,
            host_boundary,
        )
        self.assertEqual(len(forward.rules), 2)
        endpoint = binding.bindings[0].endpoint
        self.assertEqual(
            {
                (item.ingress, item.egress)
                for item in forward.rules
            },
            {
                (endpoint, host_boundary),
                (host_boundary, endpoint),
            },
        )


if __name__ == "__main__":
    unittest.main()
