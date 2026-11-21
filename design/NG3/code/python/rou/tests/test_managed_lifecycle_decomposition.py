from __future__ import annotations

from ipaddress import IPv4Interface
import unittest
from unittest.mock import Mock, patch

from rou.managed_network_domain import (
    ManagedL3BoundaryEnsureResult,
    ManagedL3BoundaryVerification,
    ManagedNetworkDomainError,
    ManagedNetworkDomainSpec,
    ManagedNetworkEnvironmentVerification,
    ensure_managed_l3_boundary,
    ensure_managed_network_environment,
    preflight_managed_l3_boundary,
)


SPEC = ManagedNetworkDomainSpec(
    namespace="vg-test",
    host_interface="vghost0",
    inner_interface="host0",
    inner_address=IPv4Interface("198.19.255.2/32"),
)

PRIVATE_BOUNDARY = ManagedL3BoundaryVerification(
    confirmed=True,
    errors=(),
)


class ManagedLifecycleDecompositionTests(unittest.TestCase):
    def test_environment_existing_drift_is_repaired(self):
        runner = Mock()
        with (
            patch(
                "rou.managed_network_domain.preflight_managed_network_environment",
                return_value=True,
            ),
            patch(
                "rou.managed_network_domain.verify_managed_network_environment",
                return_value=ManagedNetworkEnvironmentVerification(True, ()),
            ),
        ):
            result = ensure_managed_network_environment(SPEC, runner)

        self.assertFalse(result.created)
        self.assertTrue(result.confirmed)
        runner.run.assert_called_once_with(
            ("ip", "-n", SPEC.namespace, "link", "set", "lo", "up")
        )

    def test_exact_environment_with_absent_transition_is_recoverable(self):
        with (
            patch(
                "rou.managed_network_domain._namespace_names",
                return_value=(SPEC.namespace,),
            ),
            patch(
                "rou.managed_network_domain._require_containment",
            ),
            patch(
                "rou.managed_network_domain._link_rows",
                side_effect=([], []),
            ),
        ):
            self.assertFalse(preflight_managed_l3_boundary(SPEC, object()))

    def test_owned_transition_property_drift_is_repaired(self):
        repaired = ManagedL3BoundaryVerification(
            confirmed=True,
            errors=(),
            private_boundary=None,
        )
        with (
            patch(
                "rou.managed_network_domain.verify_managed_network_environment",
                return_value=ManagedNetworkEnvironmentVerification(True, ()),
            ),
            patch(
                "rou.managed_network_domain.preflight_managed_l3_boundary",
                return_value=True,
            ),
            patch(
                "rou.managed_network_domain._converge_managed_l3_boundary_properties",
            ) as converge,
            patch(
                "rou.managed_network_domain.verify_managed_l3_boundary",
                return_value=repaired,
            ),
        ):
            result = ensure_managed_l3_boundary(SPEC, object())

        self.assertIsInstance(result, ManagedL3BoundaryEnsureResult)
        self.assertFalse(result.created)
        self.assertTrue(result.confirmed)
        converge.assert_called_once_with(SPEC, unittest.mock.ANY)

    def test_orphan_host_endpoint_without_environment_is_conflict(self):
        host = {
            "ifname": SPEC.host_interface,
            "ifindex": 10,
            "link_index": 11,
            "flags": ["UP"],
            "linkinfo": {"info_kind": "veth"},
        }
        with (
            patch(
                "rou.managed_network_domain._namespace_names",
                return_value=(),
            ),
            patch(
                "rou.managed_network_domain._link_rows",
                return_value=[host],
            ),
        ):
            with self.assertRaisesRegex(
                ManagedNetworkDomainError,
                "without managed network environment",
            ):
                preflight_managed_l3_boundary(SPEC, object())

    def test_nonreciprocal_existing_veth_is_structural_conflict(self):
        host = {
            "ifname": SPEC.host_interface,
            "ifindex": 10,
            "link_index": 99,
            "flags": [],
            "linkinfo": {"info_kind": "veth"},
        }
        inner = {
            "ifname": SPEC.inner_interface,
            "ifindex": 11,
            "link_index": 10,
            "flags": [],
            "linkinfo": {"info_kind": "veth"},
        }
        with (
            patch(
                "rou.managed_network_domain._namespace_names",
                return_value=(SPEC.namespace,),
            ),
            patch(
                "rou.managed_network_domain._require_containment",
            ),
            patch(
                "rou.managed_network_domain._link_rows",
                side_effect=([host], [inner], [host], [inner]),
            ),
        ):
            with self.assertRaisesRegex(
                ManagedNetworkDomainError,
                "identity/ownership conflict",
            ):
                preflight_managed_l3_boundary(SPEC, object())


if __name__ == "__main__":
    unittest.main()
