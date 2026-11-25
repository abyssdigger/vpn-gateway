from ipaddress import IPv4Address
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from rou.alpha_runtime import (
    AlphaPreparedPolicy,
    AlphaReconcileStatus,
    AlphaRuntimeError,
    build_alpha_availability_ownership_dependencies,
    reconcile_alpha_availability_wireguard_once,
    reconcile_alpha_payload_once,
    reconcile_alpha_wireguard_peers_once,
)
from rou.host_publication_policy import HostPublicationSelectorKind
from rou.interface_identity import InterfaceIdentity
from rou.payload_routing_desired import ManagedRouteType
from rou.managed_device_manager import (
    ManagedDeviceDesiredState,
    ManagedDeviceRealization,
)
from rou.managed_wireguard_adapter import ManagedWireGuardState
from rou.probe_runtime import ProbeOwnershipDependencyState
from rou.wireguard_peer_manager import (
    WireGuardGroupOwnershipRecord,
    WireGuardPeerRealization,
)
from rou.wireguard_peer_runtime import WireGuardPeerRuntimeResult


CONFIG = """
[device.ovpn]
enabled = true
expected_interfaces = ["vpn0"]
use_outbound_nat = false
allow_vpn_client = "udp:11941>198.19.254.2:11940"

[profile.alpha]
enabled = true
direction = "outbound"
destinations = ["10.253.0.1/32"]
device_order = ["ovpn"]
"""


class AlphaPreparedPolicyTests(unittest.TestCase):
    def test_managed_vpn_is_retained_for_runtime_materialization(self):
        prepared = AlphaPreparedPolicy.from_text(
            """
[device.wg-main]
enabled = true
use_outbound_nat = true

[device.wg-main.managed_vpn]
kind = "wireguard"
interface = "wg0"
address = "10.200.0.1/32"
private_key_file = "/etc/vpn-gate/secrets/wg-main.key"

[[device.wg-main.managed_vpn.peers]]
id = "edge-a"
public_key = "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="
endpoint = "198.51.100.10:51820"
probe_target = "10.201.0.1"

[profile.alpha]
enabled = true
direction = "outbound"
destinations = ["10.253.0.0/16"]
device_order = ["wg-main"]
""",
            local_address=IPv4Address("198.19.255.2"),
        )
        self.assertEqual(
            tuple(prepared.current_config.managed_vpns),
            ("wg-main",),
        )
        self.assertEqual(
            prepared.config.structural.devices["wg-main"].expected_interfaces[0].value,
            "wg0",
        )

    def test_managed_wireguard_current_path_joins_shared_probe_plane(self):
        prepared = AlphaPreparedPolicy.from_text(
            """
[device.wg-main]
enabled = true
use_outbound_nat = true

[device.wg-main.managed_vpn]
kind = "wireguard"
interface = "wg0"
address = "10.200.0.1/32"
private_key_file = "/etc/vpn-gate/secrets/wg-main.key"

[[device.wg-main.managed_vpn.peers]]
id = "edge-a"
public_key = "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="
endpoint = "198.51.100.10:51820"
probe_target = "10.201.0.1"

[profile.alpha]
enabled = true
direction = "outbound"
destinations = ["10.253.0.0/16"]
device_order = ["wg-main"]

[profile.alpha.availability_check]
mechanism = "icmp"
target = "10.253.0.1"
""",
            local_address=IPv4Address("198.19.255.2"),
        )
        host_boundary = InterfaceIdentity("vnga-inner0", 7)
        desired = prepared.build_current(
            host_boundary,
            (
                InterfaceIdentity("lo", 1),
                host_boundary,
                InterfaceIdentity("wg0", 11),
            ),
        )

        assembly = prepared.last_probe_assembly
        self.assertIsNotNone(assembly)
        assert assembly is not None
        self.assertEqual(len(assembly.availability_intents), 1)
        self.assertEqual(len(assembly.peer_intents), 1)
        self.assertEqual(len(assembly.group_intents), 1)
        self.assertEqual(
            {type(item.owner).__name__ for item in assembly.probe.rules},
            {
                "ProbePolicyOwner",
                "WireGuardPeerProbeOwner",
                "WireGuardGroupProbeOwner",
            },
        )
        self.assertEqual(
            len(desired.nft.probe_local),
            len(assembly.probe.local_rules),
        )
        self.assertEqual(
            {context.intent.owner for context in prepared.availability_runtime.current_contexts},
            {assembly.availability_intents[0].owner},
        )

    def test_wireguard_peer_helper_uses_current_alpha_probe_plane(self):
        prepared = AlphaPreparedPolicy.from_text(
            """
[device.wg-main]
enabled = true
use_outbound_nat = false

[device.wg-main.managed_vpn]
kind = "wireguard"
interface = "wg0"
address = "10.200.0.1/32"
private_key_file = "/run/private.key"

[[device.wg-main.managed_vpn.peers]]
id = "edge-a"
public_key = "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="
endpoint = "198.51.100.10:51820"
probe_target = "10.201.0.1"

[profile.alpha]
enabled = true
direction = "outbound"
destinations = ["10.253.0.0/16"]
device_order = ["wg-main"]

[profile.alpha.availability_check]
mechanism = "icmp"
target = "10.253.0.1"
""",
            local_address=IPv4Address("198.19.255.2"),
        )
        host_boundary = InterfaceIdentity("vnga-inner0", 7)
        prepared.build_current(
            host_boundary,
            (
                InterfaceIdentity("lo", 1),
                host_boundary,
                InterfaceIdentity("wg0", 11),
            ),
        )
        base = ManagedDeviceRealization(
            device_id="wg-main",
            desired_state=ManagedDeviceDesiredState.PRESENT,
            desired_generation="base-a",
            confirmed_state=ManagedWireGuardState.PRESENT,
            confirmed_generation="base-a",
        )
        coordinator = SimpleNamespace()
        coordinator.reconcile = Mock(
            return_value=WireGuardPeerRuntimeResult(())
        )
        backend = object()

        with patch(
            "rou.alpha_runtime.LinuxStructuralPolicyBackend",
            return_value=backend,
        ):
            result = reconcile_alpha_wireguard_peers_once(
                prepared,
                (base,),
                coordinator,
                object(),
                object(),
                object(),
            )

        self.assertTrue(result.confirmed)
        coordinator.reconcile.assert_called_once()
        args, kwargs = coordinator.reconcile.call_args
        self.assertIs(args[0], prepared.current_config)
        self.assertEqual(args[1], (base,))
        self.assertEqual(args[2], prepared.last_path_routes)
        self.assertIs(args[3], prepared.last_probe_assembly)
        self.assertIs(kwargs["snapshot_observer"], backend)
        self.assertIn("probe_driver", kwargs)
        self.assertIn("ownership", kwargs)

    def test_wireguard_peer_helper_requires_current_probe_plane(self):
        prepared = AlphaPreparedPolicy.from_text(
            CONFIG,
            local_address=IPv4Address("198.19.255.2"),
        )
        with self.assertRaisesRegex(
            AlphaRuntimeError,
            "current probe desired assembly",
        ):
            reconcile_alpha_wireguard_peers_once(
                prepared,
                (),
                SimpleNamespace(),
                object(),
                object(),
                object(),
            )

    def test_external_device_still_uses_current_parser_compatibility_path(self):
        prepared = AlphaPreparedPolicy.from_text(
            CONFIG,
            local_address=IPv4Address("198.19.255.2"),
        )
        self.assertEqual(
            tuple(prepared.config.structural.devices),
            ("ovpn",),
        )

    def test_zero_path_is_fail_closed_but_admits_vpn_transport(self):
        prepared = AlphaPreparedPolicy.from_text(
            CONFIG,
            local_address=IPv4Address("198.19.255.2"),
        )
        host_boundary = InterfaceIdentity("vnga-inner0", 7)
        desired = prepared.build_current(
            host_boundary,
            (
                InterfaceIdentity("lo", 1),
                host_boundary,
            ),
        )

        self.assertEqual(len(desired.routing.rules), 1)
        self.assertEqual(len(desired.routing.routes), 1)
        self.assertIs(
            desired.routing.routes[0].route_type,
            ManagedRouteType.BLACKHOLE,
        )
        self.assertEqual(desired.nft.profile_forward.rules, ())
        self.assertEqual(desired.nft.payload_nat.masquerade_rules, ())
        self.assertEqual(len(desired.nft.local_integration.rules), 2)
        self.assertEqual(desired.nft.device_firewall.chains, ())

    def test_new_exact_vpn_endpoint_becomes_current_path_without_nat(self):
        prepared = AlphaPreparedPolicy.from_text(
            CONFIG,
            local_address=IPv4Address("198.19.255.2"),
        )
        host_boundary = InterfaceIdentity("vnga-inner0", 7)
        prepared.build_current(
            host_boundary,
            (
                InterfaceIdentity("lo", 1),
                host_boundary,
            ),
        )

        vpn0 = InterfaceIdentity("vpn0", 11)
        desired = prepared.build_current(
            host_boundary,
            (
                InterfaceIdentity("lo", 1),
                host_boundary,
                vpn0,
            ),
        )

        unicast = tuple(
            route
            for route in desired.routing.routes
            if route.route_type is ManagedRouteType.UNICAST
        )
        self.assertEqual(len(unicast), 1)
        self.assertEqual(unicast[0].endpoint, vpn0)
        self.assertEqual(str(unicast[0].destination), "10.253.0.1/32")
        self.assertEqual(desired.nft.payload_nat.masquerade_rules, ())
        self.assertEqual(len(desired.nft.profile_forward.rules), 2)
        self.assertEqual(len(desired.nft.local_integration.rules), 2)

    def test_inbound_current_path_materializes_stack_return_affinity(self):
        config = CONFIG.replace(
            'direction = "outbound"',
            'direction = "inbound"',
        ).replace(
            'use_outbound_nat = false\n',
            '',
        )
        prepared = AlphaPreparedPolicy.from_text(
            config,
            local_address=IPv4Address("198.19.255.2"),
        )
        host_boundary = InterfaceIdentity("vnga-inner0", 7)
        vpn0 = InterfaceIdentity("vpn0", 11)
        desired = prepared.build_current(
            host_boundary,
            (InterfaceIdentity("lo", 1), host_boundary, vpn0),
        )
        self.assertIsNotNone(desired.stack_return_affinity)
        self.assertEqual(len(desired.stack_return_affinity.classifiers), 1)
        self.assertEqual(len(desired.stack_return_affinity.rules), 1)


    def test_alpha_materializes_availability_and_profile_snat(self):
        availability = AlphaPreparedPolicy.from_text(
            CONFIG.replace(
                'device_order = ["ovpn"]',
                'device_order = ["ovpn"]\n'
                '[profile.alpha.availability_check]\n'
                'mechanism = "icmp"\n'
                'target = "10.253.0.1"',
            ),
            local_address=IPv4Address("198.19.255.2"),
        )
        host_boundary = InterfaceIdentity("vnga-inner0", 7)
        vpn0 = InterfaceIdentity("vpn0", 11)
        desired = availability.build_current(
            host_boundary,
            (InterfaceIdentity("lo", 1), host_boundary, vpn0),
        )
        self.assertIsNotNone(availability.last_probe_assembly)
        self.assertEqual(
            len(availability.last_probe_assembly.availability_intents),
            1,
        )
        self.assertEqual(len(desired.nft.probe_local), 2)

        snat = AlphaPreparedPolicy.from_text(
            CONFIG.replace(
                'direction = "outbound"',
                'direction = "inbound+snat>198.19.255.10"',
            ).replace(
                'use_outbound_nat = false\n',
                "",
            ),
            local_address=IPv4Address("198.19.255.2"),
        )
        self.assertEqual(
            str(snat.config.profiles["alpha"].effective_snat_address),
            "198.19.255.10",
        )
        snat_desired = snat.build_current(
            host_boundary,
            (InterfaceIdentity("lo", 1), host_boundary, vpn0),
        )
        self.assertIsNotNone(snat_desired.stack_return_affinity)
        self.assertEqual(len(snat_desired.nft.payload_nat.profile_snat_rules), 1)
        snat_rule = snat_desired.nft.payload_nat.profile_snat_rules[0]
        self.assertEqual(str(snat_rule.source_address), "198.19.255.10")
        self.assertEqual(snat_rule.egress, host_boundary)


    def test_alpha_materializes_canonical_server_publication_both_halves(self):
        replacement = (
            'use_outbound_nat = false\n'
            'publish_vpn_server = [\n'
            '    "tcp/eth0:443,8000-8001>8443,18000-18001",\n'
            '    "udp:53",\n'
            ']\n'
        )
        prepared = AlphaPreparedPolicy.from_text(
            CONFIG.replace("use_outbound_nat = false\n", replacement),
            local_address=IPv4Address("198.19.255.2"),
        )
        host_boundary = InterfaceIdentity("vnga-inner0", 7)
        desired = prepared.build_current(
            host_boundary,
            (InterfaceIdentity("lo", 1), host_boundary),
        )
        self.assertEqual(len(desired.nft.local_publication.rules), 8)

        host = prepared.build_host_publication_desired()
        self.assertEqual(len(host.rules), 4)
        first = next(rule for rule in host.rules if rule.host_port == 443)
        self.assertIs(first.selector_kind, HostPublicationSelectorKind.INTERFACE)
        self.assertEqual(first.selector_value, "eth0")
        self.assertEqual(first.internal_port, 8443)
        self.assertEqual(str(first.internal_address), "198.19.255.2")
        udp = next(rule for rule in host.rules if rule.protocol.value == "udp")
        self.assertIs(udp.selector_kind, HostPublicationSelectorKind.ANY)
        self.assertEqual(udp.host_port, 53)
        self.assertEqual(udp.internal_port, 53)

    def test_alpha_rejects_ambiguous_server_publication_projection(self):
        replacement = (
            'use_outbound_nat = false\n'
            'publish_vpn_server = [\n'
            '    "tcp:443>8443",\n'
            '    "tcp/198.51.100.10:443>9443",\n'
            ']\n'
        )
        with self.assertRaisesRegex(
            Exception,
            "host publication projection failed before runtime mutation",
        ):
            AlphaPreparedPolicy.from_text(
                CONFIG.replace("use_outbound_nat = false\n", replacement),
                local_address=IPv4Address("198.19.255.2"),
            )

    def test_alpha_private_peer_firewall_is_path_scoped(self):
        config = """
[device.oc]
enabled = true
expected_interfaces = ["vpn*/2"]
use_outbound_nat = false
firewall = [
    "out deny udp to 10.253.0.1/32:53 via peer 172.20.130.6",
    "out allow icmp to 10.253.0.1/32",
]

[profile.alpha]
enabled = true
direction = "outbound"
destinations = ["10.253.0.1/32"]
device_order = ["oc"]
"""
        prepared = AlphaPreparedPolicy.from_text(
            config,
            local_address=IPv4Address("198.19.255.2"),
        )
        self.assertTrue(prepared.requires_private_peer_observation)

        host_boundary = InterfaceIdentity("vnga-inner0", 7)
        vpn_a = InterfaceIdentity("vpn0", 11)
        vpn_b = InterfaceIdentity("vpn1", 12)
        desired = prepared.build_current(
            host_boundary,
            (
                InterfaceIdentity("lo", 1),
                host_boundary,
                vpn_a,
                vpn_b,
            ),
            path_private_peers={
                InterfaceIdentity("lo", 1): None,
                host_boundary: None,
                vpn_a: IPv4Address("172.20.130.6"),
                vpn_b: IPv4Address("172.20.130.5"),
            },
        )

        self.assertEqual(len(desired.nft.device_firewall.chains), 4)
        first_out = desired.nft.device_firewall.chains[0]
        second_out = desired.nft.device_firewall.chains[2]
        self.assertEqual(len(first_out.rules), 3)
        self.assertEqual(len(second_out.rules), 2)

        ordinary = AlphaPreparedPolicy.from_text(
            CONFIG,
            local_address=IPv4Address("198.19.255.2"),
        )
        self.assertFalse(ordinary.requires_private_peer_observation)

    def test_alpha_exact_if_firewall_is_path_scoped_without_peer_observation(self):
        config = """
[device.oc]
enabled = true
expected_interfaces = ["vpn*/2"]
use_outbound_nat = false
firewall = [
    "out deny udp to 10.253.0.1/32:53 via if vpn0",
    "out allow icmp to 10.253.0.1/32",
]

[profile.alpha]
enabled = true
direction = "outbound"
destinations = ["10.253.0.1/32"]
device_order = ["oc"]
"""
        prepared = AlphaPreparedPolicy.from_text(
            config,
            local_address=IPv4Address("198.19.255.2"),
        )
        self.assertFalse(prepared.requires_private_peer_observation)

        host_boundary = InterfaceIdentity("vnga-inner0", 7)
        vpn_a = InterfaceIdentity("vpn0", 11)
        vpn_b = InterfaceIdentity("vpn1", 12)
        desired = prepared.build_current(
            host_boundary,
            (
                InterfaceIdentity("lo", 1),
                host_boundary,
                vpn_a,
                vpn_b,
            ),
        )

        self.assertEqual(len(desired.nft.device_firewall.chains), 4)
        first_out = desired.nft.device_firewall.chains[0]
        second_out = desired.nft.device_firewall.chains[2]
        self.assertEqual(len(first_out.rules), 3)
        self.assertEqual(len(second_out.rules), 2)

    def test_path_observation_failure_closes_forwarding(self):
        prepared = AlphaPreparedPolicy.from_text(
            CONFIG,
            local_address=IPv4Address("198.19.255.2"),
        )
        host_boundary = InterfaceIdentity("vnga-inner0", 7)
        environment = SimpleNamespace(
            verification=SimpleNamespace(errors=()),
        )
        boundary = SimpleNamespace(
            verification=SimpleNamespace(
                errors=(),
                private_boundary=host_boundary,
            ),
        )
        portal = SimpleNamespace(errors=())
        containment = SimpleNamespace(
            confirmed=True,
            diagnostic=None,
        )

        with (
            patch(
                "rou.alpha_runtime.preflight_managed_network_environment",
                return_value=True,
            ),
            patch(
                "rou.alpha_runtime.ensure_managed_network_environment",
                return_value=environment,
            ),
            patch(
                "rou.alpha_runtime.ensure_managed_l3_boundary",
                return_value=boundary,
            ),
            patch(
                "rou.alpha_runtime.ensure_ordinary_side_portal",
                return_value=portal,
            ),
            patch(
                "rou.alpha_runtime.LinuxVpnPathAdapter"
            ) as adapter_type,
            patch(
                "rou.alpha_runtime.converge_forwarding_gate_once",
                return_value=containment,
            ) as contain,
        ):
            adapter_type.return_value.observe_interfaces.side_effect = (
                RuntimeError("private-peer observation unavailable")
            )
            result = reconcile_alpha_payload_once(
                prepared,
                SimpleNamespace(namespace="managed"),
                object(),
            )

        self.assertIs(result.status, AlphaReconcileStatus.FAILED)
        self.assertIn(
            "fail-closed containment=confirmed",
            result.diagnostic or "",
        )
        contain.assert_called_once()

    def test_alpha_materializes_canonical_device_nat_and_firewall(self):
        prepared = AlphaPreparedPolicy.from_text(
            CONFIG.replace(
                "use_outbound_nat = false",
                """use_outbound_nat = true
firewall = [
    "out allow icmp to 10.253.0.1/32",
]""",
            ),
            local_address=IPv4Address("198.19.255.2"),
        )
        host_boundary = InterfaceIdentity("vnga-inner0", 7)
        vpn0 = InterfaceIdentity("vpn0", 11)
        desired = prepared.build_current(
            host_boundary,
            (InterfaceIdentity("lo", 1), host_boundary, vpn0),
        )
        self.assertEqual(len(desired.nft.payload_nat.masquerade_rules), 1)
        self.assertEqual(len(desired.nft.device_firewall.chains), 2)


    def test_confirmed_no_owner_is_valid_availability_dependency_generation(self):
        prepared = AlphaPreparedPolicy.from_text(
            """
[device.wg-main]
enabled = true
use_outbound_nat = false

[device.wg-main.managed_vpn]
kind = "wireguard"
interface = "wg0"
address = "10.200.0.1/32"
private_key_file = "/run/private.key"

[[device.wg-main.managed_vpn.peers]]
id = "edge-a"
public_key = "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="
endpoint = "198.51.100.10:51820"
probe_target = "10.201.0.1"

[profile.alpha]
enabled = true
direction = "outbound"
destinations = ["10.253.0.0/16"]
device_order = ["wg-main"]

[profile.alpha.availability_check]
mechanism = "icmp"
target = "10.253.0.1"
""",
            local_address=IPv4Address("198.19.255.2"),
        )
        host_boundary = InterfaceIdentity("vnga-inner0", 7)
        prepared.build_current(
            host_boundary,
            (
                InterfaceIdentity("lo", 1),
                host_boundary,
                InterfaceIdentity("wg0", 11),
            ),
        )
        realization = WireGuardPeerRealization(
            device_id="wg-main",
            base_generation="base-a",
            interface_ifname="wg0",
            interface_ifindex=11,
            group_owners=(
                WireGuardGroupOwnershipRecord("alpha", None),
            ),
            generation="d002-generation-a",
        )
        dependencies = build_alpha_availability_ownership_dependencies(
            prepared,
            WireGuardPeerRuntimeResult((realization,)),
        )
        dependency = next(iter(dependencies.values()))
        self.assertEqual(
            dependency.state,
            ProbeOwnershipDependencyState.CONFIRMED,
        )
        self.assertEqual(
            dependency.generation,
            "d002-generation-a",
        )

        unconfirmed = build_alpha_availability_ownership_dependencies(
            prepared,
            None,
        )
        self.assertEqual(
            next(iter(unconfirmed.values())).state,
            ProbeOwnershipDependencyState.UNCONFIRMED,
        )

    def test_combined_reconcile_orders_d002_before_a007_completion(self):
        prepared = Mock()
        preparation = SimpleNamespace(confirmed=True)
        wireguard = WireGuardPeerRuntimeResult(())
        calls = []

        with (
            patch(
                "rou.alpha_runtime.prepare_alpha_availability_probe_plane_once",
                side_effect=lambda *_: calls.append("prepare") or preparation,
            ),
            patch(
                "rou.alpha_runtime.reconcile_alpha_wireguard_peers_once",
                side_effect=lambda *_: calls.append("d002") or wireguard,
            ),
            patch(
                "rou.alpha_runtime.build_alpha_availability_ownership_dependencies",
                side_effect=lambda *_: calls.append("dependencies") or {},
            ),
            patch(
                "rou.alpha_runtime.reconcile_alpha_availability_after_probe_plane_once",
                side_effect=lambda *_: calls.append("a007_a004")
                or SimpleNamespace(confirmed=True),
            ),
        ):
            result, realized, error = reconcile_alpha_availability_wireguard_once(
                prepared,
                (),
                SimpleNamespace(),
                object(),
                object(),
                object(),
            )

        self.assertTrue(result.confirmed)
        self.assertIs(realized, wireguard)
        self.assertIsNone(error)
        self.assertEqual(
            calls,
            ["prepare", "d002", "dependencies", "a007_a004"],
        )


if __name__ == "__main__":
    unittest.main()
